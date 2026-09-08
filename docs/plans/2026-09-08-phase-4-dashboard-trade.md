# Phase 4 — Dashboard, Trade Analyzer & Full-League Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Turn the single-view chat app into a three-view product — **Chat · Dashboard · Trade Analyzer** — backed by a realistic 12-team demo league. Add an analytics dashboard (category profile radar, streaming board, buy-low/sell-high, games-this-week heatmap) and a hybrid trade analyzer (deterministic per-category value delta → LLM honest verdict). Expose full-league data to the chat agent too.

**Architecture:** Backend gains a pure-Python `analytics.py` (dashboard datasets) and `trade.py` (category-delta math), each behind a FastAPI endpoint; the trade verdict is a single focused Claude call grounded in the computed deltas (not the full agent loop). A seeded generator produces a 12-team demo league so every view has substance. Frontend adds `react-router-dom` (3 routes), a Dashboard view with four reusable SVG chart components built per the `dataviz` method, and a Trade Analyzer view with roster pickers. Determinism boundary: all analytics + trade math are pure functions (unit-tested); the LLM verdict is validated with the fake model + live check.

**Tech Stack:** existing + `react-router-dom`. Charts are hand-built SVG (no chart lib) using the app's tokens as the chart palette.

**Chart palette (dataviz):** categorical **you=`--primary` (#2563EB)**, **league=`--muted`**; diverging **buy-low=`--accent` (#059669)** ↔ **sell-high=`--danger` (#DC2626)** with a neutral gray midpoint; sequential single-hue blue ramp for magnitude (streaming bars, games heatmap). Every chart ships a legend for ≥2 series and a table fallback; dark mode uses the dark tokens (stepped, not auto-flipped). Run `dataviz/scripts/validate_palette.js "#2563EB,#64748B" --mode light` before shipping the categorical pair.

---

## File Structure

```
demo_data/league.json                 # generated 12-team league (simple schema)
demo_data/free_agents.json            # generated ~30 free agents (overwrites the 3)
scripts/gen_demo_league.py            # seeded generator for the above
src/fantasy_gm/demo.py                # (modify) read generated league/free-agents
src/fantasy_gm/analytics.py           # dashboard datasets (pure functions)
src/fantasy_gm/trade.py               # trade category-delta math (pure)
src/fantasy_gm/api.py                 # (modify) /analytics/dashboard, /trade/analyze
src/fantasy_gm/agent_tools.py         # (modify) add get_league_teams, get_team
frontend/src/lib/api.ts               # typed fetch helpers for the two endpoints
frontend/src/views/ChatView.tsx       # (the existing chat, extracted from App)
frontend/src/views/DashboardView.tsx
frontend/src/views/TradeView.tsx
frontend/src/components/charts/RadarChart.tsx
frontend/src/components/charts/BarList.tsx
frontend/src/components/charts/DivergingList.tsx
frontend/src/components/charts/GamesHeatmap.tsx
frontend/src/components/Nav.tsx        # top tabs
frontend/src/App.tsx                   # (modify) router + layout
```

---

## Task B1: Demo league generator + multi-team demo

**Files:** Create `scripts/gen_demo_league.py`; Modify `src/fantasy_gm/demo.py`; Test `tests/test_demo.py`

- [ ] **Step 1: Write `scripts/gen_demo_league.py`** — seeded, deterministic, simple schema (keys already the human category names)

```python
"""Generate a realistic 12-team demo league into demo_data/. Deterministic (seeded).
Run: uv run python scripts/gen_demo_league.py"""
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

CATS = ["PTS", "REB", "AST", "ST", "BLK", "3PTM", "FG%", "FT%", "TO"]
NBA = ["LAL", "BOS", "DEN", "MIL", "PHX", "GSW", "MIN", "NYK", "OKC", "IND",
       "MIA", "DAL", "SAC", "PHI", "CLE", "NOP"]
NAMES = ["Jalen Reed", "Marcus Vance", "Andre Cole", "Tyrus Bell", "Devin Park",
         # ... generator fills 170 unique names from a first/last pool below
]
FIRST = ["Jalen", "Marcus", "Andre", "Tyrus", "Devin", "Cody", "Malik", "Zion",
         "Trey", "Isaiah", "Jaylen", "Darius", "Cam", "Keon", "Brandon", "Xavier",
         "Amari", "Kobe", "Elijah", "Nate"]
LAST = ["Reed", "Vance", "Cole", "Bell", "Park", "Ford", "Hayes", "Blake", "Diaz",
        "Grant", "Moss", "Poole", "Rowe", "Sharp", "Tate", "Ware", "Young", "Booker",
        "Ellis", "Frazier"]


def _player(rng, pid):
    return {
        "player_id": str(pid),
        "name": f"{rng.choice(FIRST)} {rng.choice(LAST)}",
        "nba_team": rng.choice(NBA),
        "positions": [rng.choice(["PG", "SG", "SF", "PF", "C"])],
        "stats": {
            "PTS": round(rng.uniform(6, 28), 1), "REB": round(rng.uniform(2, 12), 1),
            "AST": round(rng.uniform(1, 9), 1), "ST": round(rng.uniform(0.4, 2.0), 1),
            "BLK": round(rng.uniform(0.2, 2.2), 1), "3PTM": round(rng.uniform(0.4, 3.6), 1),
            "FG%": round(rng.uniform(0.41, 0.55), 3), "FT%": round(rng.uniform(0.65, 0.9), 3),
            "TO": round(rng.uniform(0.7, 3.2), 1),
        },
    }


if __name__ == "__main__":
    rng = random.Random(42)
    pid = 1000
    teams = []
    for t in range(1, 13):
        players = [_player(rng, (pid := pid + 1)) for _ in range(10)]
        teams.append({"team_key": f"428.l.123456.t.{t}",
                      "name": "My Squad" if t == 1 else f"Team {t}",
                      "players": players})
    free_agents = [_player(rng, (pid := pid + 1)) for _ in range(30)]
    out = Path("demo_data")
    out.mkdir(exist_ok=True)
    (out / "league.json").write_text(json.dumps({"teams": teams}, indent=2))
    (out / "free_agents.json").write_text(json.dumps({"players": free_agents}, indent=2))
    print(f"generated {len(teams)} teams and {len(free_agents)} free agents")
```

(Fill `FIRST`/`LAST` as shown; delete the placeholder `NAMES` list — names are composed from the pools. 20×20 = 400 combos ≫ 150 players needed.)

- [ ] **Step 2: Run it** — `uv run python scripts/gen_demo_league.py` → writes the two files.

- [ ] **Step 3: Write the failing test** `tests/test_demo.py`

```python
from fantasy_gm import demo

def test_demo_league_has_twelve_teams():
    teams = demo.demo_teams()
    assert len(teams) == 12
    assert teams[0].team_key == "428.l.123456.t.1"
    assert teams[0].name == "My Squad"
    assert all(len(t.players) >= 5 for t in teams)

def test_demo_free_agents_pool():
    fas = demo.demo_free_agents()
    assert len(fas) >= 20
    p = fas[0]
    assert set(p.stats).issuperset({"PTS", "AST", "ST"})  # human category keys
```

- [ ] **Step 4: Run it, confirm fail** (current `demo.demo_teams` reads the 1-team fixture).

- [ ] **Step 5: Rewrite the team/FA readers in `src/fantasy_gm/demo.py`** to prefer the generated simple-schema files

```python
import json
from pathlib import Path

from fantasy_gm.schemas import LeagueSettings, Player, Team
from fantasy_gm.yahoo_client import client

DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"


def _load(name: str) -> dict:
    return json.loads((DEMO_DIR / name).read_text())


def demo_league_settings() -> LeagueSettings:
    return client.parse_league_settings(_load("league_settings.json"))


def _player(d: dict) -> Player:
    return Player(player_id=d["player_id"], name=d["name"], nba_team=d["nba_team"],
                  positions=d.get("positions", []), stats=d["stats"])


def demo_teams() -> list[Team]:
    data = _load("league.json")
    return [Team(team_key=t["team_key"], name=t["name"],
                 players=[_player(p) for p in t["players"]]) for t in data["teams"]]


def demo_free_agents() -> list[Player]:
    return [_player(p) for p in _load("free_agents.json")["players"]]
```

- [ ] **Step 6: Run it, confirm pass**; re-seed Postgres snapshots for the new player pool: `uv run python scripts/seed_demo_data.py` (it reads `demo.demo_free_agents()`/`demo.demo_teams()`). **Step 7: Commit**

```bash
git add scripts/gen_demo_league.py demo_data/league.json demo_data/free_agents.json src/fantasy_gm/demo.py tests/test_demo.py
git commit -m "feat: seeded 12-team demo league + multi-team demo readers"
```

---

## Task B2: Expose full-league tools to the agent

**Files:** Modify `src/fantasy_gm/agent_tools.py`; Test `tests/test_agent_tools.py` (add a case)

- [ ] **Step 1: Add the failing test**

```python
def test_build_tools_includes_league_teams(monkeypatch):
    from fantasy_gm import agent_tools, tools
    from fantasy_gm.schemas import Team
    monkeypatch.setattr(tools, "get_all_teams",
                        lambda k: [Team(team_key="428.l.1.t.2", name="Rivals", players=[])])
    lc = agent_tools.build_tools(league_key="428.l.1", my_team_key="428.l.1.t.1")
    names = {t.name for t in lc}
    assert "get_league_teams" in names
    teams_tool = next(t for t in lc if t.name == "get_league_teams")
    assert teams_tool.invoke({})[0]["name"] == "Rivals"
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Add the tool** inside `build_tools` in `agent_tools.py`

```python
    def get_league_teams() -> list[dict]:
        """List every team in the league with their rosters and player stats.
        Use to scout opponents and find trade targets."""
        return [t.model_dump() for t in tools.get_all_teams(league_key)]
```

Append `StructuredTool.from_function(get_league_teams)` to the returned list.

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add src/fantasy_gm/agent_tools.py tests/test_agent_tools.py
git commit -m "feat: expose full-league team data to the chat agent"
```

---

## Task B3: Analytics datasets (pure functions)

**Files:** Create `src/fantasy_gm/analytics.py`; Test `tests/test_analytics.py`

All four dashboard datasets as pure functions over `Team`/`Player` lists + a schedule map. No IO here — the endpoint wires the data in.

- [ ] **Step 1: Write the failing test**

```python
from fantasy_gm.analytics import (buy_low_sell_high, category_profile,
                                   streaming_board)
from fantasy_gm.schemas import Player, Team

CATS = ["PTS", "AST", "TO"]

def _p(pid, **stats):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=stats)

def test_category_profile_you_vs_league_average():
    mine = Team(team_key="t1", name="Mine", players=[_p("1", PTS=20, AST=5)])
    other = Team(team_key="t2", name="Other", players=[_p("2", PTS=10, AST=1)])
    prof = category_profile(mine, [mine, other], CATS)
    assert prof["PTS"]["you"] == 20
    assert prof["PTS"]["league_avg"] == 15  # (20+10)/2

def test_streaming_board_ranks_by_form_times_games():
    fas = [_p("1", PTS=10), _p("2", PTS=10)]
    trends = {"1": {"PTS": 12.0}, "2": {"PTS": 8.0}}
    games = {"LAL": 4}  # both LAL
    board = streaming_board(fas, trends, games, cats=["PTS"])
    assert board[0]["player_id"] == "1"      # higher form -> higher projected
    assert board[0]["projected"]["PTS"] == 48.0  # 12 * 4

def test_buy_low_sell_high_flags_divergence():
    players = [_p("1", PTS=20)]
    trends = {"1": {"PTS": 10.0}}  # cold vs season -> buy low
    res = buy_low_sell_high(players, trends, cats=["PTS"])
    assert res[0]["signal"] == "buy_low"
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `src/fantasy_gm/analytics.py`**

```python
from fantasy_gm.schemas import Player, Team


def _team_totals(team: Team, cats: list[str]) -> dict[str, float]:
    return {c: round(sum(p.stat(c) for p in team.players), 2) for c in cats}


def category_profile(my_team: Team, all_teams: list[Team],
                     cats: list[str]) -> dict[str, dict]:
    """Your per-category totals vs the league average per category."""
    per_team = [_team_totals(t, cats) for t in all_teams]
    mine = _team_totals(my_team, cats)
    n = len(per_team) or 1
    return {c: {"you": mine[c],
                "league_avg": round(sum(t[c] for t in per_team) / n, 2)}
            for c in cats}


def streaming_board(free_agents: list[Player], trends: dict[str, dict],
                    games: dict[str, int], cats: list[str]) -> list[dict]:
    """Rank FAs by projected week value = recent form x games this week."""
    rows = []
    for p in free_agents:
        form = trends.get(p.player_id) or {c: p.stat(c) for c in cats}
        g = games.get(p.nba_team, 0)
        projected = {c: round(form.get(c, 0.0) * g, 1) for c in cats}
        score = sum(v for c, v in projected.items() if c != "TO")
        rows.append({"player_id": p.player_id, "name": p.name, "nba_team": p.nba_team,
                     "games": g, "projected": projected, "score": round(score, 1)})
    return sorted(rows, key=lambda r: r["score"], reverse=True)


def buy_low_sell_high(players: list[Player], trends: dict[str, dict],
                      cats: list[str], threshold: float = 0.15) -> list[dict]:
    """Flag players whose recent form diverges from season by > threshold."""
    out = []
    for p in players:
        form = trends.get(p.player_id)
        if not form:
            continue
        season = sum(p.stat(c) for c in cats if c != "TO") or 1.0
        recent = sum(form.get(c, 0.0) for c in cats if c != "TO")
        delta = (recent - season) / season
        if abs(delta) < threshold:
            continue
        out.append({"player_id": p.player_id, "name": p.name,
                    "delta_pct": round(delta * 100, 1),
                    "signal": "sell_high" if delta > 0 else "buy_low"})
    return sorted(out, key=lambda r: abs(r["delta_pct"]), reverse=True)
```

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add src/fantasy_gm/analytics.py tests/test_analytics.py
git commit -m "feat: analytics datasets (category profile, streaming, buy-low/sell-high)"
```

---

## Task B4: `GET /analytics/dashboard`

**Files:** Modify `src/fantasy_gm/api.py`; Test `tests/test_api.py` (add a case)

- [ ] **Step 1: Add the failing test** (demo-mode data via monkeypatch of the loaders)

```python
def test_dashboard_endpoint_returns_all_sections(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player, Team
    monkeypatch.setattr(api, "_league_cats", lambda: ["PTS", "AST"])
    monkeypatch.setattr(api, "_all_teams",
        lambda: [Team(team_key="428.l.123456.t.1", name="My Squad",
                      players=[Player(player_id="1", name="A", nba_team="LAL",
                                      stats={"PTS": 20, "AST": 5})])])
    monkeypatch.setattr(api, "_free_agents",
        lambda: [Player(player_id="9", name="FA", nba_team="LAL", stats={"PTS": 10})])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {"9": {"PTS": 11.0}})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/analytics/dashboard").json()
    assert set(body) == {"category_profile", "streaming_board",
                         "buy_low_sell_high", "schedule"}
    assert body["category_profile"]["PTS"]["you"] == 20
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement in `api.py`** — small loader helpers + the endpoint

```python
from datetime import date
from fantasy_gm import analytics
from fantasy_gm.tools import get_all_teams, get_free_agents, get_trends, get_weekly_schedule

MY_WEEK = 15  # demo week

def _league_cats() -> list[str]:
    return _load_league().categories

def _all_teams(): return get_all_teams(LEAGUE_KEY)
def _free_agents(): return get_free_agents(LEAGUE_KEY)
def _trends_for(ids): return get_trends(ids, 14, date.today())
def _week_games():
    return {t: v["games_remaining"] for t, v in get_weekly_schedule(MY_WEEK).items()}

@app.get("/analytics/dashboard")
def dashboard() -> dict:
    cats = _league_cats()
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    fas = _free_agents()
    games = _week_games()
    fa_trends = _trends_for([p.player_id for p in fas])
    roster_trends = _trends_for([p.player_id for p in mine.players])
    return {
        "category_profile": analytics.category_profile(mine, teams, cats),
        "streaming_board": analytics.streaming_board(fas, fa_trends, games, cats)[:12],
        "buy_low_sell_high": analytics.buy_low_sell_high(
            mine.players + fas, {**roster_trends, **fa_trends}, cats)[:12],
        "schedule": games,
    }
```

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat: GET /analytics/dashboard aggregating the four datasets"
```

---

## Task B5: Trade engine + `POST /trade/analyze`

**Files:** Create `src/fantasy_gm/trade.py`; Modify `src/fantasy_gm/api.py`; Test `tests/test_trade.py`, `tests/test_api.py`

- [ ] **Step 1: Write the failing test** `tests/test_trade.py`

```python
from fantasy_gm.trade import category_delta
from fantasy_gm.schemas import Player

def _p(pid, **s): return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=s)

def test_category_delta_net_per_category():
    give = [_p("1", AST=8, PTS=10)]     # you send away
    get = [_p("2", AST=2, PTS=20)]      # you receive
    d = category_delta(give, get, cats=["AST", "PTS", "TO"])
    assert d["AST"] == -6.0   # lose 6 assists
    assert d["PTS"] == 10.0   # gain 10 points
    assert d["TO"] == 0.0

def test_category_delta_lower_is_better_for_turnovers_is_caller_concern():
    # engine reports raw net; TO interpretation happens in the verdict prompt
    give = [_p("1", TO=3)]
    get = [_p("2", TO=1)]
    assert category_delta(give, get, cats=["TO"])["TO"] == -2.0
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `src/fantasy_gm/trade.py`**

```python
from fantasy_gm.schemas import Player


def category_delta(give: list[Player], get: list[Player],
                   cats: list[str]) -> dict[str, float]:
    """Net per-category change to YOUR team from the trade (get - give).
    Percentage cats (FG%/FT%) are reported as a simple mean-of-means delta;
    note in the verdict that they should be volume-weighted for a real call."""
    def total(players, c):
        vals = [p.stat(c) for p in players]
        if c.endswith("%"):
            return sum(vals) / len(vals) if vals else 0.0
        return sum(vals)
    return {c: round(total(get, c) - total(give, c), 2) for c in cats}


def summarize(delta: dict[str, float]) -> dict:
    """Count categories improved vs worsened (TO: lower is better)."""
    improved, worsened = [], []
    for c, v in delta.items():
        good = v < 0 if c == "TO" else v > 0
        if v == 0:
            continue
        (improved if good else worsened).append(c)
    return {"improved": improved, "worsened": worsened}
```

- [ ] **Step 4: Add the endpoint test** to `tests/test_api.py` (LLM verdict via a fake model)

```python
def test_trade_analyze_returns_deltas_and_verdict(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player
    pool = {"1": Player(player_id="1", name="Mine", nba_team="LAL", stats={"AST": 8}),
            "2": Player(player_id="2", name="Theirs", nba_team="BOS", stats={"AST": 2})}
    monkeypatch.setattr(api, "_league_cats", lambda: ["AST"])
    monkeypatch.setattr(api, "_players_by_id", lambda ids: {i: pool[i] for i in ids})
    monkeypatch.setattr(api, "_verdict",
                        lambda delta, summary, give, get: "Decline — you lose assists.")
    from fastapi.testclient import TestClient
    r = TestClient(api.app).post("/trade/analyze",
                                 json={"give": ["1"], "get": ["2"]})
    body = r.json()
    assert body["delta"]["AST"] == -6.0
    assert "assists" in body["verdict"].lower()
    assert body["summary"]["worsened"] == ["AST"]
```

- [ ] **Step 5: Implement the endpoint** in `api.py`

```python
from fantasy_gm import trade

class TradeRequest(BaseModel):
    give: list[str]
    get: list[str]

def _players_by_id(ids: list[str]) -> dict:
    idx = {p.player_id: p for t in _all_teams() for p in t.players}
    idx.update({p.player_id: p for p in _free_agents()})
    return {i: idx[i] for i in ids if i in idx}

def _verdict(delta, summary, give, get) -> str:
    """Single focused Claude call grounded in the computed deltas."""
    model = _make_model()
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

@app.post("/trade/analyze")
def trade_analyze(req: TradeRequest) -> dict:
    cats = _league_cats()
    byid = _players_by_id(req.give + req.get)
    give = [byid[i] for i in req.give if i in byid]
    get = [byid[i] for i in req.get if i in byid]
    delta = trade.category_delta(give, get, cats)
    summary = trade.summarize(delta)
    verdict = _verdict(delta, summary, give, get)
    rec = ("ACCEPT" if "ACCEPT" in verdict else
           "COUNTER" if "COUNTER" in verdict else "DECLINE")
    return {"delta": delta, "summary": summary, "verdict": verdict,
            "recommendation": rec}
```

- [ ] **Step 6: Run all backend tests, confirm pass**; ruff clean. **Step 7: Commit**

```bash
git add src/fantasy_gm/trade.py src/fantasy_gm/api.py tests/test_trade.py tests/test_api.py
git commit -m "feat: hybrid trade analyzer — category delta math + LLM verdict"
```

---

## Task F1: Router, nav, and view extraction

**Files:** `cd frontend && npm install react-router-dom`; Create `frontend/src/components/Nav.tsx`, `frontend/src/views/ChatView.tsx`; Modify `frontend/src/App.tsx`; Test `frontend/src/__tests__/nav.test.tsx`

- [ ] **Step 1: Install** `npm install react-router-dom`

- [ ] **Step 2: Extract the current chat** — move everything in `App.tsx` except `<Header/>` into `views/ChatView.tsx` (a component with the same reducer + `postChatStream` logic and the `.list` + `<Composer/>` markup). `App.tsx` becomes the router shell.

- [ ] **Step 3: Write the failing nav test**

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Nav } from "../components/Nav";

it("renders three tabs with the active one marked", () => {
  render(<MemoryRouter initialEntries={["/dashboard"]}><Nav /></MemoryRouter>);
  expect(screen.getByRole("link", { name: /chat/i })).toBeInTheDocument();
  const dash = screen.getByRole("link", { name: /dashboard/i });
  expect(dash).toHaveAttribute("aria-current", "page");
});
```

- [ ] **Step 4: Run it, confirm fail**; **Step 5: Implement `Nav.tsx`**

```tsx
import { NavLink } from "react-router-dom";
const TABS = [{ to: "/", label: "Chat" }, { to: "/dashboard", label: "Dashboard" },
              { to: "/trade", label: "Trade" }];
export function Nav() {
  return (
    <nav className="nav">
      {TABS.map((t) => (
        <NavLink key={t.to} to={t.to} end
          className={({ isActive }) => "tab" + (isActive ? " active" : "")}
          aria-current={undefined /* NavLink sets it when active */}>
          {t.label}
        </NavLink>
      ))}
    </nav>
  );
}
```

(NavLink sets `aria-current="page"` automatically when active — the test relies on that.)

- [ ] **Step 6: Rewrite `App.tsx`** as the router shell

```tsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { useTheme } from "./hooks/useTheme";
import { Header } from "./components/Header";
import { Nav } from "./components/Nav";
import { ChatView } from "./views/ChatView";
import { DashboardView } from "./views/DashboardView";
import { TradeView } from "./views/TradeView";
import "./styles/tokens.css";
import "./styles/app.css";

export default function App() {
  const { theme, toggle } = useTheme();
  return (
    <BrowserRouter>
      <div className="app">
        <Header theme={theme} onToggle={toggle} />
        <Nav />
        <Routes>
          <Route path="/" element={<ChatView />} />
          <Route path="/dashboard" element={<DashboardView />} />
          <Route path="/trade" element={<TradeView />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
```

Add `.nav`/`.tab`/`.tab.active` styles to `app.css` (sticky under header; active tab uses `--primary` underline + `--text`, inactive `--muted`; 44px tall targets).

- [ ] **Step 7: Run the frontend suite** (the existing `app.test.tsx` may need wrapping in `<MemoryRouter>` or pointing at `ChatView`; update it to render `<ChatView/>` directly). Confirm green. **Step 8: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/Nav.tsx frontend/src/views/ChatView.tsx frontend/src/__tests__ frontend/package.json
git commit -m "feat(ui): router + top-tab navigation; extract ChatView"
```

---

## Task F2: API client + chart components

**Files:** Create `frontend/src/lib/api.ts`, the four chart components; Test `frontend/src/__tests__/charts.test.tsx`

- [ ] **Step 1: Write `frontend/src/lib/api.ts`**

```ts
import { API_BASE } from "./config";
export async function getDashboard() {
  const r = await fetch(`${API_BASE}/analytics/dashboard`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
export async function analyzeTrade(give: string[], get: string[]) {
  const r = await fetch(`${API_BASE}/trade/analyze`, {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ give, get }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
```

- [ ] **Step 2: Write the failing chart test** (render + data-shape, not pixels)

```tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { BarList } from "../components/charts/BarList";
import { DivergingList } from "../components/charts/DivergingList";

it("BarList renders a labeled row per item with a table fallback", () => {
  render(<BarList title="Streaming" items={[
    { label: "Josh Hart", value: 54, sub: "NYK · 4 gm" }]} />);
  expect(screen.getByText("Josh Hart")).toBeInTheDocument();
  expect(screen.getByRole("table")).toBeInTheDocument();
});
it("DivergingList colors buy-low vs sell-high", () => {
  render(<DivergingList items={[{ label: "X", value: -22, signal: "buy_low" }]} />);
  expect(screen.getByText(/buy low/i)).toBeInTheDocument();
});
```

- [ ] **Step 3: Implement the four chart components** (plain SVG/HTML, dataviz-compliant: thin marks, legend/labels, table fallback, token colors).

`frontend/src/components/charts/BarList.tsx` — horizontal magnitude bars (sequential blue), direct value labels, `<table>` fallback:
```tsx
export function BarList({ title, items }: {
  title: string; items: { label: string; value: number; sub?: string }[];
}) {
  const max = Math.max(1, ...items.map((i) => i.value));
  return (
    <figure className="chart">
      <figcaption>{title}</figcaption>
      <div className="barlist">
        {items.map((i) => (
          <div className="barrow" key={i.label}>
            <span className="blabel">{i.label}{i.sub && <em> {i.sub}</em>}</span>
            <span className="btrack">
              <span className="bfill" style={{ width: `${(i.value / max) * 100}%` }} />
            </span>
            <span className="bval">{i.value}</span>
          </div>
        ))}
      </div>
      <table className="sr-table">
        <caption>{title}</caption>
        <thead><tr><th>Player</th><th>Value</th></tr></thead>
        <tbody>{items.map((i) =>
          <tr key={i.label}><td>{i.label}</td><td>{i.value}</td></tr>)}</tbody>
      </table>
    </figure>
  );
}
```

`frontend/src/components/charts/DivergingList.tsx` — buy-low (accent) / sell-high (danger), neutral center, sign shows polarity + a text label (not color-alone):
```tsx
export function DivergingList({ items }: {
  items: { label: string; value: number; signal: "buy_low" | "sell_high" }[];
}) {
  return (
    <figure className="chart">
      <figcaption>Buy-low / Sell-high (14-day vs season)</figcaption>
      <ul className="diverging">
        {items.map((i) => (
          <li key={i.label} className={i.signal}>
            <span>{i.label}</span>
            <span className="tag">{i.signal === "buy_low" ? "buy low" : "sell high"} · {i.value}%</span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
```

`frontend/src/components/charts/RadarChart.tsx` — 9-axis radar, two series (you=`--primary`, league=`--muted`), legend, table fallback. Compute axis points on a unit circle scaled by value/maxPerAxis:
```tsx
export function RadarChart({ cats, you, league }: {
  cats: string[]; you: number[]; league: number[];
}) {
  const N = cats.length, R = 90, cx = 110, cy = 110;
  const maxes = cats.map((_, i) => Math.max(1, you[i], league[i]));
  const pt = (i: number, v: number) => {
    const a = (Math.PI * 2 * i) / N - Math.PI / 2;
    const r = (v / maxes[i]) * R;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const poly = (vals: number[]) =>
    vals.map((v, i) => pt(i, v).join(",")).join(" ");
  return (
    <figure className="chart">
      <figcaption>Category profile — you vs league average</figcaption>
      <svg viewBox="0 0 220 240" width="100%" role="img"
           aria-label="Category strengths versus the league average">
        {[0.33, 0.66, 1].map((f) => (
          <circle key={f} cx={cx} cy={cy} r={R * f} className="radar-grid" />
        ))}
        {cats.map((c, i) => {
          const [x, y] = pt(i, maxes[i]);
          return <text key={c} x={x} y={y} className="radar-axis"
                       textAnchor="middle">{c}</text>;
        })}
        <polygon points={poly(league)} className="radar-league" />
        <polygon points={poly(you)} className="radar-you" />
      </svg>
      <div className="legend">
        <span><i className="sw you" /> You</span>
        <span><i className="sw league" /> League avg</span>
      </div>
    </figure>
  );
}
```

`frontend/src/components/charts/GamesHeatmap.tsx` — team grid, cell shaded by games (sequential blue ramp via opacity), number shown in-cell (not color-alone):
```tsx
export function GamesHeatmap({ games }: { games: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(games));
  const entries = Object.entries(games).sort((a, b) => b[1] - a[1]);
  return (
    <figure className="chart">
      <figcaption>Games this week</figcaption>
      <div className="heat">
        {entries.map(([team, g]) => (
          <div className="cell" key={team}
               style={{ background: `color-mix(in srgb, var(--primary) ${(g / max) * 100}%, transparent)` }}>
            <b>{team}</b><span>{g}</span>
          </div>
        ))}
      </div>
    </figure>
  );
}
```

Add chart styles to `app.css` (bars, diverging colors, radar strokes/fills at ~25% opacity, heat grid, `.sr-table { position:absolute; clip: rect(0 0 0 0); }` visually-hidden table, legend swatches). Run `dataviz/scripts/validate_palette.js "#2563EB,#64748B" --mode light` and `--mode dark` (dark surface `#0B1220`); if the pair FAILs separation, keep the shape/label secondary encodings (already present) — radar uses fill + legend + table, so identity is never color-alone.

- [ ] **Step 4: Run the chart tests, confirm pass**; **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/charts frontend/src/styles/app.css frontend/src/__tests__/charts.test.tsx
git commit -m "feat(ui): dataviz chart components (radar, bars, diverging, heatmap)"
```

---

## Task F3: Dashboard view

**Files:** Create `frontend/src/views/DashboardView.tsx`; Test `frontend/src/__tests__/dashboard.test.tsx`

- [ ] **Step 1: Write the failing test** (mock `getDashboard`)

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { DashboardView } from "../views/DashboardView";

it("renders the four sections from the payload", async () => {
  vi.spyOn(api, "getDashboard").mockResolvedValue({
    category_profile: { PTS: { you: 20, league_avg: 15 } },
    streaming_board: [{ player_id: "1", name: "Josh Hart", nba_team: "NYK",
                        games: 4, projected: { PTS: 54 }, score: 54 }],
    buy_low_sell_high: [{ player_id: "2", name: "X", delta_pct: -22, signal: "buy_low" }],
    schedule: { NYK: 4 },
  });
  render(<DashboardView />);
  expect(await screen.findByText("Josh Hart")).toBeInTheDocument();
  expect(screen.getByText(/category profile/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `DashboardView.tsx`** — fetch on mount, loading skeleton, error, then the four charts fed from the payload (shape `streaming_board` into `BarList` items, `category_profile` into radar arrays, etc.). Include a loading and error state.

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add frontend/src/views/DashboardView.tsx frontend/src/__tests__/dashboard.test.tsx
git commit -m "feat(ui): dashboard view wiring the four analytics charts"
```

---

## Task F4: Trade Analyzer view

**Files:** Create `frontend/src/views/TradeView.tsx`; Test `frontend/src/__tests__/trade.test.tsx`

- [ ] **Step 1: Write the failing test** (mock `getDashboard` for rosters or add a small teams fetch; mock `analyzeTrade`)

```tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { TradeView } from "../views/TradeView";

it("analyzes a trade and shows the verdict + deltas", async () => {
  vi.spyOn(api, "analyzeTrade").mockResolvedValue({
    delta: { AST: -6 }, summary: { improved: [], worsened: ["AST"] },
    verdict: "Decline — you lose assists. DECLINE", recommendation: "DECLINE",
  });
  render(<TradeView />);
  // (the view lets you type/select player ids; simplest: an input for give/get ids)
  await userEvent.type(screen.getByLabelText(/players to give/i), "1");
  await userEvent.type(screen.getByLabelText(/players to get/i), "2");
  await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
  expect(await screen.findByText(/DECLINE/)).toBeInTheDocument();
  expect(screen.getByText(/AST/)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `TradeView.tsx`** — v1 UX: two multi-select lists (your roster on the left, a team-picker + that team's roster on the right) populated from a small `/analytics/dashboard` or a dedicated teams fetch; selecting adds player ids to `give`/`get`. "Analyze" calls `analyzeTrade`, shows a **verdict card** (recommendation badge ACCEPT/DECLINE/COUNTER colored via status tokens + the narrative) and a **per-category delta table** (green/red by whether each cat improved, with a sign; TO note). Include loading + error states. (If roster-picker wiring is heavy, ship a simpler comma-separated id input first — the test uses labeled inputs — then enhance to pickers.)

- [ ] **Step 4: Run it, confirm pass**; **Step 5: Commit**

```bash
git add frontend/src/views/TradeView.tsx frontend/src/__tests__/trade.test.tsx
git commit -m "feat(ui): trade analyzer view — pickers, verdict card, category deltas"
```

---

## Task F5: Live check + QC

- [ ] Start both servers (`PYTHONPATH=src uv run uvicorn fantasy_gm.api:app --port 8000`; `cd frontend && npm run dev`) with `DEMO_MODE=true` + a real key. Re-seed if needed (`seed_demo_data.py`).
- [ ] Click through **Chat** (ask "propose a fair trade with Team 4"), **Dashboard** (all four charts render, dark mode OK, 375px), **Trade** (give/get a couple players → verdict + deltas).
- [ ] Run `design:design-critique` + `design:accessibility-review` on the new views; apply high-value fixes (chart contrast, tab focus/`aria-current`, verdict-badge not color-alone, table fallbacks present). Commit as `fix(ui): phase-4 design + a11y review`.

---

## Phase 4 Done — Definition of Done

- [ ] Backend `uv run pytest -v` green (demo, analytics, trade, dashboard/trade endpoints, agent tools).
- [ ] Frontend `npm test` + `npm run build` green (nav, charts, dashboard, trade).
- [ ] Live: three tabs work; dashboard shows real numbers from the 12-team demo league; trade analyzer returns a grounded verdict; chat can scout other teams.
- [ ] design-critique + accessibility-review run; fixes applied.
- [ ] README updated: new views + endpoints; palette validated for light + dark.

## Roadmap (unchanged, still gated)
- Deploy (Vercel + Railway) → live URL. Wire Intent-Analysis to live LangSmith. Swap demo → real Yahoo on approval (the 12-team generator is demo-only; real rosters come from `fetch_all_teams`).
