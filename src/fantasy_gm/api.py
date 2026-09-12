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


_COOKIE = "session"


_LOCAL_HOSTS = {"testserver", "localhost", "127.0.0.1"}


def _set_session(response: Response, request: Request, user_id: int) -> None:
    # SameSite=None needs Secure on real cross-site hosts (Vercel↔Railway). Over
    # plain http (TestClient's "testserver", local dev) a Secure cookie would be
    # dropped, so scope Secure to real hostnames.
    secure = (request.url.hostname or "") not in _LOCAL_HOSTS
    response.set_cookie(_COOKIE, users.make_token(user_id), httponly=True,
                        secure=secure, samesite="none",
                        max_age=30 * 24 * 3600, path="/")


def _current_user(request: Request) -> dict | None:
    tok = request.cookies.get(_COOKIE)
    uid = users.decode_token(tok) if tok else None
    return users.get_user_by_id(uid) if uid else None


def _load_league() -> LeagueSettings:
    return get_league_settings(LEAGUE_KEY)


def _league_for(request: Request) -> LeagueSettings:
    """League settings for this request. A signed-in user in demo mode gets their
    saved format's fixture (the single-league Postgres cache can't hold two formats
    at once); otherwise fall back to the shared league (patchable in tests / real
    Yahoo league live)."""
    u = _current_user(request)
    if u and get_settings().demo_mode:
        from fantasy_gm import demo
        return demo.demo_league_settings(u["league_format"])
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
def logout(response: Response) -> dict:
    response.delete_cookie(_COOKIE, path="/")
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
    if u and get_settings().demo_mode:
        from fantasy_gm import demo
        s = demo.demo_league_settings(u["league_format"])
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
    day_teams = json.loads((_DEMO_DIR / "schedule_by_day.json").read_text())
    out = {"format": league.format,
           "weekdays": analytics.weekday_coverage(mine.players, day_teams)}
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
    return out


@app.get("/analytics/league")
def analytics_league(request: Request) -> dict:
    league = _league_for(request)
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    fas = _free_agents()
    roster_trends = _trends_for([p.player_id for p in mine.players])
    fa_trends = _trends_for([p.player_id for p in fas])
    out = {"format": league.format,
           "teams": [t.model_dump() for t in teams],
           "my_team_key": MY_TEAM_KEY,
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
