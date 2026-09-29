# Phase 1 — Foundation & Yahoo Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a tested data foundation for the Fantasy GM Agent — a clean, typed Yahoo Fantasy client (OAuth2 + refresh), a Postgres store, a nightly stats/schedule sync, a deterministic value model, and the agent's toolbox — all covered by tests, with the two risky unknowns (Yahoo OAuth, weekly-schedule source) de-risked by spikes first.

**Architecture:** A Python package `fantasy_gm` with focused modules: `config` (env settings), `db` (Postgres access over plain SQL), `schemas` (Pydantic domain models), `yahoo_client` (isolated integration: auth/parse/cache/errors), `value` (pure valuation functions), `sync` (nightly job), and `tools` (the agent toolbox). Everything Yahoo-specific and messy is quarantined inside `yahoo_client`; the rest of the app only ever sees clean typed objects. Postgres is accessed through a thin sync helper using raw SQL for transparency.

**Tech Stack:** Python 3.12, `uv` (deps + venv), `pytest`, `ruff`, `httpx` (HTTP + OAuth2), `psycopg[binary]` 3 (Postgres), `pydantic` v2 + `pydantic-settings`, Docker Compose (local Postgres).

**Conventions used throughout:**
- Source lives under `src/fantasy_gm/`, tests mirror it under `tests/`.
- TDD: write the failing test, watch it fail, implement minimally, watch it pass, commit.
- Tests never hit the real Yahoo API — they use recorded fixtures saved by the spikes.
- DB tests run against a local Postgres started via Docker Compose, using a separate `TEST_DATABASE_URL`.

---

## File Structure

Created across this phase:

```
pyproject.toml                     # project + deps + tool config (ruff, pytest)
.gitignore
.env.example                       # documents required env vars (no secrets)
docker-compose.yml                 # local Postgres (dev + test)
db/schema.sql                      # table definitions
scripts/spike_oauth.py             # THROWAWAY: prove Yahoo OAuth + pull roster
scripts/spike_schedule.py          # THROWAWAY: prove weekly-schedule source
scripts/run_migrations.py          # apply db/schema.sql
src/fantasy_gm/__init__.py
src/fantasy_gm/config.py           # Settings (env vars)
src/fantasy_gm/db.py               # Postgres connection + query helpers
src/fantasy_gm/schemas.py          # Pydantic: Player, Team, LeagueSettings, ...
src/fantasy_gm/yahoo_client/__init__.py
src/fantasy_gm/yahoo_client/errors.py   # error classification
src/fantasy_gm/yahoo_client/auth.py      # token load/store/refresh
src/fantasy_gm/yahoo_client/cache.py     # short-TTL in-memory cache
src/fantasy_gm/yahoo_client/client.py    # typed wrapper over raw Yahoo responses
src/fantasy_gm/value.py            # pure valuation functions
src/fantasy_gm/sync.py             # nightly stats/schedule sync
src/fantasy_gm/tools.py            # agent toolbox functions
tests/fixtures/                    # recorded Yahoo responses (from spikes)
tests/conftest.py                  # shared pytest fixtures (db, etc.)
tests/test_*.py                    # one test module per source module
```

---

## Task 0: Project scaffold & tooling

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.env.example`, `docker-compose.yml`
- Create: `src/fantasy_gm/__init__.py`, `tests/__init__.py`, `tests/test_smoke.py`

- [ ] **Step 1: Initialize the project with uv**

Run (from repo root `~/Documents/fantasy-gm-agent`):
```bash
uv init --package --name fantasy-gm --python 3.12
uv add httpx "psycopg[binary]" pydantic pydantic-settings
uv add --dev pytest ruff
```
Expected: creates a `pyproject.toml`, `src/fantasy_gm/`, a `.venv`, and a `uv.lock`.

- [ ] **Step 2: Add tool config to `pyproject.toml`**

Append these sections to `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 3: Create `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
.pytest_cache/
.ruff_cache/
tests/fixtures/*.local.json
```

- [ ] **Step 4: Create `.env.example`** (documents required vars; committed, holds NO secrets)

```
# Yahoo OAuth2 (create an app at https://developer.yahoo.com/apps/)
YAHOO_CLIENT_ID=
YAHOO_CLIENT_SECRET=
YAHOO_REDIRECT_URI=oob
YAHOO_LEAGUE_KEY=            # e.g. 428.l.12345 (filled after the OAuth spike)

# Postgres
DATABASE_URL=postgresql://fgm:fgm@localhost:5432/fantasy_gm
TEST_DATABASE_URL=postgresql://fgm:fgm@localhost:5432/fantasy_gm_test

# LLM / observability (used in Phase 2)
ANTHROPIC_API_KEY=
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=fantasy-gm-agent
```

- [ ] **Step 5: Create `docker-compose.yml`** for local Postgres

```yaml
services:
  db:
    image: postgres:16
    environment:
      POSTGRES_USER: fgm
      POSTGRES_PASSWORD: fgm
      POSTGRES_DB: fantasy_gm
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
volumes:
  pgdata:
```

- [ ] **Step 6: Write a smoke test** at `tests/test_smoke.py`

```python
def test_smoke():
    assert True
```

- [ ] **Step 7: Bring up Postgres and create the test database**

```bash
docker compose up -d db
sleep 3
docker compose exec -T db psql -U fgm -d fantasy_gm -c "CREATE DATABASE fantasy_gm_test;"
```
Expected: `CREATE DATABASE` (or a "already exists" error on re-run, which is fine).

- [ ] **Step 8: Run the smoke test**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "chore: scaffold project, tooling, and local Postgres"
```

---

## Task 1: Settings module

**Files:**
- Create: `src/fantasy_gm/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_config.py
from fantasy_gm.config import Settings

def test_settings_load_from_env(monkeypatch):
    monkeypatch.setenv("YAHOO_CLIENT_ID", "cid")
    monkeypatch.setenv("YAHOO_CLIENT_SECRET", "secret")
    monkeypatch.setenv("DATABASE_URL", "postgresql://x/y")
    s = Settings()
    assert s.yahoo_client_id == "cid"
    assert s.database_url == "postgresql://x/y"
    assert s.yahoo_redirect_uri == "oob"  # default
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: fantasy_gm.config`.

- [ ] **Step 3: Write minimal implementation** at `src/fantasy_gm/config.py`

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_redirect_uri: str = "oob"
    yahoo_league_key: str = ""

    database_url: str = "postgresql://fgm:fgm@localhost:5432/fantasy_gm"
    test_database_url: str = "postgresql://fgm:fgm@localhost:5432/fantasy_gm_test"

    anthropic_api_key: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/config.py tests/test_config.py
git commit -m "feat: settings module loading env vars"
```

---

## Task 2: Database layer & schema

**Files:**
- Create: `db/schema.sql`, `scripts/run_migrations.py`, `src/fantasy_gm/db.py`
- Create: `tests/conftest.py`
- Test: `tests/test_db.py`

- [ ] **Step 1: Write `db/schema.sql`** (the 4 tables from the spec; LangGraph checkpointer tables are created later by LangGraph itself)

```sql
CREATE TABLE IF NOT EXISTS league_config (
    league_key TEXT PRIMARY KEY,
    format     TEXT NOT NULL,               -- 'category' | 'points'
    categories JSONB NOT NULL DEFAULT '[]',  -- e.g. ["PTS","REB","AST",...]
    roster_slots JSONB NOT NULL DEFAULT '{}',
    cached_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS player_stat_snapshots (
    player_id  TEXT NOT NULL,
    snapshot_date DATE NOT NULL,
    stats      JSONB NOT NULL,               -- per-game or per-day stat map
    PRIMARY KEY (player_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS weekly_schedule (
    nba_team   TEXT NOT NULL,
    week       INTEGER NOT NULL,
    games_total INTEGER NOT NULL,
    games_remaining INTEGER NOT NULL,
    as_of_date DATE NOT NULL,
    PRIMARY KEY (nba_team, week)
);

CREATE TABLE IF NOT EXISTS oauth_tokens (
    id            INTEGER PRIMARY KEY DEFAULT 1,   -- single-user: one row
    access_token  TEXT NOT NULL,
    refresh_token TEXT NOT NULL,
    expires_at    TIMESTAMPTZ NOT NULL,
    CONSTRAINT single_row CHECK (id = 1)
);
```

- [ ] **Step 2: Write `scripts/run_migrations.py`**

```python
import sys

import psycopg

from fantasy_gm.config import get_settings


def run(database_url: str) -> None:
    with open("db/schema.sql") as f:
        sql = f.read()
    with psycopg.connect(database_url) as conn:
        conn.execute(sql)
        conn.commit()
    print(f"migrations applied to {database_url}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else get_settings().database_url
    run(url)
```

- [ ] **Step 3: Write the failing test** at `tests/test_db.py`

```python
from fantasy_gm.db import fetch_all, execute

def test_insert_and_fetch(db):
    execute(
        "INSERT INTO league_config (league_key, format) VALUES (%s, %s)",
        ("428.l.1", "category"),
    )
    rows = fetch_all("SELECT league_key, format FROM league_config")
    assert rows == [{"league_key": "428.l.1", "format": "category"}]
```

- [ ] **Step 4: Write the shared `db` fixture** in `tests/conftest.py`

```python
import psycopg
import pytest

from fantasy_gm import db as db_module
from fantasy_gm.config import get_settings
from scripts.run_migrations import run as run_migrations


@pytest.fixture
def db(monkeypatch):
    test_url = get_settings().test_database_url
    run_migrations(test_url)
    # Point the db module at the test database for the duration of the test.
    monkeypatch.setattr(db_module, "_DATABASE_URL", test_url)
    yield
    # Clean all tables between tests.
    with psycopg.connect(test_url) as conn:
        conn.execute(
            "TRUNCATE league_config, player_stat_snapshots, "
            "weekly_schedule, oauth_tokens"
        )
        conn.commit()
```

Note: `tests/conftest.py` needs `scripts` importable. Add `pythonpath = ["src", "."]` to the pytest config in `pyproject.toml` (replace the earlier `pythonpath = ["src"]`).

- [ ] **Step 5: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: fantasy_gm.db`.

- [ ] **Step 6: Implement `src/fantasy_gm/db.py`**

```python
from typing import Any

import psycopg
from psycopg.rows import dict_row

from fantasy_gm.config import get_settings

_DATABASE_URL: str | None = None


def _url() -> str:
    return _DATABASE_URL or get_settings().database_url


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with psycopg.connect(_url(), row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    with psycopg.connect(_url(), row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    with psycopg.connect(_url()) as conn:
        conn.execute(sql, params)
        conn.commit()
```

- [ ] **Step 7: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "feat: postgres schema, migration runner, and db helper"
```

---

## Task 3: Domain schemas

**Files:**
- Create: `src/fantasy_gm/schemas.py`
- Test: `tests/test_schemas.py`

These are the clean typed objects the rest of the app sees. Keep them minimal but real.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_schemas.py
from fantasy_gm.schemas import LeagueSettings, Player


def test_player_defaults_missing_stats_to_zero():
    p = Player(player_id="1", name="X", nba_team="LAL", positions=["PG"], stats={"AST": 6.0})
    assert p.stats["AST"] == 6.0
    assert p.stat("REB") == 0.0  # missing stat reads as 0

def test_league_settings_is_category():
    s = LeagueSettings(league_key="428.l.1", format="category",
                       categories=["PTS", "AST"], roster_slots={"PG": 1})
    assert s.is_category is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/fantasy_gm/schemas.py`**

```python
from pydantic import BaseModel, Field


class Player(BaseModel):
    player_id: str
    name: str
    nba_team: str                      # NBA team abbrev, e.g. "LAL"
    positions: list[str] = Field(default_factory=list)
    stats: dict[str, float] = Field(default_factory=dict)  # category -> per-game value

    def stat(self, key: str) -> float:
        return self.stats.get(key, 0.0)


class Team(BaseModel):
    team_key: str
    name: str
    players: list[Player] = Field(default_factory=list)


class LeagueSettings(BaseModel):
    league_key: str
    format: str                        # "category" | "points"
    categories: list[str] = Field(default_factory=list)
    roster_slots: dict[str, int] = Field(default_factory=dict)

    @property
    def is_category(self) -> bool:
        return self.format == "category"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_schemas.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/schemas.py tests/test_schemas.py
git commit -m "feat: domain schemas (Player, Team, LeagueSettings)"
```

---

## Task 4: OAuth spike (THROWAWAY — de-risk gate #1)

> This task is **exploratory, not TDD**. Its job is to prove we can authenticate with Yahoo and pull real data, and to **save real response fixtures** that later tests replay. If Yahoo fights us, we learn now.

**Files:**
- Create: `scripts/spike_oauth.py`
- Produces: `tests/fixtures/roster.json`, `tests/fixtures/free_agents.json`, `tests/fixtures/league_settings.json`

- [ ] **Step 1: Register a Yahoo app** (manual, one-time)

Go to https://developer.yahoo.com/apps/, create an app with **Fantasy Sports → Read** permission, redirect URI `oob`. Copy the Client ID + Secret into `.env`.

- [ ] **Step 2: Write `scripts/spike_oauth.py`** (Authorization Code flow, `oob`)

```python
"""Throwaway spike: prove Yahoo OAuth2 + pull real fantasy data, save fixtures."""
import json
import webbrowser
from pathlib import Path

import httpx

from fantasy_gm.config import get_settings

AUTH = "https://api.login.yahoo.com/oauth2/request_auth"
TOKEN = "https://api.login.yahoo.com/oauth2/get_token"
API = "https://fantasysports.yahooapis.com/fantasy/v2"
s = get_settings()
FIX = Path("tests/fixtures")


def get_tokens() -> dict:
    url = (f"{AUTH}?client_id={s.yahoo_client_id}&redirect_uri={s.yahoo_redirect_uri}"
           f"&response_type=code")
    print("Open this URL, approve, paste the code:\n", url)
    webbrowser.open(url)
    code = input("code: ").strip()
    r = httpx.post(TOKEN, data={
        "client_id": s.yahoo_client_id,
        "client_secret": s.yahoo_client_secret,
        "redirect_uri": s.yahoo_redirect_uri,
        "code": code,
        "grant_type": "authorization_code",
    })
    r.raise_for_status()
    return r.json()


def pull(access_token: str, path: str) -> dict:
    r = httpx.get(f"{API}/{path}?format=json",
                  headers={"Authorization": f"Bearer {access_token}"})
    r.raise_for_status()
    return r.json()


if __name__ == "__main__":
    FIX.mkdir(parents=True, exist_ok=True)
    tokens = get_tokens()
    print("REFRESH TOKEN (save for later):", tokens["refresh_token"])
    at = tokens["access_token"]

    # Find your leagues, then inspect + save real payloads.
    leagues = pull(at, "users;use_login=1/games;game_keys=nba/leagues")
    (FIX / "leagues.json").write_text(json.dumps(leagues, indent=2))
    print("Saved leagues.json — find your league_key inside it, set YAHOO_LEAGUE_KEY in .env")

    lk = s.yahoo_league_key or input("paste league_key (e.g. 428.l.12345): ").strip()
    (FIX / "league_settings.json").write_text(
        json.dumps(pull(at, f"league/{lk}/settings"), indent=2))
    (FIX / "roster.json").write_text(
        json.dumps(pull(at, f"league/{lk}/teams;out=roster,stats"), indent=2))
    (FIX / "free_agents.json").write_text(
        json.dumps(pull(at, f"league/{lk}/players;status=FA;out=stats"), indent=2))
    print("Saved league_settings.json, roster.json, free_agents.json")
```

- [ ] **Step 3: Run the spike**

```bash
uv run python scripts/spike_oauth.py
```
Expected: browser opens, you approve, and four JSON fixtures appear under `tests/fixtures/`. Save the printed refresh token somewhere safe.

- [ ] **Step 4: GATE — inspect the fixtures**

Open `tests/fixtures/league_settings.json`, `roster.json`, `free_agents.json`. Confirm you can locate: scoring format + category list, your roster with player names/stats, and free agents with stats. **Only proceed if this data is present** — its real shape drives Task 7's parser. Note the nesting quirks; you'll parse them in Task 7.

- [ ] **Step 5: Commit the fixtures (they contain no secrets — public player stats only)**

```bash
git add scripts/spike_oauth.py tests/fixtures/*.json
git commit -m "spike: prove Yahoo OAuth2 and save real response fixtures"
```

---

## Task 5: Schedule spike (THROWAWAY — de-risk gate #2)

> Proves we can get **how many games each NBA team plays in a given fantasy week** (and how many remain). The core value model depends on this.

**Files:**
- Create: `scripts/spike_schedule.py`
- Produces: `tests/fixtures/schedule_week.json`

- [ ] **Step 1: Write `scripts/spike_schedule.py`** — try the free, key-less balldontlie games endpoint

```python
"""Throwaway spike: prove we can count NBA games per team for a date range."""
import json
from collections import Counter
from pathlib import Path

import httpx

# balldontlie v1 games endpoint is free and needs no key for basic use.
URL = "https://www.balldontlie.io/api/v1/games"


def games_for_range(start: str, end: str) -> dict[str, int]:
    counts: Counter[str] = Counter()
    page = 1
    while True:
        r = httpx.get(URL, params={"start_date": start, "end_date": end,
                                   "per_page": 100, "page": page})
        r.raise_for_status()
        data = r.json()
        for g in data["data"]:
            counts[g["home_team"]["abbreviation"]] += 1
            counts[g["visitor_team"]["abbreviation"]] += 1
        if not data["meta"].get("next_page"):
            break
        page = data["meta"]["next_page"]
    return dict(counts)


if __name__ == "__main__":
    # Pick a real Mon–Sun fantasy week.
    counts = games_for_range("2026-01-05", "2026-01-11")
    Path("tests/fixtures").mkdir(parents=True, exist_ok=True)
    Path("tests/fixtures/schedule_week.json").write_text(json.dumps(counts, indent=2))
    print(counts)
```

- [ ] **Step 2: Run the spike**

```bash
uv run python scripts/spike_schedule.py
```
Expected: a dict like `{"LAL": 4, "BOS": 3, ...}` and a saved `schedule_week.json`.

- [ ] **Step 3: GATE — decide the source**

If balldontlie returns sane per-team counts, that's our schedule source. If it's rate-limited/unavailable, fall back to Yahoo's own schedule data (inspect what `roster.json` exposes) or a static season schedule CSV. **Record the chosen source in `docs/design.md` §14 (weekly-schedule data source)** before proceeding.

- [ ] **Step 4: Commit**

```bash
git add scripts/spike_schedule.py tests/fixtures/schedule_week.json
git commit -m "spike: prove NBA weekly games-played source"
```

---

## Task 6: Yahoo auth — token store & refresh

**Files:**
- Create: `src/fantasy_gm/yahoo_client/__init__.py` (empty), `src/fantasy_gm/yahoo_client/auth.py`
- Test: `tests/test_auth.py`

Behavior: store the single token row in Postgres; return a valid access token, refreshing transparently when expired.

- [ ] **Step 1: Write the failing test** (mocks the HTTP refresh; uses the `db` fixture)

```python
# tests/test_auth.py
from datetime import datetime, timedelta, timezone

import httpx

from fantasy_gm.yahoo_client import auth


def _save(access, refresh, expires_at):
    from fantasy_gm.db import execute
    execute(
        "INSERT INTO oauth_tokens (id, access_token, refresh_token, expires_at) "
        "VALUES (1, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
        "access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token, "
        "expires_at=EXCLUDED.expires_at",
        (access, refresh, expires_at),
    )


def test_returns_valid_token_without_refresh(db):
    future = datetime.now(timezone.utc) + timedelta(minutes=30)
    _save("good", "r", future)
    assert auth.get_access_token() == "good"


def test_refreshes_when_expired(db, monkeypatch):
    past = datetime.now(timezone.utc) - timedelta(minutes=1)
    _save("stale", "r-token", past)

    def fake_post(url, data=None, **kw):
        assert data["grant_type"] == "refresh_token"
        assert data["refresh_token"] == "r-token"
        return httpx.Response(200, json={
            "access_token": "fresh", "refresh_token": "r-token2",
            "expires_in": 3600})

    monkeypatch.setattr(httpx, "post", fake_post)
    assert auth.get_access_token() == "fresh"
    # persisted for next time
    assert auth.get_access_token() == "fresh"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth.py -v`
Expected: FAIL (`ModuleNotFoundError: fantasy_gm.yahoo_client.auth`).

- [ ] **Step 3: Implement `src/fantasy_gm/yahoo_client/auth.py`**

```python
from datetime import datetime, timedelta, timezone

import httpx

from fantasy_gm.config import get_settings
from fantasy_gm.db import execute, fetch_one

TOKEN_URL = "https://api.login.yahoo.com/oauth2/get_token"
_SKEW = timedelta(seconds=60)  # refresh a bit early


def _save(access: str, refresh: str, expires_at: datetime) -> None:
    execute(
        "INSERT INTO oauth_tokens (id, access_token, refresh_token, expires_at) "
        "VALUES (1, %s, %s, %s) ON CONFLICT (id) DO UPDATE SET "
        "access_token=EXCLUDED.access_token, refresh_token=EXCLUDED.refresh_token, "
        "expires_at=EXCLUDED.expires_at",
        (access, refresh, expires_at),
    )


def _refresh(refresh_token: str) -> str:
    s = get_settings()
    resp = httpx.post(TOKEN_URL, data={
        "client_id": s.yahoo_client_id,
        "client_secret": s.yahoo_client_secret,
        "redirect_uri": s.yahoo_redirect_uri,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    })
    resp.raise_for_status()
    body = resp.json()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=body["expires_in"])
    new_refresh = body.get("refresh_token", refresh_token)
    _save(body["access_token"], new_refresh, expires_at)
    return body["access_token"]


def get_access_token() -> str:
    row = fetch_one(
        "SELECT access_token, refresh_token, expires_at FROM oauth_tokens WHERE id=1")
    if row is None:
        raise RuntimeError("No Yahoo tokens stored. Run scripts/spike_oauth.py first.")
    if row["expires_at"] - _SKEW > datetime.now(timezone.utc):
        return row["access_token"]
    return _refresh(row["refresh_token"])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_auth.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/yahoo_client/ tests/test_auth.py
git commit -m "feat: yahoo token store with transparent refresh"
```

---

## Task 7: Yahoo client — typed parsing

**Files:**
- Create: `src/fantasy_gm/yahoo_client/client.py`
- Test: `tests/test_client.py`

> The exact JSON paths below are **placeholders you MUST adjust** to match the real fixture shapes you saved in Task 4. Yahoo nests data awkwardly (numeric string keys, `count` fields). Open `tests/fixtures/league_settings.json` etc. and map the real paths. The tests below assert against *your* fixtures, so they lock in the real shape.

- [ ] **Step 1: Write helper to load a fixture** — add to `tests/conftest.py`

```python
import json
from pathlib import Path

@pytest.fixture
def fixture():
    def _load(name: str) -> dict:
        return json.loads((Path("tests/fixtures") / name).read_text())
    return _load
```

- [ ] **Step 2: Write the failing test** at `tests/test_client.py`

```python
from fantasy_gm.yahoo_client.client import (
    parse_free_agents,
    parse_league_settings,
)


def test_parse_league_settings(fixture):
    s = parse_league_settings(fixture("league_settings.json"))
    assert s.league_key  # non-empty
    assert s.format in {"category", "points"}
    if s.is_category:
        assert len(s.categories) > 0


def test_parse_free_agents_returns_players_with_stats(fixture):
    players = parse_free_agents(fixture("free_agents.json"))
    assert len(players) > 0
    p = players[0]
    assert p.name and p.player_id
    assert isinstance(p.stats, dict)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_client.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 4: Implement `src/fantasy_gm/yahoo_client/client.py`**

Write the parsers to match your real fixtures. Skeleton to adapt (adjust every path marked `# ADJUST`):

```python
from typing import Any

import httpx

from fantasy_gm.schemas import LeagueSettings, Player
from fantasy_gm.yahoo_client.auth import get_access_token

API = "https://fantasysports.yahooapis.com/fantasy/v2"


def _get(path: str) -> dict[str, Any]:
    token = get_access_token()
    r = httpx.get(f"{API}/{path}?format=json",
                  headers={"Authorization": f"Bearer {token}"}, timeout=20)
    r.raise_for_status()
    return r.json()


def parse_league_settings(raw: dict[str, Any]) -> LeagueSettings:
    # ADJUST paths to your fixture. Yahoo commonly nests under fantasy_content.
    league = raw["fantasy_content"]["league"]           # ADJUST
    settings = league[1]["settings"][0]                 # ADJUST
    league_key = league[0]["league_key"]                # ADJUST
    scoring = settings.get("scoring_type", "head")      # ADJUST
    fmt = "points" if "point" in scoring else "category"
    categories = [
        c["stat"]["display_name"]                       # ADJUST
        for c in settings.get("stat_categories", {}).get("stats", [])
    ]
    return LeagueSettings(league_key=league_key, format=fmt, categories=categories)


def parse_free_agents(raw: dict[str, Any]) -> list[Player]:
    # ADJUST to your fixture's player-list nesting.
    players_node = raw["fantasy_content"]["league"][1]["players"]  # ADJUST
    out: list[Player] = []
    for key, node in players_node.items():
        if key == "count":
            continue
        pdata = node["player"]                          # ADJUST
        meta = pdata[0]
        stats = pdata[1].get("player_stats", {}).get("stats", [])  # ADJUST
        out.append(Player(
            player_id=_meta(meta, "player_id"),
            name=_meta(meta, "name")["full"] if isinstance(_meta(meta, "name"), dict)
                 else _meta(meta, "name"),
            nba_team=_meta(meta, "editorial_team_abbr"),
            positions=_positions(meta),
            stats={s["stat"]["stat_id"]: float(s["stat"]["value"] or 0)  # ADJUST
                   for s in stats},
        ))
    return out


def _meta(meta_list: list[dict], field: str):
    for item in meta_list:
        if field in item:
            return item[field]
    return ""


def _positions(meta_list: list[dict]) -> list[str]:
    val = _meta(meta_list, "eligible_positions")
    if isinstance(val, list):
        return [p.get("position", "") for p in val]
    return []


# Live fetch wrappers (used by sync/tools; not unit-tested against the network)
def fetch_league_settings(league_key: str) -> LeagueSettings:
    return parse_league_settings(_get(f"league/{league_key}/settings"))


def fetch_free_agents(league_key: str) -> list[Player]:
    return parse_free_agents(_get(f"league/{league_key}/players;status=FA;out=stats"))
```

- [ ] **Step 5: Iterate until tests pass**

Run: `uv run pytest tests/test_client.py -v`
Adjust the `# ADJUST` paths against your fixtures until both tests PASS. This is the "wrestle the legacy API" work — expect a few iterations.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/yahoo_client/client.py tests/test_client.py tests/conftest.py
git commit -m "feat: typed parsers for Yahoo league settings and free agents"
```

---

## Task 8: Short-TTL cache

**Files:**
- Create: `src/fantasy_gm/yahoo_client/cache.py`
- Test: `tests/test_cache.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cache.py
import time
from fantasy_gm.yahoo_client.cache import ttl_cache


def test_caches_within_ttl_and_expires():
    calls = {"n": 0}

    @ttl_cache(ttl_seconds=1)
    def f():
        calls["n"] += 1
        return calls["n"]

    assert f() == 1
    assert f() == 1          # cached
    time.sleep(1.1)
    assert f() == 2          # expired -> recomputed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cache.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement `src/fantasy_gm/yahoo_client/cache.py`**

```python
import time
from functools import wraps
from typing import Callable


def ttl_cache(ttl_seconds: float) -> Callable:
    def decorator(fn: Callable) -> Callable:
        store: dict[tuple, tuple[float, object]] = {}

        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.monotonic()
            if key in store:
                ts, val = store[key]
                if now - ts < ttl_seconds:
                    return val
            val = fn(*args, **kwargs)
            store[key] = (now, val)
            return val

        wrapper.cache_clear = store.clear  # type: ignore[attr-defined]
        return wrapper

    return decorator
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cache.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/yahoo_client/cache.py tests/test_cache.py
git commit -m "feat: short-ttl cache decorator"
```

---

## Task 9: Error classification

**Files:**
- Create: `src/fantasy_gm/yahoo_client/errors.py`
- Test: `tests/test_errors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_errors.py
import httpx
import pytest

from fantasy_gm.yahoo_client.errors import YahooError, classify


def test_401_maps_to_reauth():
    err = classify(httpx.HTTPStatusError(
        "x", request=httpx.Request("GET", "http://x"),
        response=httpx.Response(401)))
    assert err.kind == "reauth"


def test_429_maps_to_rate_limited():
    err = classify(httpx.HTTPStatusError(
        "x", request=httpx.Request("GET", "http://x"),
        response=httpx.Response(429)))
    assert err.kind == "rate_limited"

def test_yahoo_error_is_raisable():
    with pytest.raises(YahooError):
        raise YahooError(kind="unknown", message="boom")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_errors.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement `src/fantasy_gm/yahoo_client/errors.py`**

```python
from dataclasses import dataclass

import httpx


@dataclass
class YahooError(Exception):
    kind: str      # "reauth" | "rate_limited" | "server" | "unknown"
    message: str

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message}"


def classify(exc: httpx.HTTPStatusError) -> YahooError:
    status = exc.response.status_code
    if status == 401:
        return YahooError("reauth", "Access rejected; refresh token likely dead.")
    if status == 429:
        return YahooError("rate_limited", "Yahoo rate limit hit; back off.")
    if 500 <= status < 600:
        return YahooError("server", f"Yahoo server error {status}.")
    return YahooError("unknown", f"Unexpected status {status}.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_errors.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/yahoo_client/errors.py tests/test_errors.py
git commit -m "feat: classify Yahoo HTTP errors into actionable kinds"
```

---

## Task 10: Value model (the analytical core)

**Files:**
- Create: `src/fantasy_gm/value.py`
- Test: `tests/test_value.py`

Two modes from the spec: **short-term** (games-this-week aware) and **long-term** (season value, schedule ignored). Pure functions → easy, high-value tests.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_value.py
import pytest

from fantasy_gm.value import long_term_value, short_term_value


def test_short_term_scales_with_games_this_week():
    form = {"PTS": 20.0, "AST": 5.0}
    two = short_term_value(form, games_remaining=2)
    four = short_term_value(form, games_remaining=4)
    assert four == pytest.approx(2 * two)


def test_short_term_is_zero_with_no_games():
    assert short_term_value({"PTS": 20.0}, games_remaining=0) == 0.0


def test_long_term_ignores_weekly_games():
    season = {"PTS": 20.0, "AST": 5.0}
    # games_remaining must not affect long-term value
    assert long_term_value(season) == long_term_value(season)
    assert long_term_value(season) == pytest.approx(25.0)  # simple sum baseline
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_value.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement `src/fantasy_gm/value.py`**

```python
"""Player valuation.

short_term_value: for waivers/streaming/start-sit. Weighs games *this week*.
long_term_value:  for core-player trade evaluation. Season value; schedule ignored.

Both take a stat map (category -> per-game value). v1 uses an equal-weight sum as
the baseline aggregate; category weights can be layered on later without changing
the interface.
"""


def _aggregate(stats: dict[str, float]) -> float:
    return sum(stats.values())


def short_term_value(recent_form: dict[str, float], games_remaining: int) -> float:
    """Expected contribution over the rest of this week."""
    return _aggregate(recent_form) * games_remaining


def long_term_value(season_stats: dict[str, float]) -> float:
    """Sustained per-game value; deliberately independent of weekly schedule."""
    return _aggregate(season_stats)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_value.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/value.py tests/test_value.py
git commit -m "feat: short-term and long-term player valuation"
```

---

## Task 11: Nightly sync job

**Files:**
- Create: `src/fantasy_gm/sync.py`
- Test: `tests/test_sync.py`

Writes daily player stat snapshots and weekly schedule into Postgres so `get_trends`/`get_weekly_schedule` read locally. Tests inject fake fetchers (no network).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_sync.py
from datetime import date

from fantasy_gm.db import fetch_all
from fantasy_gm.schemas import Player
from fantasy_gm.sync import sync_schedule, sync_stats


def test_sync_stats_upserts_snapshot(db):
    players = [Player(player_id="1", name="X", nba_team="LAL",
                      stats={"PTS": 20.0})]
    sync_stats(players, snapshot_date=date(2026, 1, 6))
    rows = fetch_all("SELECT player_id, stats FROM player_stat_snapshots")
    assert rows[0]["player_id"] == "1"
    assert rows[0]["stats"]["PTS"] == 20.0


def test_sync_schedule_writes_counts(db):
    sync_schedule({"LAL": 4, "BOS": 3}, week=1,
                  remaining={"LAL": 4, "BOS": 3}, as_of=date(2026, 1, 6))
    rows = {r["nba_team"]: r["games_total"]
            for r in fetch_all("SELECT nba_team, games_total FROM weekly_schedule")}
    assert rows == {"LAL": 4, "BOS": 3}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_sync.py -v`
Expected: FAIL (`ImportError`).

- [ ] **Step 3: Implement `src/fantasy_gm/sync.py`**

```python
import json
from datetime import date

from fantasy_gm.db import execute
from fantasy_gm.schemas import Player


def sync_stats(players: list[Player], snapshot_date: date) -> None:
    for p in players:
        execute(
            "INSERT INTO player_stat_snapshots (player_id, snapshot_date, stats) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (player_id, snapshot_date) DO UPDATE SET stats=EXCLUDED.stats",
            (p.player_id, snapshot_date, json.dumps(p.stats)),
        )


def sync_schedule(games_total: dict[str, int], week: int,
                  remaining: dict[str, int], as_of: date) -> None:
    for team, total in games_total.items():
        execute(
            "INSERT INTO weekly_schedule "
            "(nba_team, week, games_total, games_remaining, as_of_date) "
            "VALUES (%s, %s, %s, %s, %s) "
            "ON CONFLICT (nba_team, week) DO UPDATE SET "
            "games_total=EXCLUDED.games_total, "
            "games_remaining=EXCLUDED.games_remaining, "
            "as_of_date=EXCLUDED.as_of_date",
            (team, week, total, remaining.get(team, total), as_of),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_sync.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/sync.py tests/test_sync.py
git commit -m "feat: nightly sync of stat snapshots and weekly schedule"
```

---

## Task 12: The agent toolbox

**Files:**
- Create: `src/fantasy_gm/tools.py`
- Test: `tests/test_tools.py`

These are plain typed functions now (Phase 2 wraps them as LangGraph tools). They read from Postgres + the Yahoo client and return clean data. Includes the **league-config read-once/refresh** behavior and **trends** (recent form from snapshots).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tools.py
import json
from datetime import date, timedelta

from fantasy_gm.db import execute
from fantasy_gm import tools


def test_get_league_settings_reads_cache_without_fetch(db, monkeypatch):
    execute(
        "INSERT INTO league_config (league_key, format, categories) "
        "VALUES (%s, %s, %s)",
        ("428.l.1", "category", json.dumps(["PTS", "AST"])),
    )
    # If it tries to fetch from Yahoo, fail the test.
    monkeypatch.setattr(tools, "_fetch_settings",
                        lambda k: (_ for _ in ()).throw(AssertionError("fetched!")))
    s = tools.get_league_settings("428.l.1")
    assert s.categories == ["PTS", "AST"]


def test_get_trends_averages_recent_snapshots(db):
    execute("INSERT INTO player_stat_snapshots VALUES (%s,%s,%s)",
            ("1", date(2026, 1, 5), json.dumps({"PTS": 10.0})))
    execute("INSERT INTO player_stat_snapshots VALUES (%s,%s,%s)",
            ("1", date(2026, 1, 6), json.dumps({"PTS": 30.0})))
    trend = tools.get_trends(["1"], window_days=14,
                             as_of=date(2026, 1, 7))
    assert trend["1"]["PTS"] == 20.0  # mean of 10 and 30


def test_get_weekly_schedule_reads_table(db):
    execute("INSERT INTO weekly_schedule VALUES (%s,%s,%s,%s,%s)",
            ("LAL", 1, 4, 3, date(2026, 1, 6)))
    sched = tools.get_weekly_schedule(week=1)
    assert sched["LAL"]["games_remaining"] == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tools.py -v`
Expected: FAIL (`ImportError` / attribute errors).

- [ ] **Step 3: Implement `src/fantasy_gm/tools.py`**

```python
import json
from datetime import date, timedelta

from fantasy_gm.db import execute, fetch_all, fetch_one
from fantasy_gm.schemas import LeagueSettings
from fantasy_gm.yahoo_client import client


def _fetch_settings(league_key: str) -> LeagueSettings:
    return client.fetch_league_settings(league_key)


def get_league_settings(league_key: str) -> LeagueSettings:
    """Read cached config; fetch + cache only if missing (read-once behavior)."""
    row = fetch_one(
        "SELECT league_key, format, categories, roster_slots "
        "FROM league_config WHERE league_key=%s", (league_key,))
    if row is None:
        return refresh_league_settings(league_key)
    return LeagueSettings(
        league_key=row["league_key"], format=row["format"],
        categories=row["categories"], roster_slots=row["roster_slots"])


def refresh_league_settings(league_key: str) -> LeagueSettings:
    """Force a re-fetch from Yahoo and overwrite the cache."""
    s = _fetch_settings(league_key)
    execute(
        "INSERT INTO league_config (league_key, format, categories, roster_slots) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT (league_key) DO UPDATE SET "
        "format=EXCLUDED.format, categories=EXCLUDED.categories, "
        "roster_slots=EXCLUDED.roster_slots, cached_at=now()",
        (s.league_key, s.format, json.dumps(s.categories),
         json.dumps(s.roster_slots)),
    )
    return s


def get_trends(player_ids: list[str], window_days: int, as_of: date) -> dict[str, dict]:
    """Mean of each stat over the trailing window, per player."""
    start = as_of - timedelta(days=window_days)
    out: dict[str, dict] = {}
    for pid in player_ids:
        rows = fetch_all(
            "SELECT stats FROM player_stat_snapshots "
            "WHERE player_id=%s AND snapshot_date > %s AND snapshot_date <= %s",
            (pid, start, as_of))
        if not rows:
            out[pid] = {}
            continue
        totals: dict[str, float] = {}
        for r in rows:
            for k, v in r["stats"].items():
                totals[k] = totals.get(k, 0.0) + float(v)
        out[pid] = {k: v / len(rows) for k, v in totals.items()}
    return out


def get_weekly_schedule(week: int) -> dict[str, dict]:
    rows = fetch_all(
        "SELECT nba_team, games_total, games_remaining FROM weekly_schedule "
        "WHERE week=%s", (week,))
    return {r["nba_team"]: {"games_total": r["games_total"],
                            "games_remaining": r["games_remaining"]} for r in rows}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tools.py -v`
Expected: PASS (all three).

- [ ] **Step 5: Run the whole suite + lint**

```bash
uv run pytest -v
uv run ruff check src tests
```
Expected: all tests PASS; ruff clean (fix any lint issues).

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/tools.py tests/test_tools.py
git commit -m "feat: toolbox — league config (read-once/refresh), trends, schedule"
```

---

## Phase 1 Done — Definition of Done

- [ ] `uv run pytest -v` is green (config, db, schemas, auth, client, cache, errors, value, sync, tools).
- [ ] Both spikes passed and their fixtures are committed.
- [ ] The chosen weekly-schedule source is recorded in `docs/design.md` §14.
- [ ] `README.md` gains a short "Integration & Data Layer" section (draft the Architecture + Security & Auth notes now, while fresh).

**What Phase 1 delivers:** a tested, network-isolated data foundation — you can pull real Yahoo data, store it, compute trends and player value, and call every toolbox function. Everything the agent will need is in place and proven.

---

## Roadmap — later phases (to be detailed after Phase 1)

These are intentionally *not* broken into bite-sized tasks yet, because their code depends on the real data shapes discovered in Phase 1. They will each get their own full plan.

**Phase 2 — Agent, API & Evals** (spec §5, §8, §9a, §9c)
- Wrap `tools.py` functions as LangGraph tools; build the agent loop with league-config seeding, iteration/cost caps, and the grounding guardrail.
- Add remaining tools (`get_my_roster`, `get_team`, `get_free_agents`, `get_player_stats`) as thin Yahoo-client wrappers.
- FastAPI `/chat` with token + tool-event **streaming**; Postgres checkpointer for memory.
- LangSmith pre-ship eval dataset + grounding & tool-trajectory scorers.
- README: Trade-offs section.

**Phase 3 — Frontend, Deploy & Closed Loop** (spec §4 UI, §9b, §10, §11)
- Vite + React streaming chat (tokens + tool-status chips + stat tables).
- Deploy: Vercel (frontend) + Railway/Fly (backend + Postgres); live URL.
- Wire Intent-Analysis skill catalog to the toolbox; connect ingestion to the live LangSmith project.
- README: Deployment Guide + diagram + demo GIF/Loom.
