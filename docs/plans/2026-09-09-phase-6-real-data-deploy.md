# Phase 6 — Real NBA Data + Public Deploy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** (1) Replace the generated fake demo league with a **static real-NBA dataset** (real names + real per-game stats) so the app is credible until the Yahoo API connects. (2) **Deploy** it to a public URL (Railway backend + Postgres, Vercel frontend) — an always-on, cost-guarded demo whose link can be added to the Yahoo API application to speed review.

**Architecture:** A local build script uses `nba_api` (real stats from stats.nba.com — works from a residential machine, not from the datacenter, so we snapshot to static JSON) to generate `demo_data/league.json` + `free_agents.json` with real players drafted into the 12-team demo league. The deployed backend serves this static data (no live nba_api). The public Claude-powered endpoints (`/chat`, `/trade/analyze`) get a per-IP in-memory **rate limiter** and run on **`claude-sonnet-5`** (set via the existing `AGENT_MODEL` env — no code change). A Dockerfile packages the backend for Railway; the frontend builds on Vercel. Determinism boundary unchanged.

**Tech Stack:** existing + `nba_api` (dev/script only — pulls pandas/numpy, NOT in the production image) + a Dockerfile. No new runtime deps except the tiny rate limiter (stdlib).

---

## File Structure

```
scripts/build_real_league.py     # NEW — nba_api → real 12-team league + FAs (run locally)
demo_data/league.json            # regenerated with REAL players/stats
demo_data/free_agents.json       # regenerated with REAL players/stats
src/fantasy_gm/ratelimit.py      # NEW — in-memory per-key rate limiter
src/fantasy_gm/api.py            # (modify) apply rate limit to /chat + /trade/analyze
pyproject.toml                   # (modify) nba_api in a `scripts`/dev group
Dockerfile                       # NEW — backend image for Railway
.dockerignore                    # NEW
docs/deploy.md                   # NEW — Railway + Vercel runbook (also in D1 below)
```

---

## Task A1: Build the real-NBA dataset (local)

**Files:** Modify `pyproject.toml`; Create `scripts/build_real_league.py`; regenerate `demo_data/league.json` + `free_agents.json`; Test: existing `tests/test_demo.py` must still pass against the real data.

- [ ] **Step 1: Add nba_api as a dev/script dependency** (kept out of the production image)

```bash
uv add --dev nba_api
```

- [ ] **Step 2: Write `scripts/build_real_league.py`**

```python
"""Build a static real-NBA demo league from nba_api (run LOCALLY — stats.nba.com
blocks datacenter IPs, so we snapshot to static JSON the deployed app serves).

    uv run python scripts/build_real_league.py [SEASON]   # e.g. 2024-25
Regenerates demo_data/league.json + demo_data/free_agents.json with real players.
"""
import json
import sys
from pathlib import Path

from nba_api.stats.endpoints import leaguedashplayerstats as L

OUT = Path(__file__).resolve().parent.parent / "demo_data"
# nba_api column -> our category key
MAP = {"PTS": "PTS", "REB": "REB", "AST": "AST", "STL": "ST", "BLK": "BLK",
       "TOV": "TO", "FG3M": "3PTM", "FG_PCT": "FG%", "FT_PCT": "FT%"}
N_TEAMS, PER_TEAM = 12, 10


def _fantasy_score(s: dict) -> float:
    # rough draft-ordering value (counting cats minus turnovers)
    return (s["PTS"] + s["REB"] * 1.2 + s["AST"] * 1.5 + s["ST"] * 3
            + s["BLK"] * 3 + s["3PTM"] - s["TO"])


def build(season: str) -> None:
    df = L.LeagueDashPlayerStats(season=season, per_mode_detailed="PerGame",
                                 timeout=60).get_data_frames()[0]
    df = df[df["GP"] >= 20]  # real rotation players only
    players = []
    for _, r in df.iterrows():
        stats = {ours: round(float(r[nba]), 3) for nba, ours in MAP.items()}
        players.append({"player_id": str(int(r["PLAYER_ID"])),
                        "name": r["PLAYER_NAME"], "nba_team": r["TEAM_ABBREVIATION"],
                        "positions": [], "stats": stats})
    players.sort(key=lambda p: _fantasy_score(p["stats"]), reverse=True)

    drafted = players[: N_TEAMS * PER_TEAM]
    free_agents = players[N_TEAMS * PER_TEAM : N_TEAMS * PER_TEAM + 40]

    # snake draft into 12 teams so rosters are balanced
    teams = [[] for _ in range(N_TEAMS)]
    for i, p in enumerate(drafted):
        rnd = i // N_TEAMS
        col = i % N_TEAMS
        idx = col if rnd % 2 == 0 else (N_TEAMS - 1 - col)
        teams[idx].append(p)
    league = {"teams": [
        {"team_key": f"428.l.123456.t.{i+1}",
         "name": "My Squad" if i == 0 else f"Team {i+1}",
         "players": roster}
        for i, roster in enumerate(teams)]}

    OUT.mkdir(exist_ok=True)
    (OUT / "league.json").write_text(json.dumps(league, indent=2))
    (OUT / "free_agents.json").write_text(json.dumps({"players": free_agents}, indent=2))
    print(f"built {len(drafted)} rostered + {len(free_agents)} FAs from real {season} data")


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "2024-25")
```

- [ ] **Step 3: Run it** (uses the most recent completed season by default; adjust when the new season has enough games)

```bash
uv run python scripts/build_real_league.py
```
Expected: prints a build summary; `demo_data/league.json` now has real names (Jokić, SGA, …) with real stats.

- [ ] **Step 4: Re-seed Postgres** from the real data (snapshots + schedule)

```bash
uv run python scripts/seed_demo_data.py
```

- [ ] **Step 5: Verify existing demo tests still pass** against real data

Run: `uv run pytest tests/test_demo.py -v`
Expected: PASS (12 teams, ≥5 players each, human category keys — now real players).

- [ ] **Step 6: Commit** (the real dataset is public season-average stats — fine to commit)

```bash
git add scripts/build_real_league.py demo_data/league.json demo_data/free_agents.json pyproject.toml uv.lock
git commit -m "feat: real-NBA demo league from nba_api (static snapshot)"
```

---

## Task B1: Rate limiter for the public Claude endpoints

**Files:** Create `src/fantasy_gm/ratelimit.py`; Modify `src/fantasy_gm/api.py`; Test `tests/test_ratelimit.py`, `tests/test_api.py`

- [ ] **Step 1: Write the failing unit test** `tests/test_ratelimit.py`

```python
from fantasy_gm.ratelimit import RateLimiter

def test_allows_up_to_limit_then_blocks():
    rl = RateLimiter(max_requests=2, window_seconds=60)
    assert rl.allow("ip1", now=100.0) is True
    assert rl.allow("ip1", now=101.0) is True
    assert rl.allow("ip1", now=102.0) is False        # 3rd within window blocked
    assert rl.allow("ip2", now=102.0) is True          # other key unaffected

def test_window_resets():
    rl = RateLimiter(max_requests=1, window_seconds=10)
    assert rl.allow("ip1", now=0.0) is True
    assert rl.allow("ip1", now=5.0) is False
    assert rl.allow("ip1", now=11.0) is True           # window elapsed
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `src/fantasy_gm/ratelimit.py`**

```python
import time
from collections import defaultdict


class RateLimiter:
    """In-memory sliding-window limiter (single-instance; fine for one Railway dyno)."""

    def __init__(self, max_requests: int, window_seconds: float):
        self.max = max_requests
        self.window = window_seconds
        self._hits: dict[str, list[float]] = defaultdict(list)

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        hits = [t for t in self._hits[key] if now - t < self.window]
        if len(hits) >= self.max:
            self._hits[key] = hits
            return False
        hits.append(now)
        self._hits[key] = hits
        return True
```

- [ ] **Step 4: Add an endpoint test** (append to `tests/test_api.py`) — the limited endpoints 429 after the cap

```python
def test_chat_rate_limited(monkeypatch):
    from fantasy_gm import api
    # tiny limit so the test trips it fast
    monkeypatch.setattr(api, "_claude_limiter", api.RateLimiter(max_requests=1, window_seconds=60))
    from fantasy_gm.schemas import LeagueSettings
    monkeypatch.setattr(api, "_load_league",
                        lambda: LeagueSettings(league_key="k", format="category"))
    monkeypatch.setattr(api, "_make_model", lambda: object())

    class SpyAgent:
        def stream(self, *a, **k):
            return iter([("updates", {"agent": {"messages": []}})])
    monkeypatch.setattr(api, "build_agent", lambda **kw: SpyAgent())

    from fastapi.testclient import TestClient
    c = TestClient(api.app)
    r1 = c.post("/chat", json={"message": "hi", "conversation_id": "a"})
    r2 = c.post("/chat", json={"message": "hi", "conversation_id": "a"})
    assert r1.status_code == 200
    assert r2.status_code == 429
```

- [ ] **Step 5: Wire it into `api.py`** — a shared limiter + a guard on `/chat` and `/trade/analyze`

```python
from fastapi import HTTPException, Request
from fantasy_gm.ratelimit import RateLimiter

# ~20 Claude-backed requests per 10 min per IP — generous for a reviewer, caps abuse.
_claude_limiter = RateLimiter(max_requests=20, window_seconds=600)

def _guard(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    if not _claude_limiter.allow(ip):
        raise HTTPException(status_code=429, detail="Rate limit reached — try again shortly.")
```

Add a `request: Request` param and call `_guard(request)` at the top of `chat()` and `trade_analyze()`.

- [ ] **Step 6: Run tests, confirm pass; ruff clean; Commit**

```bash
git add src/fantasy_gm/ratelimit.py src/fantasy_gm/api.py tests/test_ratelimit.py tests/test_api.py
git commit -m "feat: per-IP rate limit on Claude-backed endpoints"
```

---

## Task B2: Backend Dockerfile for Railway

**Files:** Create `Dockerfile`, `.dockerignore`, `scripts/start.sh`

- [ ] **Step 1: Write `scripts/start.sh`** (idempotent migrate + seed, then serve; `$PORT` from Railway)

```bash
#!/usr/bin/env sh
set -e
export PYTHONPATH=/app/src
# --no-sync: deps were installed at build time; don't re-sync (avoids the
# uv local-package rebuild quirk). The app imports via PYTHONPATH, not an install.
uv run --no-sync python scripts/run_migrations.py
uv run --no-sync python scripts/setup_checkpointer.py
uv run --no-sync python scripts/seed_demo_data.py
exec uv run --no-sync uvicorn fantasy_gm.api:app --host 0.0.0.0 --port "${PORT:-8000}"
```

- [ ] **Step 2: Write `Dockerfile`** (production image — no dev deps, so no nba_api/pandas bloat)

```dockerfile
FROM python:3.12-slim
RUN pip install --no-cache-dir uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
# --no-install-project: install only third-party deps (the app source isn't copied
# yet, and we run it via PYTHONPATH, not as an installed package). --no-dev skips
# nba_api/pandas so the runtime image stays lean.
RUN uv sync --frozen --no-dev --no-install-project
COPY . .
ENV PYTHONPATH=/app/src
CMD ["sh", "scripts/start.sh"]
```

- [ ] **Step 3: Write `.dockerignore`**

```
frontend/node_modules
frontend/dist
.venv
.git
__pycache__
*.pyc
.pytest_cache
.ruff_cache
```

- [ ] **Step 4: Build the image locally to verify it compiles** (optional if Docker Desktop is running)

```bash
docker build -t fantasy-gm-api . && echo "image built"
```
(Startup will fail without a DATABASE_URL — that's expected locally; the build succeeding is what we're checking.)

- [ ] **Step 5: Commit**

```bash
git add Dockerfile .dockerignore scripts/start.sh
git commit -m "chore: backend Dockerfile + start script for Railway"
```

---

## Runbook D1: Deploy (Railway + Vercel) — needs your accounts

> Do these once with your logins. Order matters (each side needs the other's URL).

**1. Backend + Postgres on Railway**
- New project → **Deploy from GitHub repo** (push this repo to GitHub first if not already) → Railway detects the `Dockerfile`.
- Add a **PostgreSQL** plugin → it sets `DATABASE_URL` automatically (reference it in the service's variables).
- Set service **Variables**:
  - `ANTHROPIC_API_KEY` = your key
  - `AGENT_MODEL` = `claude-sonnet-5`  ← the cost guard (env-driven, no code change)
  - `DEMO_MODE` = `true`
  - `DEMO_LEAGUE_FORMAT` = `category` (or `points`)
  - `BALLDONTLIE_API_KEY` = your key
  - `LANGCHAIN_TRACING_V2` = `true`, `LANGCHAIN_API_KEY` = …, `LANGCHAIN_PROJECT` = `fantasy-gm-agent`
  - (`FRONTEND_ORIGIN` — fill after step 2)
- Deploy → copy the public backend URL (e.g. `https://fantasy-gm-api.up.railway.app`).

**2. Frontend on Vercel**
- Import the repo → **Root Directory = `frontend`**, framework preset **Vite**.
- Env var `VITE_API_BASE` = the Railway backend URL from step 1.
- Deploy → copy the Vercel URL (e.g. `https://fantasy-gm.vercel.app`).

**3. Close the CORS loop**
- Back in Railway, set `FRONTEND_ORIGIN` = the Vercel URL → redeploy backend.
- Open the Vercel URL; confirm chat, dashboard, and a trade all work end-to-end.

**4. Speed up Yahoo review**
- Add the **live Vercel URL** to your Yahoo Fantasy API application (in the "Website URL / where the product lives" field) so the reviewer can see a working product.

## Runbook D2: Refreshing real data (weekly, optional)
- Re-run locally: `uv run python scripts/build_real_league.py [SEASON]` → commit the updated `demo_data/*.json` → Railway redeploys → `start.sh` re-seeds. (Deployed server can't call nba_api itself — datacenter IPs are blocked — so refresh is a local commit.)

---

## Phase 6 Done — Definition of Done
- [ ] `demo_data/league.json` + `free_agents.json` contain real NBA players/stats; `uv run pytest` green (incl. ratelimit + rate-limit endpoint test).
- [ ] Dashboard/trade/chat show real player names locally (both formats).
- [ ] `docker build` succeeds.
- [ ] Deploy runbook produces a working public Vercel URL backed by Railway; chat/dashboard/trade work live; the URL is added to the Yahoo application.

## Deferred / notes
- Auth still deferred (public review URL by design; rate limit + Sonnet cap cost).
- Real Yahoo swap on approval unchanged (DEMO_MODE=false + re-auth + parser validation).
- The single-instance in-memory rate limiter resets on redeploy and isn't shared across replicas — fine for one Railway instance; revisit if scaled out.
