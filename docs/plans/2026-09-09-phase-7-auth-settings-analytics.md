# Phase 7 — Auth, Settings & Richer Analytics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add (1) **layered email+password sign-in** (the app stays browsable in demo mode without login; signing in adds a per-user account + saved settings — keeps the public/Yahoo-review URL open), (2) a **Settings page** (account, theme, per-user league format, "Connect Yahoo — coming soon"), (3) a **Weekdays analysis** dashboard card (which days of the week your roster is thin on games → stream a waiver player), and (4) a **Trade-history demo shell** (fabricated sample trades with per-player before/after, expandable per player — real Yahoo transactions + game-logs swap in on approval).

**Architecture:** Auth is optional/additive: a `users` table + bcrypt passwords + a signed **JWT in an httpOnly cookie**; endpoints read the current user if present but never require it (demo stays open). Per-user **league format** lives on the user row and is threaded into the league-settings resolution (demo mode derives settings per format, bypassing the Postgres cache). Weekday coverage and trade history are pure functions over a per-day schedule fixture and a fabricated trades fixture. Frontend gains an auth context, a login/register screen, a Settings view, and two new dashboard sections. Cross-domain cookies (Vercel↔Railway) use `SameSite=None; Secure` with CORS `allow_credentials=True`.

**Tech Stack:** existing + `passlib[bcrypt]` (hashing), `pyjwt` (tokens). No new frontend deps.

**New env:** `SECRET_KEY` (JWT signing) — set on Railway; defaults to a dev value locally.

---

## Task A1: Auth backend (users, JWT cookie, /auth endpoints)

**Files:** `uv add "passlib[bcrypt]" pyjwt`; Modify `db/schema.sql`, `config.py`, `api.py`; Create `src/fantasy_gm/users.py`; Test `tests/test_users.py`, `tests/test_api.py`

- [ ] **Step 1: Add the `users` table to `db/schema.sql`**

```sql
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    email         TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    league_format TEXT NOT NULL DEFAULT 'category',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 2: Add `secret_key` to `config.py` Settings**

```python
    secret_key: str = "dev-secret-change-me"   # JWT signing; set SECRET_KEY in prod
```

- [ ] **Step 3: Write the failing test** `tests/test_users.py`

```python
from fantasy_gm import users

def test_hash_and_verify():
    h = users.hash_password("hunter2")
    assert h != "hunter2"
    assert users.verify_password("hunter2", h) is True
    assert users.verify_password("wrong", h) is False

def test_token_roundtrip():
    tok = users.make_token(42)
    assert users.decode_token(tok) == 42
    assert users.decode_token("garbage") is None

def test_create_and_fetch_user(db):
    u = users.create_user("a@b.com", "pw")
    assert u["email"] == "a@b.com"
    assert users.get_user_by_email("a@b.com")["id"] == u["id"]
    assert users.get_user_by_id(u["id"])["email"] == "a@b.com"
```

- [ ] **Step 4: Run it, confirm fail**; **Step 5: Implement `src/fantasy_gm/users.py`**

```python
import datetime as dt

import jwt
from passlib.context import CryptContext

from fantasy_gm.config import get_settings
from fantasy_gm.db import execute, fetch_one

_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_ALG = "HS256"


def hash_password(pw: str) -> str:
    return _pwd.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return _pwd.verify(pw, hashed)


def make_token(user_id: int) -> str:
    payload = {"sub": str(user_id),
               "exp": dt.datetime.now(dt.UTC) + dt.timedelta(days=30)}
    return jwt.encode(payload, get_settings().secret_key, algorithm=_ALG)


def decode_token(token: str) -> int | None:
    try:
        p = jwt.decode(token, get_settings().secret_key, algorithms=[_ALG])
        return int(p["sub"])
    except Exception:
        return None


def create_user(email: str, password: str) -> dict:
    execute("INSERT INTO users (email, password_hash) VALUES (%s, %s)",
            (email.lower(), hash_password(password)))
    return get_user_by_email(email)


def get_user_by_email(email: str) -> dict | None:
    return fetch_one("SELECT id, email, password_hash, league_format "
                     "FROM users WHERE email=%s", (email.lower(),))


def get_user_by_id(uid: int) -> dict | None:
    return fetch_one("SELECT id, email, password_hash, league_format "
                     "FROM users WHERE id=%s", (uid,))
```

- [ ] **Step 6: Run it, confirm pass** (the `db` fixture already truncates tables — add `users` to its TRUNCATE list in `tests/conftest.py`).

- [ ] **Step 7: Add auth endpoints + cookie plumbing to `api.py`**

```python
from fastapi import Response
from fantasy_gm import users

app.add_middleware(...)  # EXISTING CORS — add allow_credentials=True to it

_COOKIE = "session"

class Credentials(BaseModel):
    email: str
    password: str

def _set_session(resp: Response, user_id: int) -> None:
    resp.set_cookie(_COOKIE, users.make_token(user_id), httponly=True,
                    secure=True, samesite="none", max_age=30 * 24 * 3600, path="/")

def _current_user(request: Request) -> dict | None:
    tok = request.cookies.get(_COOKIE)
    uid = users.decode_token(tok) if tok else None
    return users.get_user_by_id(uid) if uid else None

@app.post("/auth/register")
def register(creds: Credentials, response: Response) -> dict:
    if users.get_user_by_email(creds.email):
        raise HTTPException(409, "Email already registered.")
    u = users.create_user(creds.email, creds.password)
    _set_session(response, u["id"])
    return {"email": u["email"], "league_format": u["league_format"]}

@app.post("/auth/login")
def login(creds: Credentials, response: Response) -> dict:
    u = users.get_user_by_email(creds.email)
    if not u or not users.verify_password(creds.password, u["password_hash"]):
        raise HTTPException(401, "Invalid email or password.")
    _set_session(response, u["id"])
    return {"email": u["email"], "league_format": u["league_format"]}

@app.post("/auth/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(_COOKIE, path="/")
    return {"ok": True}

@app.get("/auth/me")
def me(request: Request) -> dict:
    u = _current_user(request)
    if not u:
        raise HTTPException(401, "Not signed in.")
    return {"email": u["email"], "league_format": u["league_format"]}
```

IMPORTANT: update the existing `app.add_middleware(CORSMiddleware, ...)` call to include `allow_credentials=True` (keep the existing `allow_origins` + `allow_origin_regex`; credentials are incompatible with `allow_origins=["*"]`, but we use explicit origins + regex, so this is fine).

- [ ] **Step 8: Add endpoint tests** to `tests/test_api.py`

```python
def test_auth_register_login_me(db):
    from fantasy_gm import api
    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    r = c.post("/auth/register", json={"email": "x@y.com", "password": "pw"})
    assert r.status_code == 200 and r.json()["email"] == "x@y.com"
    assert c.get("/auth/me").json()["email"] == "x@y.com"   # cookie persists in the client
    c.post("/auth/logout")
    assert c.get("/auth/me").status_code == 401
    bad = c.post("/auth/login", json={"email": "x@y.com", "password": "nope"})
    assert bad.status_code == 401
```

- [ ] **Step 9: Run all tests green; ruff clean; Commit**

```bash
git add pyproject.toml uv.lock db/schema.sql src/fantasy_gm/config.py src/fantasy_gm/users.py src/fantasy_gm/api.py tests/test_users.py tests/test_api.py tests/conftest.py
git commit -m "feat: email+password auth (users, bcrypt, JWT cookie, /auth endpoints)"
```

Note: the deployed Postgres already has tables (CREATE IF NOT EXISTS won't add `users` to an existing DB via the app's simple runner) — the container reseeds on boot and `run_migrations.py` runs `CREATE TABLE IF NOT EXISTS users`, which DOES create the new table on the next deploy. No manual migration needed.

---

## Task A2: Per-user league format (Settings backend)

**Files:** Modify `src/fantasy_gm/demo.py`, `src/fantasy_gm/api.py`; Test `tests/test_api.py`

- [ ] **Step 1: Make `demo.demo_league_settings` accept an explicit format**

```python
def demo_league_settings(fmt: str | None = None) -> LeagueSettings:
    fmt = fmt or get_settings().demo_league_format
    fixture = ("league_settings_points.json" if fmt == "points"
               else "league_settings.json")
    return client.parse_league_settings(_load(fixture))
```

- [ ] **Step 2: Add the failing test** — a signed-in user with `league_format='points'` gets a points dashboard

```python
def test_dashboard_uses_user_format(db, monkeypatch):
    from fantasy_gm import api, users
    from fantasy_gm.schemas import Player, Team
    users.create_user("p@p.com", "pw")
    from fantasy_gm.db import execute
    execute("UPDATE users SET league_format='points' WHERE email='p@p.com'")
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="1", name="A", nba_team="LAL", stats={"PTS": 20})])])
    monkeypatch.setattr(api, "_free_agents", lambda: [])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})
    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    c.post("/auth/login", json={"email": "p@p.com", "password": "pw"})
    body = c.get("/analytics/dashboard").json()
    assert body["format"] == "points"
```

- [ ] **Step 3: Thread the per-user format into the league-settings resolution** in `api.py`

Add:
```python
def _format_for(request: Request) -> str:
    u = _current_user(request)
    if u:
        return u["league_format"]
    return get_settings().demo_league_format

def _league_for(fmt: str) -> LeagueSettings:
    # In demo mode derive settings for the requested format directly (bypasses the
    # single-league Postgres cache, which can't hold two formats at once).
    if get_settings().demo_mode:
        from fantasy_gm import demo
        return demo.demo_league_settings(fmt)
    return _load_league()
```

Then give `dashboard()`, `trade_analyze()`, `league_info()` a `request: Request` param and replace `_load_league()` / `_league_info()` with `_league_for(_format_for(request))`.

- [ ] **Step 4: Add `PATCH /settings`** (requires auth) to update `league_format`

```python
class SettingsPatch(BaseModel):
    league_format: str

@app.patch("/settings")
def update_settings(patch: SettingsPatch, request: Request) -> dict:
    u = _current_user(request)
    if not u:
        raise HTTPException(401, "Not signed in.")
    if patch.league_format not in {"category", "points"}:
        raise HTTPException(400, "Invalid format.")
    from fantasy_gm.db import execute
    execute("UPDATE users SET league_format=%s WHERE id=%s",
            (patch.league_format, u["id"]))
    return {"league_format": patch.league_format}
```

- [ ] **Step 5: Run tests green; Commit**

```bash
git add src/fantasy_gm/demo.py src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat: per-user league format (settings) threaded into endpoints"
```

---

## Task C1: Weekdays analysis (per-day schedule)

**Files:** Modify `scripts/build_real_league.py` (emit a per-weekday schedule) + create `demo_data/schedule_by_day.json`; Modify `src/fantasy_gm/analytics.py`, `src/fantasy_gm/api.py`; Test `tests/test_analytics.py`, `tests/test_api.py`

- [ ] **Step 1: Create `demo_data/schedule_by_day.json`** — weekday → NBA teams playing that day. Generate from balldontlie for one real week (add a function to `build_real_league.py` that buckets that week's games by weekday abbrev Mon..Sun), or hand-author a representative week. Shape:

```json
{"Mon": ["LAL","BOS","DEN", "..."], "Tue": ["..."], "Wed": [], "Thu": ["..."],
 "Fri": ["..."], "Sat": ["..."], "Sun": ["..."]}
```

- [ ] **Step 2: Write the failing test** (append to `tests/test_analytics.py`)

```python
from fantasy_gm.analytics import weekday_coverage
from fantasy_gm.schemas import Player

def test_weekday_coverage_flags_thin_days():
    roster = [Player(player_id="1", name="A", nba_team="LAL"),
              Player(player_id="2", name="B", nba_team="BOS")]
    day_teams = {"Mon": ["LAL", "BOS"], "Tue": ["LAL"], "Wed": []}
    cov = weekday_coverage(roster, day_teams, weak_threshold=2)
    by_day = {c["day"]: c for c in cov}
    assert by_day["Mon"]["count"] == 2 and by_day["Mon"]["weak"] is False
    assert by_day["Tue"]["count"] == 1 and by_day["Tue"]["weak"] is True
    assert by_day["Wed"]["count"] == 0 and by_day["Wed"]["weak"] is True
```

- [ ] **Step 3: Run it, confirm fail**; **Step 4: Implement in `analytics.py`**

```python
_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

def weekday_coverage(roster, day_teams: dict[str, list[str]],
                     weak_threshold: int = 4) -> list[dict]:
    """Per weekday: how many of my players have a game; flag thin days to stream."""
    out = []
    for d in _DAYS:
        teams = set(day_teams.get(d, []))
        count = sum(1 for p in roster if p.nba_team in teams)
        out.append({"day": d, "count": count,
                    "weak": len(teams) > 0 and count <= weak_threshold})
    return out
```

- [ ] **Step 5: Add `GET /analytics/weekdays`** to `api.py`

```python
import json
from pathlib import Path
_DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"

@app.get("/analytics/weekdays")
def weekdays() -> dict:
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    day_teams = json.loads((_DEMO_DIR / "schedule_by_day.json").read_text())
    return {"days": analytics.weekday_coverage(mine.players, day_teams)}
```

- [ ] **Step 6: Add a light endpoint test; run green; Commit**

```bash
git add scripts/build_real_league.py demo_data/schedule_by_day.json src/fantasy_gm/analytics.py src/fantasy_gm/api.py tests/test_analytics.py tests/test_api.py
git commit -m "feat: weekday coverage analytics (thin-day streaming targets)"
```

---

## Task D1: Trade-history demo shell

**Files:** Create `demo_data/trade_history.json` (fabricated, real demo players); Create `src/fantasy_gm/trades_history.py`; Modify `src/fantasy_gm/api.py`; Test `tests/test_trades_history.py`

- [ ] **Step 1: Create `demo_data/trade_history.json`** — 2–3 fabricated trades over players that exist in `demo_data/league.json`, e.g.:

```json
[
  {"date": "2025-12-14", "with_team": "Team 4",
   "gave": ["<player_id>"], "got": ["<player_id>"]}
]
```

- [ ] **Step 2: Write the failing test** `tests/test_trades_history.py`

```python
from fantasy_gm.trades_history import build_history
from fantasy_gm.schemas import Player

def _p(pid, **s): return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=s)

def test_build_history_before_after():
    by_id = {"1": _p("1", PTS=20.0), "2": _p("2", PTS=10.0)}
    trades = [{"date": "2025-12-14", "with_team": "Team 4", "gave": ["1"], "got": ["2"]}]
    hist = build_history(trades, by_id)
    t = hist[0]
    assert t["with_team"] == "Team 4"
    p = t["got"][0]
    assert p["name"] == "P2"
    assert "before" in p and "after" in p     # synthetic before/after stat maps
```

- [ ] **Step 3: Run it, confirm fail**; **Step 4: Implement `src/fantasy_gm/trades_history.py`**

```python
def _sides(ids: list[str], by_id: dict) -> list[dict]:
    out = []
    for i in ids:
        p = by_id.get(i)
        if not p:
            continue
        before = dict(p.stats)                                   # season baseline
        after = {k: round(v * 1.08, 2) for k, v in p.stats.items()}  # synthetic since-trade
        out.append({"player_id": p.player_id, "name": p.name, "nba_team": p.nba_team,
                    "before": before, "after": after})
    return out


def build_history(trades: list[dict], by_id: dict) -> list[dict]:
    """Fabricated trade history with per-player before/after stats (demo shell).
    On Yahoo approval, replace `trades` with real transactions and `after` with
    real post-trade game-log averages."""
    return [{"date": t["date"], "with_team": t["with_team"],
             "gave": _sides(t.get("gave", []), by_id),
             "got": _sides(t.get("got", []), by_id)} for t in trades]
```

- [ ] **Step 5: Add `GET /trades/history`** to `api.py`

```python
from fantasy_gm import trades_history

@app.get("/trades/history")
def trade_history() -> dict:
    by_id = {p.player_id: p for t in _all_teams() for p in t.players}
    by_id.update({p.player_id: p for p in _free_agents()})
    trades = json.loads((_DEMO_DIR / "trade_history.json").read_text())
    return {"trades": trades_history.build_history(trades, by_id)}
```

- [ ] **Step 6: Run green; Commit**

```bash
git add demo_data/trade_history.json src/fantasy_gm/trades_history.py src/fantasy_gm/api.py tests/test_trades_history.py
git commit -m "feat: trade-history demo shell (before/after per player)"
```

---

## Task F1: Auth on the frontend (context + login + header)

**Files:** Create `frontend/src/state/auth.tsx` (AuthProvider + useAuth), `frontend/src/components/AuthModal.tsx`; Modify `frontend/src/lib/api.ts` (auth calls, `credentials: "include"` on ALL fetches), `frontend/src/components/Header.tsx`, `frontend/src/App.tsx`; Test `frontend/src/__tests__/auth.test.tsx`

- [ ] **Step 1:** In `lib/api.ts`, add `credentials: "include"` to every `fetch(...)` (so the session cookie is sent), and add `register/login/logout/me` + `updateSettings(league_format)` calls.
- [ ] **Step 2:** `state/auth.tsx` — an `AuthProvider` that calls `/auth/me` on mount, exposes `{ user, login, register, logout, refresh }`. `user` is `{email, league_format} | null`.
- [ ] **Step 3:** `AuthModal.tsx` — a modal with email/password, toggling Login ↔ Register, error display; calls the context.
- [ ] **Step 4:** `Header.tsx` — when signed out show a "Sign in" button (opens the modal); when signed in show the email + a menu with "Settings" and "Sign out". Add a Settings entry (gear).
- [ ] **Step 5:** Wrap `<App/>` in `<AuthProvider>`. Test: the modal logs in (mock `api.login`) and the header shows the email. `npm test` + `npm run build` green. Commit `feat(ui): auth context, login/register modal, header account menu`.

---

## Task F2: Settings view

**Files:** Create `frontend/src/views/SettingsView.tsx`; Modify `frontend/src/App.tsx` (route `/settings`), `frontend/src/components/Nav.tsx` or Header (entry); Test `frontend/src/__tests__/settings.test.tsx`

- [ ] Settings sections: **Account** (email, Sign out) — only if signed in, else a "Sign in to save settings" prompt; **Appearance** (light/dark toggle, reuse `useTheme`); **League** (Category ↔ Points segmented control → calls `updateSettings`, refreshes auth/user, and re-fetches the dashboard); **Connect Yahoo** (disabled "Coming soon" row explaining real-league connection lands on API approval). Loading/error states. Test renders the sections and the format toggle calls `updateSettings`. Commit `feat(ui): settings view (account, theme, league format, Yahoo placeholder)`.

---

## Task F3: Weekdays card (dashboard)

**Files:** Create `frontend/src/components/charts/WeekdayBars.tsx`; Modify `frontend/src/views/DashboardView.tsx`, `frontend/src/lib/api.ts` (`getWeekdays`); Test `frontend/src/__tests__/dashboard.test.tsx`

- [ ] A card "Games this week by day" — 7 columns (Mon–Sun), each a bar of your player-count that day, **weak days highlighted in the danger/coral color with a "stream" tag**, plus a one-line hint ("Thin on Wed & Sun — grab waiver players who play those days"). Fetch `getWeekdays()` on the dashboard; render below the existing cards. Table fallback for a11y. Commit `feat(ui): weekday coverage card on the dashboard`.

---

## Task F4: Trade History view

**Files:** Create `frontend/src/views/TradeHistoryView.tsx`, `frontend/src/components/TradePlayerRow.tsx`; Modify `frontend/src/App.tsx` (route + nav), `frontend/src/lib/api.ts` (`getTradeHistory`); Test `frontend/src/__tests__/tradehistory.test.tsx`

- [ ] A "Trade History" section (its own tab, or a section under Trade): list each trade (date, with team, gave/got player pills). **Clicking a player expands a dropdown** showing a compact before/after stat comparison (before = season, after = since-trade, with up/down deltas colored green/red — never color alone). A small note: "Demo trades — real history connects with Yahoo." Test: renders a trade and expanding a player shows before/after. Commit `feat(ui): trade history view with per-player before/after dropdown`.

---

## Task F5: Live check + QC

- [ ] Local: `PYTHONPATH=src uv run uvicorn ...` + `npm run dev`. Register/login; toggle format in Settings → dashboard flips; weekday card shows thin days; trade history expands a player. Sign out → demo still browsable.
- [ ] Run `design:design-critique` + `design:accessibility-review` on the new views (auth modal, settings, weekday card, trade history); apply high-value fixes. Commit `fix(ui): phase-7 design + a11y review`.

---

## Runbook: deploy
- Railway → backend → Variables → add **`SECRET_KEY`** = a long random string. Redeploy (the boot migration creates the `users` table via `run_migrations.py`).
- Vercel auto-deploys the frontend on push.
- Verify on the live URL: sign in, settings, weekday card, trade history; and that logged-out demo still works (Yahoo review URL stays open).

## Phase 7 Done — Definition of Done
- [ ] Backend `uv run pytest -v` green (users, auth endpoints, per-user format, weekday, trade history).
- [ ] Frontend `npm test` + `npm run build` green.
- [ ] Live: register/login/logout works; settings persist per user; format toggle flips the dashboard; weekday card + trade history render; logged-out demo still works.
- [ ] design-critique + accessibility-review applied; `SECRET_KEY` set on Railway.

## Deferred (Yahoo-approval phase)
- Per-user real Yahoo connection ("Connect Yahoo" → OAuth, per-user token + league/team selection) replacing shared demo data.
- Real trade history (Yahoo transactions) + real before/after from nba_api game logs, swapped into the D1 shell.
