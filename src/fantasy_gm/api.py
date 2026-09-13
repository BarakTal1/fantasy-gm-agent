import json
import os
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import BaseModel

from fantasy_gm import analytics, proposals, received_trades, trade, trades_history, users
from fantasy_gm.agent import build_agent
from fantasy_gm.config import get_settings
from fantasy_gm.db import execute
from fantasy_gm.ratelimit import RateLimiter
from fantasy_gm.schemas import LeagueSettings
from fantasy_gm.tools import (
    get_all_teams,
    get_free_agents,
    get_league_settings,
    get_trends,
    get_weekly_schedule,
)

_DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"

_checkpointer = None  # set at startup in production; stays None under tests


@asynccontextmanager
async def lifespan(_app):
    global _checkpointer
    cm = PostgresSaver.from_conn_string(get_settings().database_url)
    _checkpointer = cm.__enter__()
    _checkpointer.setup()
    try:
        yield
    finally:
        cm.__exit__(None, None, None)
        _checkpointer = None


app = FastAPI(title="Fantasy GM Agent", lifespan=lifespan)

_ALLOWED_ORIGINS = [
    "http://localhost:5173",   # Vite dev
    "http://127.0.0.1:5173",
]
# In production, add the deployed frontend origin via env (see deploy runbook).
if os.getenv("FRONTEND_ORIGIN"):
    _ALLOWED_ORIGINS.append(os.environ["FRONTEND_ORIGIN"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=_ALLOWED_ORIGINS,
    # Allow the Vercel frontend (production + preview deploys) without depending
    # on an exact FRONTEND_ORIGIN env match (trailing slash / preview-hash safe).
    allow_origin_regex=r"https://fantasy-gm-agent.*\.vercel\.app",
    allow_credentials=True,   # send/receive the session cookie cross-origin
    allow_methods=["*"],
    allow_headers=["*"],
)

# Single-user demo config — replace with real values / auth in a multi-user build.
LEAGUE_KEY = "428.l.123456"
MY_TEAM_KEY = "428.l.123456.t.1"

# ~20 Claude-backed requests per 10 min per IP — generous for a reviewer, caps abuse.
_claude_limiter = RateLimiter(max_requests=20, window_seconds=600)


def _guard(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not _claude_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Rate limit reached — try again shortly.")


class ChatRequest(BaseModel):
    message: str
    conversation_id: str = "default"


class TradeRequest(BaseModel):
    give: list[str]
    get: list[str]


class Credentials(BaseModel):
    email: str
    password: str


class SettingsPatch(BaseModel):
    league_format: str


class LeagueConfigPatch(BaseModel):
    name: str = ""
    format: str
    categories: list[str] = []
    point_weights: dict[str, float] = {}
    roster_slots: dict[str, int] = {}


# Editable option lists surfaced to the Settings editor. Categories/points stats
# are constrained to the stat keys the demo data actually carries, so a manual
# league still computes real analytics; positions match the standard NBA slots.
_CATEGORY_OPTIONS = ["FG%", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"]
_POINT_STAT_OPTIONS = ["PTS", "REB", "AST", "3PTM", "ST", "BLK", "TO"]
_POSITION_OPTIONS = ["PG", "SG", "SF", "PF", "C", "G", "F", "UTIL"]


_COOKIE = "session"


_LOCAL_HOSTS = {"testserver", "localhost", "127.0.0.1"}


def _cookie_policy(request: Request) -> tuple[bool, str]:
    """(secure, samesite) for the session cookie, scoped to the host.

    Real hosts (Vercel↔Railway) are cross-site, so the cookie must be
    SameSite=None + Secure. On local hosts the frontend and API are same-site
    (both `localhost`) served over plain http, where a Secure cookie is dropped
    AND SameSite=None-without-Secure is rejected by browsers — so use Lax, which
    is valid without Secure and still sent on same-site requests."""
    local = (request.url.hostname or "") in _LOCAL_HOSTS
    return (False, "lax") if local else (True, "none")


def _set_session(response: Response, request: Request, user_id: int) -> None:
    secure, samesite = _cookie_policy(request)
    response.set_cookie(_COOKIE, users.make_token(user_id), httponly=True,
                        secure=secure, samesite=samesite,
                        max_age=30 * 24 * 3600, path="/")


def _current_user(request: Request) -> dict | None:
    tok = request.cookies.get(_COOKIE)
    uid = users.decode_token(tok) if tok else None
    return users.get_user_by_id(uid) if uid else None


def _load_league() -> LeagueSettings:
    return get_league_settings(LEAGUE_KEY)


def _user_league(u: dict) -> LeagueSettings:
    """A signed-in user's league settings: their saved manual config if they have
    one, else the demo fixture for their chosen format (single-league Postgres
    cache can't hold two formats at once), else the shared live/DB league."""
    cfg = u.get("league_config") or {}
    if cfg.get("format"):
        return LeagueSettings(
            league_key=LEAGUE_KEY, format=cfg["format"], name=cfg.get("name", ""),
            categories=cfg.get("categories", []),
            point_weights=cfg.get("point_weights", {}),
            roster_slots=cfg.get("roster_slots", {}))
    if get_settings().demo_mode:
        from fantasy_gm import demo
        return demo.demo_league_settings(u["league_format"])
    return _load_league()


def _league_for(request: Request) -> LeagueSettings:
    """League settings for this request — a signed-in user's config, or the shared
    league (patchable in tests / real Yahoo league live) when anonymous."""
    u = _current_user(request)
    if u:
        return _user_league(u)
    return _load_league()


@app.post("/auth/register")
def register(creds: Credentials, request: Request, response: Response) -> dict:
    if not creds.email or not creds.password:
        raise HTTPException(status_code=400, detail="Email and password required.")
    if users.get_user_by_email(creds.email):
        raise HTTPException(status_code=409, detail="Email already registered.")
    u = users.create_user(creds.email, creds.password)
    _set_session(response, request, u["id"])
    return {"email": u["email"], "league_format": u["league_format"]}


@app.post("/auth/login")
def login(creds: Credentials, request: Request, response: Response) -> dict:
    u = users.get_user_by_email(creds.email)
    if not u or not users.verify_password(creds.password, u["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    _set_session(response, request, u["id"])
    return {"email": u["email"], "league_format": u["league_format"]}


@app.post("/auth/logout")
def logout(request: Request, response: Response) -> dict:
    # The browser only clears a cookie when the deletion Set-Cookie carries the
    # SAME attributes it was set with. So mirror _set_session's policy exactly,
    # otherwise a cross-site delete is ignored and the user stays logged in.
    secure, samesite = _cookie_policy(request)
    response.delete_cookie(_COOKIE, path="/", samesite=samesite, secure=secure,
                           httponly=True)
    return {"ok": True}


@app.get("/auth/me")
def me(request: Request) -> dict:
    u = _current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return {"email": u["email"], "league_format": u["league_format"]}


@app.patch("/settings")
def update_settings(patch: SettingsPatch, request: Request) -> dict:
    u = _current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not signed in.")
    if patch.league_format not in {"category", "points"}:
        raise HTTPException(status_code=400, detail="Invalid league format.")
    execute("UPDATE users SET league_format=%s WHERE id=%s",
            (patch.league_format, u["id"]))
    return {"league_format": patch.league_format}


def _yahoo_connected() -> bool:
    """True when a Yahoo OAuth token is stored (Fantasy API access granted)."""
    from fantasy_gm.db import fetch_one
    try:
        return fetch_one("SELECT 1 FROM oauth_tokens WHERE id=1") is not None
    except Exception:
        return False


def _league_config_response(u: dict) -> dict:
    s = _user_league(u)
    cfg = u.get("league_config") or {}
    return {
        "name": s.name,
        "format": s.format,
        "categories": s.categories,
        "point_weights": s.point_weights,
        "roster_slots": s.roster_slots,
        "source": "manual" if cfg.get("format") else "demo",
        "yahoo_connected": _yahoo_connected(),
        "options": {"categories": _CATEGORY_OPTIONS,
                    "point_stats": _POINT_STAT_OPTIONS,
                    "positions": _POSITION_OPTIONS},
    }


@app.get("/settings/league")
def get_league_config(request: Request) -> dict:
    u = _current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not signed in.")
    return _league_config_response(u)


@app.put("/settings/league")
def put_league_config(patch: LeagueConfigPatch, request: Request) -> dict:
    u = _current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not signed in.")
    if patch.format not in {"category", "points"}:
        raise HTTPException(status_code=400, detail="Invalid league format.")
    if patch.format == "category" and not patch.categories:
        raise HTTPException(status_code=400,
                            detail="Pick at least one scoring category.")
    if patch.format == "points" and not patch.point_weights:
        raise HTTPException(status_code=400,
                            detail="Set at least one point weight.")
    config = {"name": patch.name.strip(), "format": patch.format,
              "categories": patch.categories, "point_weights": patch.point_weights,
              "roster_slots": patch.roster_slots}
    users.set_league_config(u["id"], config, patch.format)
    return _league_config_response(users.get_user_by_id(u["id"]))


@app.post("/settings/league/sync-yahoo")
def sync_league_from_yahoo(request: Request) -> dict:
    """Pull league settings from the connected Yahoo account. Graceful fallback:
    while Fantasy API access is still pending (no stored OAuth token), this returns
    409 so the UI can show a clear 'not connected yet' state instead of failing."""
    u = _current_user(request)
    if not u:
        raise HTTPException(status_code=401, detail="Not signed in.")
    if not _yahoo_connected():
        raise HTTPException(
            status_code=409,
            detail="Yahoo isn't connected yet — Fantasy API access is pending "
                   "approval. Set your league up manually for now.")
    from fantasy_gm.yahoo_client import client as yahoo_client
    try:
        s = yahoo_client.parse_league_settings(
            yahoo_client._get(f"league/{LEAGUE_KEY}/settings"))
    except Exception as e:                      # network / parse / auth failure
        raise HTTPException(status_code=502,
                            detail=f"Couldn't reach Yahoo: {e}") from e
    config = {"name": s.name, "format": s.format, "categories": s.categories,
              "point_weights": s.point_weights, "roster_slots": s.roster_slots}
    users.set_league_config(u["id"], config, s.format)
    return _league_config_response(users.get_user_by_id(u["id"]))


MY_WEEK = 15  # demo week


def _all_teams():
    return get_all_teams(LEAGUE_KEY)


def _free_agents():
    return get_free_agents(LEAGUE_KEY)


def _trends_for(ids):
    return get_trends(ids, 14, date.today())


def _week_games():
    return {t: v["games_remaining"] for t, v in get_weekly_schedule(MY_WEEK).items()}


def _players_by_id(ids: list[str]) -> dict:
    idx = {p.player_id: p for t in _all_teams() for p in t.players}
    idx.update({p.player_id: p for p in _free_agents()})
    return {i: idx[i] for i in ids if i in idx}


def _pending_offers() -> list[dict]:
    from fantasy_gm.yahoo_client import client as yahoo_client
    return yahoo_client.fetch_pending_trades(LEAGUE_KEY, MY_TEAM_KEY)


def _verdict(delta, summary, give, get) -> str:
    """Single focused Claude call grounded in the computed deltas.
    `summary` is None for a points-league delta (net fantasy points); otherwise
    `delta`/`summary` are the category-league per-category delta + improved/worsened."""
    model = _make_model()
    if summary is None:
        prompt = (
            "You are an honest NBA fantasy trade analyst for a points league.\n"
            f"Net fantasy-points change to the user's team: {delta['net']} "
            f"(giving up {delta['give_value']} pts, receiving {delta['get_value']} pts).\n"
            f"Giving away: {[p.name for p in give]}; receiving: {[p.name for p in get]}.\n"
            "Give a 3-4 sentence honest verdict and end with exactly one of: "
            "ACCEPT, DECLINE, or COUNTER."
        )
    else:
        prompt = (
            "You are an honest NBA fantasy trade analyst for a category league.\n"
            f"Net category change to the user's team (positive = more of that cat; "
            f"for TO, negative is better): {delta}.\n"
            f"Categories improved: {summary['improved']}; worsened: {summary['worsened']}.\n"
            f"Giving away: {[p.name for p in give]}; receiving: {[p.name for p in get]}.\n"
            "Give a 3-4 sentence honest verdict and end with exactly one of: "
            "ACCEPT, DECLINE, or COUNTER."
        )
    return _text(model.invoke(prompt).content)


def _make_model():
    s = get_settings()
    return ChatAnthropic(model=s.agent_model, api_key=s.anthropic_api_key,
                         max_tokens=4096)


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


def _text(content) -> str:
    if isinstance(content, str):
        return content
    return "".join(b.get("text", "") for b in content
                   if isinstance(b, dict) and b.get("type") == "text")


def _chunk_text(msg) -> str:
    """Text delta from a streamed message chunk (Opus 5 returns block lists)."""
    return _text(getattr(msg, "content", "") or "")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


def _league_info() -> LeagueSettings:
    # Fetch fresh (demo or live) so the league NAME is present — the Postgres
    # league_config cache stores format/categories but not the display name.
    from fantasy_gm.yahoo_client import client as yahoo_client
    return yahoo_client.fetch_league_settings(LEAGUE_KEY)


@app.get("/league/info")
def league_info(request: Request) -> dict:
    # A signed-in user in demo mode sees their chosen format; otherwise fetch fresh
    # from Yahoo (live) / the fixture (demo) so the league display name is present.
    u = _current_user(request)
    if u:
        s = _user_league(u)
        # Fall back to the fixture name when a manual config left the name blank.
        if not s.name and get_settings().demo_mode:
            from fantasy_gm import demo
            s.name = demo.demo_league_settings(u["league_format"]).name
    else:
        s = _league_info()
    return {"name": s.name, "format": s.format, "format_label": s.format_label}


@app.get("/league/teams")
def league_teams() -> dict:
    return {"my_team_key": MY_TEAM_KEY,
            "teams": [t.model_dump() for t in _all_teams()]}


@app.get("/analytics/my-team")
def analytics_my_team(request: Request) -> dict:
    league = _league_for(request)
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    games = _week_games()
    roster_trends = _trends_for([p.player_id for p in mine.players])
    out = {"format": league.format,
           "roster": analytics.roster_week_outlook(
               mine.players, roster_trends, games, league),
           "best_player": analytics.best_player(mine.players, league),
           "position_strengths": analytics.position_strengths(mine.players, league),
           "positional_balance": analytics.positional_balance(
               mine.players, league.roster_slots)}
    if league.is_category:
        out["category_profile"] = analytics.category_profile(
            mine, teams, league.categories)
    return out


@app.get("/analytics/waivers")
def analytics_waivers(request: Request) -> dict:
    league = _league_for(request)
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    fas = _free_agents()
    games = _week_games()
    fa_trends = _trends_for([p.player_id for p in fas])
    out = {"format": league.format, "schedule": games,
           "recommended_pickups": analytics.recommended_pickups(
               mine, teams, fas, fa_trends, games, league)}
    if league.is_points:
        out["points_value_board"] = analytics.points_value_board(
            fas, fa_trends, games, league)
    else:
        out["streaming_board"] = analytics.streaming_board(
            fas, fa_trends, games, league.categories)[:12]
    day_teams = json.loads((_DEMO_DIR / "schedule_by_day.json").read_text())
    out["weekdays"] = analytics.weekday_coverage(mine.players, day_teams)
    out["teams_to_target"] = analytics.teams_to_target(mine.players, fas, day_teams, league)
    return out


@app.get("/analytics/league")
def analytics_league(request: Request) -> dict:
    league = _league_for(request)
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    fas = _free_agents()
    games = _week_games()
    roster_trends = _trends_for([p.player_id for p in mine.players])
    fa_trends = _trends_for([p.player_id for p in fas])
    # Categories drive which stat columns the League table shows. For a points
    # league there are no `categories`, so fall back to the core box-score line.
    stat_cats = league.categories or ["PTS", "REB", "AST", "ST", "BLK", "3PTM", "TO"]
    out = {"format": league.format,
           "teams": [t.model_dump() for t in teams],
           "my_team_key": MY_TEAM_KEY,
           "team_stats": analytics.team_stat_totals(teams, stat_cats, games),
           "buy_low_sell_high": analytics.buy_low_sell_high(
               mine.players + fas, {**roster_trends, **fa_trends},
               league.categories)[:12] if league.is_category else []}
    if league.is_category:
        out["category_profile"] = analytics.category_profile(
            mine, teams, league.categories)
    return out



@app.get("/trades/history")
def trade_history() -> dict:
    """Fabricated past trades with per-player before/after stats (demo shell)."""
    by_id = {p.player_id: p for t in _all_teams() for p in t.players}
    by_id.update({p.player_id: p for p in _free_agents()})
    trades = json.loads((_DEMO_DIR / "trade_history.json").read_text())
    return {"trades": trades_history.build_history(trades, by_id)}


@app.get("/trades/received")
def trades_received() -> dict:
    """Pending trade offers other managers sent you (demo fixture / live-gated)."""
    by_id = {p.player_id: p for t in _all_teams() for p in t.players}
    by_id.update({p.player_id: p for p in _free_agents()})
    return {"offers": received_trades.build_offers(_pending_offers(), by_id)}


@app.get("/trades/suggestions")
def trades_suggestions(request: Request) -> dict:
    """Deterministic suggested trades to offer other teams (Claude on demand)."""
    league = _league_for(request)
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    ids = [p.player_id for t in teams for p in t.players]
    trends = _trends_for(ids)
    return {"format": league.format,
            "suggestions": proposals.suggest_trades(mine, teams, trends, league)}


@app.post("/trade/analyze")
def trade_analyze(req: TradeRequest, request: Request) -> dict:
    _guard(request)
    league = _league_for(request)
    byid = _players_by_id(req.give + req.get)
    give = [byid[i] for i in req.give if i in byid]
    get = [byid[i] for i in req.get if i in byid]
    if league.is_points:
        delta = trade.points_delta(give, get, league)
        verdict = _verdict(delta, None, give, get)
        rec = ("ACCEPT" if "ACCEPT" in verdict else
               "COUNTER" if "COUNTER" in verdict else "DECLINE")
        return {"format": league.format, "delta": delta, "verdict": verdict,
                "recommendation": rec}
    delta = trade.category_delta(give, get, league.categories)
    summary = trade.summarize(delta)
    verdict = _verdict(delta, summary, give, get)
    rec = ("ACCEPT" if "ACCEPT" in verdict else
           "COUNTER" if "COUNTER" in verdict else "DECLINE")
    return {"format": league.format, "delta": delta, "summary": summary,
            "verdict": verdict, "recommendation": rec}


@app.post("/chat")
def chat(req: ChatRequest, request: Request) -> StreamingResponse:
    _guard(request)
    agent = build_agent(league=_league_for(request), league_key=LEAGUE_KEY,
                        my_team_key=MY_TEAM_KEY, model=_make_model(),
                        checkpointer=_checkpointer)

    def gen():
        config = {"configurable": {"thread_id": req.conversation_id}}
        emitted_token = False
        last_id = None
        for mode, chunk in agent.stream(
            {"messages": [HumanMessage(req.message)]},
            config=config,
            stream_mode=["updates", "messages"],
        ):
            if mode == "messages":
                msg, _meta = chunk
                # Only stream assistant text — messages mode also surfaces
                # ToolMessages (raw JSON tool results), which must NOT leak
                # into the answer. AIMessageChunk is a subclass of AIMessage.
                tool_calls = getattr(msg, "tool_calls", None)
                if isinstance(msg, AIMessage) and not tool_calls:
                    text = _chunk_text(msg)
                    if text:
                        # Separate distinct assistant turns (preamble vs final
                        # answer) so markdown blocks don't glue together.
                        mid = getattr(msg, "id", None)
                        if emitted_token and mid != last_id:
                            yield _sse("token", {"text": "\n\n"})
                        last_id = mid
                        emitted_token = True
                        yield _sse("token", {"text": text})
            elif mode == "updates":
                for _node, update in chunk.items():
                    msgs = update.get("messages", []) if isinstance(update, dict) else []
                    for m in msgs:
                        for tc in getattr(m, "tool_calls", None) or []:
                            yield _sse("tool", {"name": tc["name"]})
                        if isinstance(m, AIMessage) and _text(m.content) and not emitted_token:
                            # fallback for non-streaming models: send the whole answer
                            yield _sse("final", {"text": _text(m.content)})
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream")
