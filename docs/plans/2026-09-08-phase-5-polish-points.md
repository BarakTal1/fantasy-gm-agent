# Phase 5 — Personal-Use Polish + Points-League Support Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Make the two workflows the owner will actually rely on — **waivers/streaming** and **trade analysis** — genuinely trustworthy and pleasant to use on a phone, and make the whole value model **format-aware** so it works for a **points league** as well as a **category league**. No auth, no deploy this phase (deferred). Runs on demo data (both formats) until Yahoo approval; swaps to real data unchanged.

**Architecture:** A new `scoring.py` centralizes player valuation and branches on `LeagueSettings.format`: category leagues use per-category values (with need-weighting vs the owner's weak cats); points leagues use a single weighted **fantasy-points** value from the league's stat weights. `analytics.py` and `trade.py` consume `scoring` and return format-tagged payloads; endpoints expose `format` so the React views render the right thing (radar + category deltas for category; points value board + net-points for points). Trade picking becomes roster-aware dropdowns via a new `GET /league/teams`. Determinism boundary unchanged: all valuation/analytics/trade math is pure and unit-tested; the LLM trade verdict stays a single grounded call.

**Tech Stack:** unchanged (FastAPI + Postgres backend; Vite/React/TS frontend). No new deps.

---

## File Structure

```
demo_data/league_settings_points.json   # points-format demo league settings (stat weights)
src/fantasy_gm/config.py                 # (modify) DEMO_LEAGUE_FORMAT
src/fantasy_gm/schemas.py                # (modify) LeagueSettings.point_weights
src/fantasy_gm/demo.py                   # (modify) pick settings file by format
src/fantasy_gm/yahoo_client/client.py    # (modify) parse points stat_modifiers
src/fantasy_gm/scoring.py                # NEW — format-aware player valuation
src/fantasy_gm/analytics.py              # (modify) format branch + need-weighting
src/fantasy_gm/trade.py                  # (modify) points net-delta branch
src/fantasy_gm/api.py                    # (modify) /league/teams; format-aware payloads
frontend/src/lib/api.ts                  # (modify) getTeams()
frontend/src/views/TradeView.tsx         # (modify) dropdown pickers + format-aware result
frontend/src/views/DashboardView.tsx     # (modify) format-aware rendering + drop suggestions
frontend/src/components/PlayerPicker.tsx # NEW — reusable roster dropdown/multiselect
frontend/src/styles/app.css              # (modify) picker + mobile polish
```

---

## Task B1: League scoring model (format + weights)

**Files:** Modify `schemas.py`; Create `demo_data/league_settings_points.json`; Modify `config.py`, `demo.py`, `yahoo_client/client.py`; Test `tests/test_schemas.py`, `tests/test_demo.py`

- [ ] **Step 1: Add the failing test** (append to `tests/test_schemas.py`)

```python
def test_league_settings_points_format():
    from fantasy_gm.schemas import LeagueSettings
    s = LeagueSettings(league_key="k", format="points",
                       point_weights={"PTS": 1.0, "AST": 1.5})
    assert s.is_points is True
    assert s.is_category is False
    assert s.point_weights["AST"] == 1.5
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Extend `LeagueSettings`** in `schemas.py`

```python
    point_weights: dict[str, float] = Field(default_factory=dict)  # points leagues only

    @property
    def is_points(self) -> bool:
        return self.format == "points"
```

(`is_category` already exists.)

- [ ] **Step 4: Create `demo_data/league_settings_points.json`** — Yahoo-shaped, `scoring_type: "point"`, with `stat_modifiers` (the point values). Mirror the category fixture's structure but add a `stat_modifiers.stats` list:

```json
{
  "fantasy_content": {
    "league": [
      {"league_key": "428.l.222222", "name": "Points League", "scoring_type": "point",
       "current_week": 15, "season": "2025"},
      {"settings": [{
        "scoring_type": "point",
        "stat_categories": {"stats": [
          {"stat": {"stat_id": 12, "display_name": "PTS"}},
          {"stat": {"stat_id": 15, "display_name": "REB"}},
          {"stat": {"stat_id": 16, "display_name": "AST"}},
          {"stat": {"stat_id": 10, "display_name": "3PTM"}},
          {"stat": {"stat_id": 17, "display_name": "ST"}},
          {"stat": {"stat_id": 18, "display_name": "BLK"}},
          {"stat": {"stat_id": 19, "display_name": "TO"}}
        ]},
        "stat_modifiers": {"stats": [
          {"stat": {"stat_id": 12, "value": 1.0}},
          {"stat": {"stat_id": 15, "value": 1.2}},
          {"stat": {"stat_id": 16, "value": 1.5}},
          {"stat": {"stat_id": 10, "value": 0.5}},
          {"stat": {"stat_id": 17, "value": 3.0}},
          {"stat": {"stat_id": 18, "value": 3.0}},
          {"stat": {"stat_id": 19, "value": -1.0}}
        ]}
      }]}
    ]
  }
}
```

- [ ] **Step 5: Add `DEMO_LEAGUE_FORMAT`** to `config.py` Settings (default `"category"`):

```python
    demo_league_format: str = "category"   # "category" | "points"
```

- [ ] **Step 6: Update `demo.demo_league_settings()`** to pick the file + weights by format

```python
from fantasy_gm.config import get_settings

def demo_league_settings() -> LeagueSettings:
    fmt = get_settings().demo_league_format
    fixture = ("league_settings_points.json" if fmt == "points"
               else "league_settings.json")
    return client.parse_league_settings(_load(fixture))
```

- [ ] **Step 7: Extend `parse_league_settings`** in `client.py` to read `stat_modifiers` into `point_weights` when scoring is points. Map stat_id→display_name from `stat_categories`, then build `{display_name: value}`:

```python
    fmt = "points" if "point" in scoring else "category"
    weights = {}
    if fmt == "points":
        id_to_name = {str(c["stat"]["stat_id"]): c["stat"]["display_name"]
                      for c in settings.get("stat_categories", {}).get("stats", [])}
        for m in settings.get("stat_modifiers", {}).get("stats", []):
            sid = str(m["stat"]["stat_id"])
            if sid in id_to_name:
                weights[id_to_name[sid]] = float(m["stat"]["value"])
    return LeagueSettings(league_key=league_key, format=fmt, categories=categories,
                          point_weights=weights)
```

- [ ] **Step 8: Add a demo test** (append to `tests/test_demo.py`)

```python
def test_demo_points_settings(monkeypatch):
    from fantasy_gm.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_LEAGUE_FORMAT", "points")
    from fantasy_gm import demo
    s = demo.demo_league_settings()
    assert s.is_points
    assert s.point_weights["ST"] == 3.0
    get_settings.cache_clear()
```

- [ ] **Step 9: Run tests, confirm pass; ruff clean; Commit**

```bash
git add src/fantasy_gm/schemas.py src/fantasy_gm/config.py src/fantasy_gm/demo.py src/fantasy_gm/yahoo_client/client.py demo_data/league_settings_points.json tests/test_schemas.py tests/test_demo.py
git commit -m "feat: points-league scoring model (format + stat weights)"
```

---

## Task B2: `scoring.py` — format-aware valuation

**Files:** Create `src/fantasy_gm/scoring.py`; Test `tests/test_scoring.py`

Central valuation used by analytics + trade. Category leagues value per-category; points leagues collapse to one number.

- [ ] **Step 1: Write the failing test**

```python
from fantasy_gm.schemas import LeagueSettings, Player
from fantasy_gm.scoring import fantasy_points, player_value

def _p(**s): return Player(player_id="1", name="P", nba_team="LAL", stats=s)

def test_fantasy_points_weighted_sum():
    w = {"PTS": 1.0, "AST": 1.5, "TO": -1.0}
    assert fantasy_points({"PTS": 20, "AST": 4, "TO": 2}, w) == 24.0  # 20+6-2

def test_player_value_points_league_is_scalar():
    s = LeagueSettings(league_key="k", format="points",
                       point_weights={"PTS": 1.0, "AST": 1.5})
    v = player_value(_p(PTS=20, AST=4), s)
    assert v == 26.0  # scalar fantasy points

def test_player_value_category_league_excludes_turnovers_from_score():
    s = LeagueSettings(league_key="k", format="category",
                       categories=["PTS", "AST", "TO"])
    v = player_value(_p(PTS=20, AST=4, TO=3), s)
    assert v == 24.0  # counting-cat sum, TO excluded from the "more is better" score
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement `src/fantasy_gm/scoring.py`**

```python
from fantasy_gm.schemas import LeagueSettings, Player

# Categories where a lower value is better (excluded from "more is better" sums).
NEGATIVE_CATS = {"TO"}


def fantasy_points(stats: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(stats.get(c, 0.0) * w for c, w in weights.items()), 2)


def player_value(player: Player, settings: LeagueSettings) -> float:
    """A single comparable value for a player under this league's scoring.
    Points league: weighted fantasy points. Category league: sum of counting
    categories the player helps (turnovers excluded from the positive score)."""
    if settings.is_points:
        return fantasy_points(player.stats, settings.point_weights)
    return round(sum(player.stat(c) for c in settings.categories
                     if c not in NEGATIVE_CATS and not c.endswith("%")), 2)
```

- [ ] **Step 4: Run it, confirm pass; Commit**

```bash
git add src/fantasy_gm/scoring.py tests/test_scoring.py
git commit -m "feat: format-aware player valuation (points vs category)"
```

---

## Task B3: Format-aware analytics + need-weighted waivers

**Files:** Modify `src/fantasy_gm/analytics.py`; Test `tests/test_analytics.py`

Add: (a) **need weights** for category leagues (where is my team weak vs league), (b) a `recommended_pickups` that ranks free agents by *value that helps me* and pairs each with a suggested drop, (c) a points-league value board.

- [ ] **Step 1: Add failing tests** (append to `tests/test_analytics.py`)

```python
from fantasy_gm.analytics import recommended_pickups, points_value_board
from fantasy_gm.schemas import LeagueSettings

def _team(name, players): return Team(team_key=name, name=name, players=players)

def test_recommended_pickups_category_prefers_my_weak_cats(monkeypatch):
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("Mine", [_p("1", PTS=30, AST=1)])          # strong PTS, weak AST
    league = [mine, _team("Rival", [_p("2", PTS=10, AST=9)])]
    fas = [_p("A", PTS=0, AST=8), _p("B", PTS=10, AST=0)]    # A helps my weak AST
    trends = {"A": {"PTS": 0, "AST": 8}, "B": {"PTS": 10, "AST": 0}}
    games = {"LAL": 3}
    recs = recommended_pickups(mine, league, fas, trends, games, cat)
    assert recs[0]["player_id"] == "A"                       # need-weighting favors A
    assert "drop" in recs[0]                                  # suggests a drop

def test_points_value_board_ranks_by_projected_points():
    pts = LeagueSettings(league_key="k", format="points",
                         point_weights={"PTS": 1.0})
    fas = [_p("A", PTS=10), _p("B", PTS=20)]
    trends = {"A": {"PTS": 10}, "B": {"PTS": 20}}
    board = points_value_board(fas, trends, {"LAL": 4}, pts)
    assert board[0]["player_id"] == "B"
    assert board[0]["projected_points"] == 80.0  # 20 * 4
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement in `analytics.py`**

```python
from fantasy_gm.schemas import LeagueSettings
from fantasy_gm import scoring


def _need_weights(my_team, all_teams, cats):
    """1.0 baseline; >1 for categories where my team trails the league average."""
    prof = category_profile(my_team, all_teams, cats)
    w = {}
    for c in cats:
        if c.endswith("%") or c == "TO":
            w[c] = 1.0
            continue
        you, avg = prof[c]["you"], prof[c]["league_avg"] or 1.0
        w[c] = 1.0 + max(0.0, (avg - you) / avg)   # weak cat -> weight > 1
    return w


def _weakest(players, settings) -> dict | None:
    if not players:
        return None
    worst = min(players, key=lambda p: scoring.player_value(p, settings))
    return {"player_id": worst.player_id, "name": worst.name,
            "value": scoring.player_value(worst, settings)}


def recommended_pickups(my_team, all_teams, free_agents, trends, games,
                        settings: LeagueSettings, limit: int = 12) -> list[dict]:
    """Rank FAs by value-that-helps-me x games this week; pair with a drop."""
    drop = _weakest(my_team.players, settings)
    weights = (_need_weights(my_team, all_teams, settings.categories)
               if settings.is_category else None)
    rows = []
    for p in free_agents:
        form = trends.get(p.player_id) or dict(p.stats)
        g = games.get(p.nba_team, 0)
        if settings.is_points:
            score = scoring.fantasy_points(form, settings.point_weights) * g
        else:
            score = sum(form.get(c, 0.0) * weights[c] * g
                        for c in settings.categories
                        if c not in scoring.NEGATIVE_CATS and not c.endswith("%"))
        rows.append({"player_id": p.player_id, "name": p.name, "nba_team": p.nba_team,
                     "games": g, "score": round(score, 1), "drop": drop})
    # Refinement to validate in the F4 live check: normalize each category by its
    # league-average scale before applying the need weight, so raw magnitude (a big
    # PTS number) doesn't drown out help in a weak category.
    return sorted(rows, key=lambda r: r["score"], reverse=True)[:limit]


def points_value_board(free_agents, trends, games, settings: LeagueSettings,
                       limit: int = 12) -> list[dict]:
    rows = []
    for p in free_agents:
        form = trends.get(p.player_id) or dict(p.stats)
        g = games.get(p.nba_team, 0)
        rows.append({"player_id": p.player_id, "name": p.name, "nba_team": p.nba_team,
                     "games": g,
                     "projected_points": round(
                         scoring.fantasy_points(form, settings.point_weights) * g, 1)})
    return sorted(rows, key=lambda r: r["projected_points"], reverse=True)[:limit]
```

- [ ] **Step 4: Run tests, confirm pass; Commit**

```bash
git add src/fantasy_gm/analytics.py tests/test_analytics.py
git commit -m "feat: need-weighted waiver recs + points value board"
```

---

## Task B4: Format-aware trade engine

**Files:** Modify `src/fantasy_gm/trade.py`; Test `tests/test_trade.py`

- [ ] **Step 1: Add the failing test** (append to `tests/test_trade.py`)

```python
from fantasy_gm.trade import points_delta
from fantasy_gm.schemas import LeagueSettings

def test_points_delta_net_fantasy_points():
    s = LeagueSettings(league_key="k", format="points",
                       point_weights={"PTS": 1.0, "AST": 1.5})
    give = [_p("1", PTS=10, AST=2)]   # value 13
    get = [_p("2", PTS=20, AST=0)]    # value 20
    d = points_delta(give, get, s)
    assert d["net"] == 7.0
    assert d["give_value"] == 13.0 and d["get_value"] == 20.0
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement in `trade.py`**

```python
from fantasy_gm.schemas import LeagueSettings
from fantasy_gm import scoring


def points_delta(give, get, settings: LeagueSettings) -> dict:
    gv = round(sum(scoring.fantasy_points(p.stats, settings.point_weights)
                   for p in give), 2)
    tv = round(sum(scoring.fantasy_points(p.stats, settings.point_weights)
                   for p in get), 2)
    return {"give_value": gv, "get_value": tv, "net": round(tv - gv, 2)}
```

- [ ] **Step 4: Run tests, confirm pass; Commit**

```bash
git add src/fantasy_gm/trade.py tests/test_trade.py
git commit -m "feat: points-league net-value trade delta"
```

---

## Task B5: Endpoints — `/league/teams` + format-aware dashboard & trade

**Files:** Modify `src/fantasy_gm/api.py`; Test `tests/test_api.py`

- [ ] **Step 1: Add failing tests** (append to `tests/test_api.py`)

```python
def test_league_teams_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player, Team
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key="428.l.1.t.1", name="Mine",
             players=[Player(player_id="1", name="A", nba_team="LAL", stats={"PTS": 20})])])
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/league/teams").json()
    assert body["my_team_key"] == api.MY_TEAM_KEY
    assert body["teams"][0]["players"][0]["name"] == "A"

def test_dashboard_is_format_tagged(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_load_league",
        lambda: LeagueSettings(league_key="k", format="points",
                               point_weights={"PTS": 1.0}))
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="1", name="A", nba_team="LAL", stats={"PTS": 20})])])
    monkeypatch.setattr(api, "_free_agents", lambda: [
        Player(player_id="9", name="FA", nba_team="LAL", stats={"PTS": 15})])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})
    from fastapi.testclient import TestClient
    body = TestClient(api.app).get("/analytics/dashboard").json()
    assert body["format"] == "points"
    assert "points_value_board" in body            # points view, not radar
```

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Implement in `api.py`**

Add `/league/teams`:
```python
@app.get("/league/teams")
def league_teams() -> dict:
    return {"my_team_key": MY_TEAM_KEY,
            "teams": [t.model_dump() for t in _all_teams()]}
```

Make `dashboard()` branch on format — reuse `_all_teams/_free_agents/_trends_for/_week_games`, then:
```python
@app.get("/analytics/dashboard")
def dashboard() -> dict:
    league = _load_league()
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    fas = _free_agents()
    games = _week_games()
    fa_trends = _trends_for([p.player_id for p in fas])
    roster_trends = _trends_for([p.player_id for p in mine.players])
    common = {
        "format": league.format,
        "schedule": games,
        "recommended_pickups": analytics.recommended_pickups(
            mine, teams, fas, fa_trends, games, league),
        "buy_low_sell_high": analytics.buy_low_sell_high(
            mine.players + fas, {**roster_trends, **fa_trends}, league.categories)[:12]
        if league.is_category else [],
    }
    if league.is_points:
        common["points_value_board"] = analytics.points_value_board(
            fas, fa_trends, games, league)
    else:
        common["category_profile"] = analytics.category_profile(
            mine, teams, league.categories)
        common["streaming_board"] = analytics.streaming_board(
            fas, fa_trends, games, league.categories)[:12]
    return common
```

Make `trade_analyze()` branch: category → existing `category_delta`+`summarize`; points → `points_delta`. Return `{"format": league.format, ...}` and a format-appropriate `_verdict` prompt (net points vs category deltas). Keep `_verdict` monkeypatchable.

- [ ] **Step 4: Update the existing dashboard/trade tests** if the payload keys shifted (category path still returns `category_profile`/`streaming_board`; the older `test_dashboard_endpoint_returns_all_sections` should assert against the category branch and now also `recommended_pickups`). Run full suite green; ruff clean.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat: /league/teams + format-aware dashboard & trade payloads"
```

---

## Task F1: Reusable PlayerPicker + Trade dropdowns

**Files:** Create `frontend/src/components/PlayerPicker.tsx`; Modify `frontend/src/lib/api.ts`, `frontend/src/views/TradeView.tsx`; Test `frontend/src/__tests__/trade.test.tsx`

- [ ] **Step 1: Add `getTeams()` to `lib/api.ts`**

```ts
export async function getTeams() {
  const r = await fetch(`${API_BASE}/league/teams`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<{ my_team_key: string; teams: Team[] }>;
}
```
(Define a `Team`/`Player` TS type in `lib/api.ts` matching the payload.)

- [ ] **Step 2: Update the trade test** to the picker UX (mock `getTeams` + `analyzeTrade`)

```tsx
it("picks players from rosters and shows a verdict", async () => {
  vi.spyOn(api, "getTeams").mockResolvedValue({
    my_team_key: "t1",
    teams: [
      { team_key: "t1", name: "Mine",
        players: [{ player_id: "1", name: "My Star", nba_team: "LAL", stats: {} }] },
      { team_key: "t2", name: "Rival",
        players: [{ player_id: "2", name: "Their Star", nba_team: "BOS", stats: {} }] },
    ],
  });
  vi.spyOn(api, "analyzeTrade").mockResolvedValue({
    format: "category", delta: { AST: -6 }, summary: { improved: [], worsened: ["AST"] },
    verdict: "You lose assists.", recommendation: "DECLINE",
  });
  render(<TradeView />);
  // select my player, opponent, their player via the pickers, then analyze
  await userEvent.click(await screen.findByRole("button", { name: /my star/i }));
  await userEvent.selectOptions(screen.getByLabelText(/opponent team/i), "t2");
  await userEvent.click(await screen.findByRole("button", { name: /their star/i }));
  await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
  expect(await screen.findByText(/DECLINE/)).toBeInTheDocument();
});
```

- [ ] **Step 3: Run it, confirm fail**; **Step 4: Implement `PlayerPicker.tsx`** — a labeled list of a roster's players as toggle buttons (tap to add/remove; selected state highlighted; 44px targets). Props: `{ label, players, selected, onToggle }`. Include an `<select>` for the opponent-team choice in TradeView.

- [ ] **Step 5: Rewrite `TradeView.tsx`** — on mount `getTeams()`; show **your roster** picker (give) and an **opponent `<select>`** that populates the opponent roster picker (get); selected players render as cards; "Analyze" calls `analyzeTrade(give, get)`; render the result **format-aware**: category → per-category delta table (green/red, TO inverted) + verdict badge; points → give/get/net fantasy-points + verdict badge. Loading + error + empty states.

- [ ] **Step 6: Run it, confirm pass; build; Commit**

```bash
git add frontend/src/components/PlayerPicker.tsx frontend/src/lib/api.ts frontend/src/views/TradeView.tsx frontend/src/__tests__/trade.test.tsx
git commit -m "feat(ui): roster-aware trade pickers + format-aware verdict"
```

---

## Task F2: Format-aware dashboard + drop suggestions

**Files:** Modify `frontend/src/views/DashboardView.tsx`; Test `frontend/src/__tests__/dashboard.test.tsx`

- [ ] **Step 1: Update the dashboard test** to cover both branches — category payload still renders the radar; a points payload (`format: "points"`, `points_value_board`) renders a points board and NOT the radar. Add a case asserting a **recommended-pickup row shows its suggested drop**.

- [ ] **Step 2: Run it, confirm fail**; **Step 3: Update `DashboardView.tsx`** — read `payload.format`:
  - **category**: RadarChart (category profile) + a **Recommended pickups** list (from `recommended_pickups`, each row "add X · drop Y") replacing/augmenting the raw streaming board + DivergingList (buy/sell) + GamesHeatmap.
  - **points**: a **points value board** (BarList of `projected_points`) + Recommended pickups + GamesHeatmap. No radar, no category buy/sell.
  - Loading/error/empty states throughout.

- [ ] **Step 4: Run it, confirm pass; build; Commit**

```bash
git add frontend/src/views/DashboardView.tsx frontend/src/__tests__/dashboard.test.tsx
git commit -m "feat(ui): format-aware dashboard + recommended pickups with drops"
```

---

## Task F3: Mobile polish + states pass

**Files:** Modify `frontend/src/styles/app.css` (+ small view tweaks)

- [ ] **Step 1:** Resize checks at 375px for: nav tabs (wrap/scroll, not overflow), chat stat tables (`overflow-x:auto` inside the bubble), tool-chip row wrap, the trade pickers (rosters scroll, buttons ≥44px, opponent select full-width), dashboard charts (radar `max-width:100%`, bar rows readable, heatmap grid reflows to fewer columns).
- [ ] **Step 2:** Ensure every async view (dashboard, trade) has a **loading skeleton**, an **error state with retry**, and an **empty state** ("no recommendations / pick players to analyze").
- [ ] **Step 3:** Run `npm run build` + `npm test` green. **Commit** `fix(ui): mobile polish + loading/error/empty states`.

---

## Task F4: Live check + QC

- [ ] Start both servers (`PYTHONPATH=src uv run uvicorn fantasy_gm.api:app --port 8000`; `cd frontend && npm run dev`), `DEMO_MODE=true`, real key. Re-seed if needed.
- [ ] **Category run** (`DEMO_LEAGUE_FORMAT=category`): dashboard shows radar + recommended pickups (add/drop); trade pickers → per-category verdict. Test on 375px.
- [ ] **Points run** (`DEMO_LEAGUE_FORMAT=points`, restart backend): dashboard shows points value board (no radar); trade pickers → net-points verdict. Test on 375px.
- [ ] Run `design:design-critique` + `design:accessibility-review` on the trade + dashboard views; apply high-value fixes. Commit `fix(ui): phase-5 design + a11y review`.

---

## Phase 5 Done — Definition of Done

- [ ] Backend `uv run pytest -v` green (scoring, analytics both formats, trade both formats, endpoints).
- [ ] Frontend `npm test` + `npm run build` green.
- [ ] Live: category league and points league both render correct dashboard + trade results; trade uses dropdown pickers; waiver recs show add + suggested drop; both usable at 375px.
- [ ] design-critique + accessibility-review applied.

## Deferred (not this phase)
- Auth/private gate and deploy (revisit when going live on a phone).
- Real Yahoo data swap on approval (parsers already parse `stat_modifiers`; validate against a real points and a real category response when access lands).
- Intent-Analysis loop.
