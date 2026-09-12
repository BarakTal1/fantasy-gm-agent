# Phase 8 — Received Trades, Suggested Trades & 5-Tab UI Reorg Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a research-grounded buy-low/sell-high engine, a received-trades inbox, a deterministic suggested-trades generator, split the dashboard into subject-scoped analytics endpoints, reorganize the UI into 5 tabs (Chat · My Team · Waivers · Trade · League), and re-theme from amber to turquoise/green/yellow.

**Architecture:** Backend stays pure-function + demo-shell/live-gated (same pattern as `trades_history` and `yahoo_client`). Two new modules (`proposals.py`, `received_trades.py`) and an upgraded `analytics.buy_low_sell_high`. New GET endpoints reuse the existing `POST /trade/analyze` verdict engine for on-demand Claude analysis. Frontend relocates existing chart components into new views and adds a shared Analyze component; the theme is a single-file CSS-token swap.

**Tech Stack:** Existing — Python 3 / FastAPI / pydantic / pytest (backend); Vite + React + TS / Vitest + Testing Library (frontend). No new dependencies.

**Design doc:** [docs/plans/2026-09-12-phase-8-trade-features-ui-reorg-design.md](2026-09-12-phase-8-trade-features-ui-reorg-design.md)

**Run commands:** backend `uv run pytest <path> -q`; frontend `npm test -- <path>` (run inside `frontend/`). Lint: `uv run ruff check src tests`.

---

## File Structure

**Backend**
- Modify `src/fantasy_gm/analytics.py` — replace `buy_low_sell_high` with the efficiency/volume split; add helpers.
- Create `src/fantasy_gm/proposals.py` — deterministic suggested-trades generator.
- Create `src/fantasy_gm/received_trades.py` — map pending-offer fixtures/live data to resolved player objects.
- Modify `src/fantasy_gm/yahoo_client/client.py` — add live-gated `parse_pending_trades` / `fetch_pending_trades`.
- Modify `src/fantasy_gm/api.py` — new endpoints (`/trades/received`, `/trades/suggestions`, `/analytics/my-team`, `/analytics/waivers`, `/analytics/league`); remove `/analytics/dashboard`.
- Create `demo_data/pending_trades.json` — received-offer fixture.
- Tests: modify `tests/test_analytics.py`, `tests/test_api.py`; create `tests/test_proposals.py`, `tests/test_received_trades.py`; add a client test in `tests/test_client.py`.

**Frontend** (under `frontend/`)
- Modify `src/styles/tokens.css` (theme) and comment-only touch-ups in `src/styles/app.css`.
- Modify `src/lib/api.ts` — add `getReceivedTrades`, `getTradeSuggestions`, `getMyTeamAnalytics`, `getWaiversAnalytics`, `getLeagueAnalytics`, types; remove `getDashboard`.
- Modify `src/components/Nav.tsx` and `src/App.tsx` — 5 tabs/routes.
- Create `src/components/AnalyzeTrade.tsx` — shared deterministic-card → Claude-verdict flow.
- Create `src/views/MyTeamView.tsx`, `src/views/WaiversView.tsx`, `src/views/LeagueView.tsx`.
- Modify `src/views/TradeView.tsx` — add Received + Suggested sections + embed history.
- Delete `src/views/DashboardView.tsx` (content relocated).
- Tests: modify `src/__tests__/nav.test.tsx`, delete/replace `src/__tests__/dashboard.test.tsx`; create view tests for the three new views and the expanded Trade tab.

---

## PHASE 1 — Backend trade features

### Task 1: Research-grounded `buy_low_sell_high`

**Files:**
- Modify: `src/fantasy_gm/analytics.py`
- Test: `tests/test_analytics.py`

- [ ] **Step 1: Replace the existing `test_buy_low_sell_high_flags_divergence` and add new cases** in `tests/test_analytics.py`

Replace the old test (lines ~42-46) with these:

```python
def test_buy_low_volume_only_league_flags_cold_form():
    # No percentage cats: classification falls back to volume divergence.
    players = [_p("1", PTS=20)]
    trends = {"1": {"PTS": 10.0}}          # -50% vs season -> buy_low
    res = buy_low_sell_high(players, trends, cats=["PTS"])
    assert res and res[0]["signal"] == "buy_low"
    assert res[0]["efficiency_delta"] is None
    assert res[0]["drivers"] == ["PTS below season"]


def test_sell_high_on_hot_shooting():
    players = [_p("1", **{"FG%": 0.40, "PTS": 20})]
    trends = {"1": {"FG%": 0.55, "PTS": 21}}   # +15 FG pts -> regression risk
    res = buy_low_sell_high(players, trends, cats=["FG%", "PTS"])
    assert res and res[0]["signal"] == "sell_high"
    assert res[0]["efficiency_delta"] > 0


def test_buy_low_rejected_when_volume_collapsed():
    # Cold shooting but counting volume also cratered -> opportunity gone, no buy.
    players = [_p("1", **{"FG%": 0.50, "PTS": 20})]
    trends = {"1": {"FG%": 0.40, "PTS": 8}}    # FG cold AND PTS -60%
    res = buy_low_sell_high(players, trends, cats=["FG%", "PTS"])
    assert res == []


def test_confidence_dampens_low_sample():
    players = [_p("1", PTS=20)]
    trends = {"1": {"PTS": 10.0}}
    hi = buy_low_sell_high(players, trends, cats=["PTS"], games={"1": 40})
    lo = buy_low_sell_high(players, trends, cats=["PTS"], games={"1": 5})
    assert hi[0]["strength"] > lo[0]["strength"]
    assert hi[0]["confidence"] == 1.0 and lo[0]["confidence"] == 0.6
```

- [ ] **Step 2: Run the tests, confirm they fail**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: failures (new output keys/params don't exist yet; `test_buy_low_rejected_when_volume_collapsed` etc.).

- [ ] **Step 3: Replace `buy_low_sell_high` in `analytics.py`**

Delete the current `buy_low_sell_high` (lines ~41-57) and insert this block (keep the existing `from fantasy_gm import scoring` import at the top of the file):

```python
# --- Buy-low / sell-high (research-grounded) ---
# Pro analysts (RotoWire, Athlon, Fantasy Analytics Authority, ESPN, Dunkest)
# key on: (1) EFFICIENCY regression toward baseline as the primary signal — a
# FG% sitting >~4 points above career mean ≈ regression/sell risk, well below ≈
# bounce-back/buy; (2) OPPORTUNITY (minutes/usage) must be intact for a buy-low;
# (3) SAMPLE SIZE — under ~20 games counting stats swing ±15-20%, ~30 games is
# stable, and STL/BLK stay high-variance. We lack career means / usage / minutes
# in demo, so: baseline = season stats, current = recent-form trend, "opportunity
# intact" is proxied by "counting volume hasn't collapsed", and a confidence
# multiplier uses games-played when the live feed supplies it.
# LIVE-DATA UPGRADES (flip on with real Yahoo stats): multi-year career mean as
# the regression baseline; true usage-rate + minutes for opportunity; real
# games-played feeding confidence.
SHOOTING_SPREAD = 0.05    # ~5 FG% points ≈ one unit of divergence (≈ the 4-pt anchor)
MIN_BASE = 1.0            # floor for counting baselines (avoid /0 and tiny-base blowups)
SIGNAL_THRESHOLD = 0.5    # min |normalized divergence| to flag
VOL_FLOOR = 0.5           # buy-low requires volume not down more than this (opportunity)
W_EFF = 0.7               # efficiency weight (primary)
W_VOL = 0.3               # volume weight (secondary)
STL_BLK_WEIGHT = 0.5      # down-weight high-variance defensive cats
_EFF_EXTRA = {"3PM"}      # shooting-proxy counting cat folded into efficiency


def _is_pct(cat: str) -> bool:
    return cat.endswith("%")


def _divergence(recent: float, season: float, cat: str) -> float:
    if _is_pct(cat):
        return (recent - season) / SHOOTING_SPREAD
    return (recent - season) / max(abs(season), MIN_BASE)


def _confidence(games: int | None) -> float:
    if games is None:
        return 0.8            # demo default (medium) — no games-played available
    if games < 20:
        return 0.6
    if games < 30:
        return 0.8
    return 1.0


def _drivers(p: Player, form: dict, ordered_cats: list[str], signal: str) -> list[str]:
    """Top-2 categories moving the signal, as human-readable strings."""
    scored = []
    for c in ordered_cats:
        dv = _divergence(form.get(c, p.stat(c)), p.stat(c), c)
        above = dv > 0
        # sell_high cares about cats above season; buy_low about cats below.
        # For TO, "below season" (fewer turnovers) reads as an improvement, but
        # for driver wording we report raw direction consistently.
        relevant = above if signal == "sell_high" else not above
        if relevant and dv != 0:
            scored.append((abs(dv), c, "above" if above else "below"))
    scored.sort(reverse=True)
    return [f"{c} {word} season" for _, c, word in scored[:2]]


def buy_low_sell_high(players: list[Player], trends: dict[str, dict],
                      cats: list[str], games: dict[str, int] | None = None) -> list[dict]:
    """Flag buy-low / sell-high via an efficiency-vs-volume split.

    `games` (optional) maps player_id -> games in the trend window, used only for
    the sample-size confidence multiplier. Returns rows sorted by strength desc.
    """
    games = games or {}
    eff_cats = [c for c in cats if _is_pct(c) or c in _EFF_EXTRA]
    vol_cats = [c for c in cats if c not in eff_cats]
    out = []
    for p in players:
        form = trends.get(p.player_id)
        if not form:
            continue

        def d(c: str) -> float:
            return _divergence(form.get(c, p.stat(c)), p.stat(c), c)

        eff = (sum(d(c) for c in eff_cats) / len(eff_cats)) if eff_cats else None
        vnum = vden = 0.0
        for c in vol_cats:
            w = STL_BLK_WEIGHT if c in ("STL", "BLK") else 1.0
            contrib = -d(c) if c in scoring.NEGATIVE_CATS else d(c)
            vnum += w * contrib
            vden += w
        vol = (vnum / vden) if vden else 0.0
        primary = eff if eff is not None else vol
        conf = _confidence(games.get(p.player_id))

        if primary >= SIGNAL_THRESHOLD:
            signal = "sell_high"
            strength = (conf * (W_EFF * max(eff or 0.0, 0.0) + W_VOL * max(vol, 0.0))
                        if eff_cats else conf * abs(vol))
        elif primary <= -SIGNAL_THRESHOLD:
            if eff_cats and vol < -VOL_FLOOR:
                continue                      # opportunity collapsed -> don't buy
            signal = "buy_low"
            strength = (conf * (W_EFF * abs(eff or 0.0) + W_VOL * abs(min(vol, 0.0)))
                        if eff_cats else conf * abs(vol))
        else:
            continue

        out.append({
            "player_id": p.player_id, "name": p.name, "nba_team": p.nba_team,
            "signal": signal, "strength": round(strength, 3),
            "efficiency_delta": round(eff, 3) if eff is not None else None,
            "volume_delta": round(vol, 3), "confidence": conf,
            "drivers": _drivers(p, form, eff_cats + vol_cats, signal),
        })
    return sorted(out, key=lambda r: r["strength"], reverse=True)
```

- [ ] **Step 4: Run the analytics tests, confirm they pass**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): research-grounded buy-low/sell-high (efficiency vs volume split)"
```

---

### Task 2: Suggested trades — category leagues (`proposals.py`)

**Files:**
- Create: `src/fantasy_gm/proposals.py`
- Test: `tests/test_proposals.py`

- [ ] **Step 1: Write the failing test** `tests/test_proposals.py`

```python
from fantasy_gm import proposals
from fantasy_gm.schemas import LeagueSettings, Player, Team


def _p(pid, **stats):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=stats)


def _team(key, name, players):
    return Team(team_key=key, name=name, players=players)


def test_category_suggestion_targets_my_weak_category():
    # I'm strong PTS, weak AST. A rival has a cold (buy-low) AST player, and I
    # hold a mid-value asset whose value is close enough to pass fairness.
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("t1", "Mine", [_p("m1", PTS=20, AST=2), _p("m2", PTS=12, AST=3)])
    rival = _team("t2", "Rival", [_p("r1", PTS=6, AST=11)])   # season value ~17
    league = [mine, rival]
    # Rival's dimer is cold across the board lately -> buy_low (both cats ~-0.5).
    trends = {"r1": {"PTS": 3, "AST": 5}}
    out = proposals.suggest_trades(mine, league, trends, cat)
    assert out, "expected at least one proposal"
    top = out[0]
    assert top["with_team"] == "Rival"
    assert "r1" in [p["player_id"] for p in top["get"]]
    assert "AST" in top["targeted_categories"]
    assert top["need_fit"] > 0
    assert top["fairness_gap"] >= 0


def test_packages_capped_at_two_per_side():
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("t1", "Mine",
                 [_p("m1", PTS=20, AST=2), _p("m2", PTS=12, AST=3), _p("m3", PTS=10, AST=4)])
    rival = _team("t2", "Rival", [_p("r1", PTS=6, AST=11), _p("r2", PTS=5, AST=9)])
    league = [mine, rival]
    trends = {"r1": {"PTS": 3, "AST": 5}, "r2": {"PTS": 2, "AST": 4}}
    out = proposals.suggest_trades(mine, league, trends, cat)
    assert out, "expected proposals to exercise the cap"
    for prop in out:
        assert 1 <= len(prop["give"]) <= 2
        assert 1 <= len(prop["get"]) <= 2


def test_no_suggestions_when_no_buy_low_targets():
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("t1", "Mine", [_p("m1", PTS=30, AST=1)])
    rival = _team("t2", "Rival", [_p("r1", PTS=20, AST=5)])
    trends = {}                                   # no trends -> nobody flagged buy_low
    out = proposals.suggest_trades(mine, [mine, rival], trends, cat)
    assert out == []
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `uv run pytest tests/test_proposals.py -q`
Expected: FAIL (`No module named 'fantasy_gm.proposals'`).

- [ ] **Step 3: Implement `src/fantasy_gm/proposals.py`**

```python
"""Deterministic suggested-trades generator.

Scans the league for packages the user could OFFER other teams: target their
buy-low players who fill the user's weak categories, give up the user's
sell-high / roster players, keep the value gap within a fairness tolerance so
the other side might plausibly accept, and rank by need-weighted fit. No Claude
at generation time — the frontend's Analyze button runs the existing verdict
engine on demand for a chosen proposal.
"""
import itertools

from fantasy_gm import scoring, trade
from fantasy_gm.analytics import _need_weights, buy_low_sell_high
from fantasy_gm.schemas import LeagueSettings, Player, Team

DEFAULT_LIMIT = 8
WEAK_EPS = 0.05        # need-weight above 1+this counts as a "weak" category
PKG_POOL = 6           # cap players considered per side before combining (bounds combos)
FAIRNESS_PCT = 0.25    # |value gap| must be within this fraction of the larger side
MIN_NEED_FIT = 0.01    # drop proposals that don't actually help a weak category


def _value(players: list[Player], settings: LeagueSettings) -> float:
    return sum(scoring.player_value(p, settings) for p in players)


def _weak_cats(weights: dict[str, float], cats: list[str]) -> list[str]:
    return [c for c in cats if not c.endswith("%")
            and c not in scoring.NEGATIVE_CATS and weights.get(c, 1.0) > 1 + WEAK_EPS]


def _need_fit(give: list[Player], get: list[Player],
              weights: dict[str, float], cats: list[str]) -> float:
    """Need-weighted positive improvement to my categories from the swap."""
    delta = trade.category_delta(give, get, cats)   # get - give, per cat
    fit = 0.0
    for c in cats:
        if c.endswith("%"):
            continue
        gain = -delta[c] if c in scoring.NEGATIVE_CATS else delta[c]
        if gain > 0:
            fit += gain * weights.get(c, 1.0)
    return fit


def _packages(assets: list[Player], targets: list[Player],
              settings: LeagueSettings) -> list[tuple[list[Player], list[Player]]]:
    assets = sorted(assets, key=lambda p: scoring.player_value(p, settings),
                    reverse=True)[:PKG_POOL]
    targets = sorted(targets, key=lambda p: scoring.player_value(p, settings),
                     reverse=True)[:PKG_POOL]
    out: list[tuple[list[Player], list[Player]]] = []
    for a in assets:
        for t in targets:
            out.append(([a], [t]))                              # 1-for-1
    for combo in itertools.combinations(assets, 2):
        for t in targets:
            out.append((list(combo), [t]))                      # 2-for-1
    for a in assets:
        for combo in itertools.combinations(targets, 2):
            out.append(([a], list(combo)))                      # 1-for-2
    return out


def _suggest_category(my_team: Team, all_teams: list[Team], trends: dict,
                      settings: LeagueSettings, limit: int) -> list[dict]:
    cats = settings.categories
    weights = _need_weights(my_team, all_teams, cats)
    weak = _weak_cats(weights, cats)
    # My tradeable assets: sell-high flagged players; fall back to the whole
    # roster when nothing is flagged, so a proposal is still possible.
    my_signals = {r["player_id"]: r for r in buy_low_sell_high(my_team.players, trends, cats)}
    assets = [p for p in my_team.players
              if my_signals.get(p.player_id, {}).get("signal") == "sell_high"]
    if not assets:
        assets = list(my_team.players)

    proposals_out: list[dict] = []
    seen: set[tuple] = set()
    for team in all_teams:
        if team.team_key == my_team.team_key:
            continue
        their_signals = {r["player_id"]: r
                         for r in buy_low_sell_high(team.players, trends, cats)}
        targets = [p for p in team.players
                   if their_signals.get(p.player_id, {}).get("signal") == "buy_low"
                   and (not weak or sum(p.stat(c) for c in weak) > 0)]
        for give, get in _packages(assets, targets, settings):
            key = (team.team_key,
                   tuple(sorted(p.player_id for p in give)),
                   tuple(sorted(p.player_id for p in get)))
            if key in seen:
                continue
            fit = _need_fit(give, get, weights, cats)
            if fit < MIN_NEED_FIT:
                continue
            gap = abs(_value(give, settings) - _value(get, settings))
            tol = max(_value(give, settings), _value(get, settings), 1.0) * FAIRNESS_PCT
            if gap > tol:
                continue
            seen.add(key)
            delta = trade.category_delta(give, get, cats)
            targeted = [c for c in weak
                        if (delta[c] > 0 if c not in scoring.NEGATIVE_CATS
                            else delta[c] < 0)]
            proposals_out.append({
                "with_team": team.name,
                "give": [p.model_dump() for p in give],
                "get": [p.model_dump() for p in get],
                "targeted_categories": targeted,
                "fairness_gap": round(gap, 2),
                "need_fit": round(fit, 2),
            })
    proposals_out.sort(key=lambda x: x["need_fit"], reverse=True)
    return proposals_out[:limit]


def suggest_trades(my_team: Team, all_teams: list[Team], trends: dict,
                   settings: LeagueSettings, limit: int = DEFAULT_LIMIT) -> list[dict]:
    if settings.is_points:
        from fantasy_gm.proposals_points import suggest_points   # Task 3
        return suggest_points(my_team, all_teams, trends, settings, limit)
    return _suggest_category(my_team, all_teams, trends, settings, limit)
```

- [ ] **Step 4: Run it, confirm category tests pass**

Run: `uv run pytest tests/test_proposals.py -q`
Expected: the three category tests PASS. (A points test is added in Task 3; the `proposals_points` import is only hit in points mode.)

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/proposals.py tests/test_proposals.py
git commit -m "feat(proposals): deterministic category-league suggested trades"
```

---

### Task 3: Suggested trades — points leagues

**Files:**
- Create: `src/fantasy_gm/proposals_points.py`
- Test: `tests/test_proposals.py` (append)

- [ ] **Step 1: Append the failing test** to `tests/test_proposals.py`

```python
def test_points_suggestion_is_net_positive_points():
    pts = LeagueSettings(league_key="k", format="points", categories=["PTS"],
                         point_weights={"PTS": 1.0})
    mine = _team("t1", "Mine", [_p("m1", PTS=18)])
    rival = _team("t2", "Rival", [_p("r1", PTS=22)])
    trends = {"r1": {"PTS": 11}}                 # rival star slumping -> buy_low
    out = proposals.suggest_trades(mine, [mine, rival], trends, pts)
    assert out, "expected a points proposal"
    assert out[0]["need_fit"] > 0               # projected points gained
    assert out[0]["with_team"] == "Rival"
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `uv run pytest tests/test_proposals.py::test_points_suggestion_is_net_positive_points -q`
Expected: FAIL (`No module named 'fantasy_gm.proposals_points'`).

- [ ] **Step 3: Implement `src/fantasy_gm/proposals_points.py`**

```python
"""Points-league variant of the suggested-trades generator.

Simpler than the category engine: target other teams' buy-low players whose
projected fantasy points beat what you give up, keep the value gap small, rank
by net projected points gained. Split into its own module so each file holds one
scoring regime.
"""
from fantasy_gm import scoring
from fantasy_gm.analytics import buy_low_sell_high
from fantasy_gm.proposals import FAIRNESS_PCT
from fantasy_gm.schemas import LeagueSettings, Player, Team


def _proj(p: Player, settings: LeagueSettings) -> float:
    # Project on SEASON stats, not the recent trend: the buy-low thesis is that a
    # slumping target regresses back up to its season baseline. `trends` is used
    # only to FLAG the target as buy-low (in suggest_points), not to value it.
    return scoring.fantasy_points(dict(p.stats), settings.point_weights)


def suggest_points(my_team: Team, all_teams: list[Team], trends: dict,
                   settings: LeagueSettings, limit: int) -> list[dict]:
    out: list[dict] = []
    for team in all_teams:
        if team.team_key == my_team.team_key:
            continue
        signals = {r["player_id"]: r
                   for r in buy_low_sell_high(team.players, trends, settings.categories)}
        targets = [p for p in team.players
                   if signals.get(p.player_id, {}).get("signal") == "buy_low"]
        for a in my_team.players:
            for t in targets:
                give_pts, get_pts = _proj(a, settings), _proj(t, settings)
                if get_pts <= give_pts:
                    continue
                gap = abs(scoring.player_value(a, settings)
                          - scoring.player_value(t, settings))
                tol = max(scoring.player_value(t, settings), 1.0) * FAIRNESS_PCT
                if gap > tol:
                    continue
                out.append({
                    "with_team": team.name,
                    "give": [a.model_dump()], "get": [t.model_dump()],
                    "targeted_categories": [],
                    "fairness_gap": round(gap, 2),
                    "need_fit": round(get_pts - give_pts, 2),
                })
    out.sort(key=lambda x: x["need_fit"], reverse=True)
    return out[:limit]
```

- [ ] **Step 4: Run the full proposals suite, confirm it passes**

Run: `uv run pytest tests/test_proposals.py -q`
Expected: PASS (all category + points tests).

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/proposals_points.py tests/test_proposals.py
git commit -m "feat(proposals): points-league suggested-trades variant"
```

---

### Task 4: Received trades module + demo fixture

**Files:**
- Create: `src/fantasy_gm/received_trades.py`
- Create: `demo_data/pending_trades.json`
- Test: `tests/test_received_trades.py`

- [ ] **Step 1: Write the failing test** `tests/test_received_trades.py`

```python
from fantasy_gm import received_trades
from fantasy_gm.schemas import Player


def _p(pid, name):
    return Player(player_id=pid, name=name, nba_team="LAL", stats={"PTS": 10.0})


def test_build_offers_resolves_players_and_direction():
    by_id = {"1626164": _p("1626164", "Booker"), "202681": _p("202681", "Kyrie")}
    raw = [{"from_team": "Team 2", "date": "2026-01-20", "note": "need scoring",
            "they_give": ["202681"], "they_want": ["1626164"]}]
    offers = received_trades.build_offers(raw, by_id)
    assert len(offers) == 1
    o = offers[0]
    assert o["from_team"] == "Team 2" and o["note"] == "need scoring"
    assert o["they_give"][0]["name"] == "Kyrie"       # offered TO me
    assert o["they_want"][0]["name"] == "Booker"      # my player they want


def test_build_offers_skips_unknown_ids():
    by_id = {"202681": _p("202681", "Kyrie")}
    raw = [{"from_team": "Team 2", "date": "2026-01-20",
            "they_give": ["202681"], "they_want": ["does-not-exist"]}]
    offers = received_trades.build_offers(raw, by_id)
    assert offers[0]["they_give"][0]["name"] == "Kyrie"
    assert offers[0]["they_want"] == []


def test_build_offers_empty():
    assert received_trades.build_offers([], {}) == []
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `uv run pytest tests/test_received_trades.py -q`
Expected: FAIL (`No module named 'fantasy_gm.received_trades'`).

- [ ] **Step 3: Implement `src/fantasy_gm/received_trades.py`**

```python
"""Received-trades (pending offers) shell.

Turns a list of pending offers other managers sent you into resolved player
objects for the UI. Demo mode reads demo_data/pending_trades.json; on Yahoo API
approval, the live parser in yahoo_client.client supplies the same offer shape.
Direction convention per offer: `they_give` = players offered TO you,
`they_want` = your players they're asking for.
"""


def _resolve(ids: list[str], by_id: dict) -> list[dict]:
    return [by_id[i].model_dump() for i in ids if i in by_id]


def build_offers(offers: list[dict], by_id: dict) -> list[dict]:
    return [{
        "from_team": o["from_team"],
        "date": o["date"],
        "note": o.get("note", ""),
        "they_give": _resolve(o.get("they_give", []), by_id),
        "they_want": _resolve(o.get("they_want", []), by_id),
    } for o in offers]
```

- [ ] **Step 4: Create `demo_data/pending_trades.json`** (ids verified present in the demo league)

```json
[
  {
    "from_team": "Team 2",
    "date": "2026-01-20",
    "note": "I need a scorer — Kyrie for Booker straight up.",
    "they_give": ["202681"],
    "they_want": ["1626164"]
  },
  {
    "from_team": "Team 3",
    "date": "2026-01-18",
    "note": "Buy-low on Fox? I'll send Jalen Johnson.",
    "they_give": ["1630552"],
    "they_want": ["1628368"]
  }
]
```

- [ ] **Step 5: Run the tests, confirm they pass**

Run: `uv run pytest tests/test_received_trades.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/received_trades.py demo_data/pending_trades.json tests/test_received_trades.py
git commit -m "feat(received-trades): pending-offer shell + demo fixture"
```

---

### Task 5: Live-gated Yahoo pending-trade parser

**Files:**
- Modify: `src/fantasy_gm/yahoo_client/client.py`
- Create: `tests/fixtures/pending_trades_yahoo.json`
- Test: `tests/test_client.py` (append)

> The live path parses Yahoo's `transactions;types=pending` JSON to the same
> offer shape `received_trades.build_offers` expects. Like the other parsers in
> this module, it is validated against a spec-shaped synthetic fixture and must
> be re-verified against real Yahoo data on approval.

- [ ] **Step 1: Create the synthetic fixture** `tests/fixtures/pending_trades_yahoo.json`

```json
{
  "fantasy_content": {
    "league": [
      {"league_key": "428.l.123456"},
      {"transactions": {
        "0": {"transaction": [
          {"type": "pending_trade", "trader_team_key": "428.l.123456.t.2",
           "tradee_team_key": "428.l.123456.t.1"},
          {"players": {
            "0": {"player": [[{"player_key": "428.p.202681"}, {"player_id": "202681"},
                   {"name": {"full": "Kyrie Irving"}}],
                  {"transaction_data": [{"type": "pending_trade",
                     "source_team_key": "428.l.123456.t.2",
                     "destination_team_key": "428.l.123456.t.1"}]}]},
            "1": {"player": [[{"player_key": "428.p.1626164"}, {"player_id": "1626164"},
                   {"name": {"full": "Devin Booker"}}],
                  {"transaction_data": [{"type": "pending_trade",
                     "source_team_key": "428.l.123456.t.1",
                     "destination_team_key": "428.l.123456.t.2"}]}]},
            "count": 2
          }}
        ]},
        "count": 1
      }}
    ]
  }
}
```

- [ ] **Step 2: Write the failing test** (append to `tests/test_client.py`)

```python
def test_parse_pending_trades_recipient_side(fixture):
    from fantasy_gm.yahoo_client import client
    raw = fixture("pending_trades_yahoo.json")
    offers = client.parse_pending_trades(raw, my_team_key="428.l.123456.t.1")
    assert len(offers) == 1
    o = offers[0]
    # destination == me => offered to me; source == me => my player they want.
    assert o["they_give"] == ["202681"]     # Kyrie, headed to me
    assert o["they_want"] == ["1626164"]    # Booker, leaving me
    assert o["from_team"] == "428.l.123456.t.2"
```

(The `fixture` pytest fixture already exists in `tests/conftest.py`.)

- [ ] **Step 3: Run it, confirm it fails**

Run: `uv run pytest tests/test_client.py::test_parse_pending_trades_recipient_side -q`
Expected: FAIL (`module 'client' has no attribute 'parse_pending_trades'`).

- [ ] **Step 4: Add the parser + fetch wrapper to `yahoo_client/client.py`**

Append these functions (after `parse_teams_with_rosters`, before the `# Live fetch wrappers` block):

```python
def parse_pending_trades(raw: dict[str, Any], my_team_key: str) -> list[dict]:
    """Pending trades where *I* am the recipient, in received_trades' offer shape.

    NOTE (approval-gated): validated against a spec-shaped synthetic fixture
    (tests/fixtures/pending_trades_yahoo.json); re-verify against real Yahoo
    `transactions;types=pending` JSON once API access is granted.
    """
    league = raw["fantasy_content"]["league"]
    txns = league[1].get("transactions", {})
    offers: list[dict] = []
    for key, node in txns.items():
        if key == "count":
            continue
        txn = node["transaction"]
        meta = txn[0]
        if meta.get("type") != "pending_trade":
            continue
        if meta.get("tradee_team_key") != my_team_key:
            continue                          # only offers sent TO me
        they_give, they_want = [], []
        players_node = txn[1].get("players", {})
        for pk, pnode in players_node.items():
            if pk == "count":
                continue
            pdata = pnode["player"]
            pid = _meta(pdata[0], "player_id")
            tdata = pdata[1].get("transaction_data", [{}])[0]
            if tdata.get("destination_team_key") == my_team_key:
                they_give.append(pid)         # coming to me
            elif tdata.get("source_team_key") == my_team_key:
                they_want.append(pid)         # leaving me
        offers.append({"from_team": meta.get("trader_team_key", ""),
                       "date": meta.get("timestamp", ""), "note": "",
                       "they_give": they_give, "they_want": they_want})
    return offers


def fetch_pending_trades(league_key: str, my_team_key: str) -> list[dict]:
    if _demo_mode():
        import json
        from pathlib import Path
        demo_dir = Path(__file__).resolve().parents[3] / "demo_data"
        return json.loads((demo_dir / "pending_trades.json").read_text())
    raw = _get(f"league/{league_key}/transactions;types=pending")
    return parse_pending_trades(raw, my_team_key)
```

Note: `_parse_player` expects `player_id` inside the first meta list — the fixture nests meta as `pdata[0]` being a list of dicts, matching `_meta`. The pending-trade parser reads `player_id` via `_meta(pdata[0], "player_id")`, consistent with the existing `_meta` helper.

- [ ] **Step 5: Run it, confirm it passes**

Run: `uv run pytest tests/test_client.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/yahoo_client/client.py tests/fixtures/pending_trades_yahoo.json tests/test_client.py
git commit -m "feat(yahoo): live-gated pending-trade parser (validate on approval)"
```

---

### Task 6: API endpoints for received + suggested trades

**Files:**
- Modify: `src/fantasy_gm/api.py`
- Test: `tests/test_api.py` (append)

- [ ] **Step 1: Write the failing tests** (append to `tests/test_api.py`)

```python
def test_received_trades_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import Player, Team
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="1626164", name="Booker", nba_team="PHX",
                             stats={"PTS": 27.0})])])
    monkeypatch.setattr(api, "_free_agents", lambda: [
        Player(player_id="202681", name="Kyrie", nba_team="DAL", stats={"PTS": 24.0})])
    monkeypatch.setattr(api, "_pending_offers", lambda: [
        {"from_team": "Team 2", "date": "2026-01-20", "note": "swap",
         "they_give": ["202681"], "they_want": ["1626164"]}])
    body = TestClient(api.app).get("/trades/received").json()
    assert len(body["offers"]) == 1
    assert body["offers"][0]["they_give"][0]["name"] == "Kyrie"
    assert body["offers"][0]["they_want"][0]["name"] == "Booker"


def test_suggestions_endpoint(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_league_for",
        lambda request: LeagueSettings(league_key="k", format="category",
                                       categories=["PTS", "AST"]))
    monkeypatch.setattr(api, "_all_teams", lambda: [
        Team(team_key=api.MY_TEAM_KEY, name="Mine",
             players=[Player(player_id="m1", name="Scorer", nba_team="LAL",
                             stats={"PTS": 20, "AST": 2}),
                      Player(player_id="m2", name="Role", nba_team="LAL",
                             stats={"PTS": 12, "AST": 3})]),
        Team(team_key="428.l.123456.t.2", name="Rival",
             players=[Player(player_id="r1", name="Dimer", nba_team="BOS",
                             stats={"PTS": 6, "AST": 11})])])
    monkeypatch.setattr(api, "_trends_for",
        lambda ids: {"r1": {"PTS": 3, "AST": 5}})   # rival dimer cold -> buy_low
    body = TestClient(api.app).get("/trades/suggestions").json()
    assert body["format"] == "category"
    assert isinstance(body["suggestions"], list)
    assert body["suggestions"] and body["suggestions"][0]["with_team"] == "Rival"
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `uv run pytest tests/test_api.py::test_received_trades_endpoint tests/test_api.py::test_suggestions_endpoint -q`
Expected: FAIL (endpoints / `_pending_offers` don't exist).

- [ ] **Step 3: Add helpers + endpoints to `api.py`**

Add the import (extend the existing `from fantasy_gm import ...` line at line 15):

```python
from fantasy_gm import analytics, proposals, received_trades, trade, trades_history, users
```

Add a helper near `_players_by_id` (after line ~207):

```python
def _pending_offers() -> list[dict]:
    from fantasy_gm.yahoo_client import client as yahoo_client
    return yahoo_client.fetch_pending_trades(LEAGUE_KEY, MY_TEAM_KEY)
```

Add the endpoints (after the existing `/trades/history` endpoint, ~line 334):

```python
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
```

- [ ] **Step 4: Run the tests, confirm they pass**

Run: `uv run pytest tests/test_api.py::test_received_trades_endpoint tests/test_api.py::test_suggestions_endpoint -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat(api): /trades/received and /trades/suggestions endpoints"
```

---

## PHASE 2 — Analytics endpoint split

### Task 7: Subject-scoped analytics endpoints; remove `/analytics/dashboard`

**Files:**
- Modify: `src/fantasy_gm/api.py`
- Test: `tests/test_api.py`

- [ ] **Step 1: Replace the three dashboard tests** in `tests/test_api.py`

Delete `test_dashboard_endpoint_returns_all_sections`, `test_dashboard_is_format_tagged`, and `test_dashboard_uses_signed_in_user_format`. Add in their place:

```python
def _mk_category(monkeypatch):
    from fantasy_gm import api
    from fantasy_gm.schemas import LeagueSettings, Player, Team
    monkeypatch.setattr(api, "_league_for",
        lambda request: LeagueSettings(league_key="428.l.123456", format="category",
                                       categories=["PTS", "AST"]))
    monkeypatch.setattr(api, "_all_teams",
        lambda: [Team(team_key=api.MY_TEAM_KEY, name="My Squad",
                      players=[Player(player_id="1", name="A", nba_team="LAL",
                                      stats={"PTS": 20, "AST": 5})]),
                 Team(team_key="428.l.123456.t.2", name="Rival",
                      players=[Player(player_id="2", name="B", nba_team="BOS",
                                      stats={"PTS": 10, "AST": 9})])])
    monkeypatch.setattr(api, "_free_agents",
        lambda: [Player(player_id="9", name="FA", nba_team="LAL", stats={"PTS": 10})])
    monkeypatch.setattr(api, "_trends_for", lambda ids: {"9": {"PTS": 11.0}})
    monkeypatch.setattr(api, "_week_games", lambda: {"LAL": 4})


def test_my_team_analytics_category(monkeypatch):
    from fantasy_gm import api
    _mk_category(monkeypatch)
    body = TestClient(api.app).get("/analytics/my-team").json()
    assert body["format"] == "category"
    assert body["category_profile"]["PTS"]["you"] == 20


def test_waivers_analytics_category(monkeypatch):
    from fantasy_gm import api
    _mk_category(monkeypatch)
    body = TestClient(api.app).get("/analytics/waivers").json()
    assert body["format"] == "category"
    assert "recommended_pickups" in body and "streaming_board" in body


def test_league_analytics_category(monkeypatch):
    from fantasy_gm import api
    _mk_category(monkeypatch)
    body = TestClient(api.app).get("/analytics/league").json()
    assert body["format"] == "category"
    assert "category_profile" in body and "teams" in body
    assert isinstance(body["buy_low_sell_high"], list)


def test_dashboard_endpoint_removed():
    from fantasy_gm import api
    assert TestClient(api.app).get("/analytics/dashboard").status_code == 404
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `uv run pytest tests/test_api.py -q`
Expected: the new tests FAIL (endpoints missing); `test_dashboard_endpoint_removed` currently FAILS because the endpoint still exists.

- [ ] **Step 3: Replace the `/analytics/dashboard` endpoint in `api.py`**

Delete the entire `dashboard(request)` function (lines ~290-316) and insert:

```python
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
```

- [ ] **Step 4: Run the full API suite, confirm it passes**

Run: `uv run pytest tests/test_api.py -q`
Expected: PASS (new analytics tests pass; `test_dashboard_endpoint_removed` passes).

- [ ] **Step 5: Run the whole backend suite + lint**

Run: `uv run pytest -q && uv run ruff check src tests`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat(api): split /analytics/dashboard into my-team/waivers/league endpoints"
```

---

## PHASE 3 — Frontend reorg + re-theme

### Task 8: Re-theme tokens (amber → turquoise/green/yellow)

**Files:**
- Modify: `frontend/src/styles/tokens.css`
- Modify: `frontend/src/styles/app.css` (comment text only)

- [ ] **Step 1: Replace the palette blocks in `tokens.css`**

Replace the `:root { ... }`, `:root[data-theme="dark"] { ... }`, and the `@media (prefers-color-scheme: dark)` block's variables with these values (keep the `--font`/`--display`/`--radius*` lines and the `@import` line unchanged). Update the top comment to `/* Lightning — "Kinetic Verdant Precision" design tokens (cool; light + dark). */`.

Light `:root` brand + neutrals:

```css
  /* Electric brand — turquoise primary, green accent, yellow highlight */
  --primary: #14B8A6; --primary-hover: #0D9488; --on-primary: #06231F;
  --gold: #FACC15;
  --grad: linear-gradient(135deg, #FACC15 0%, #14B8A6 100%);
  --glow: rgba(20, 184, 166, 0.20);
  --accent: #16A34A; --danger: #DC2626; --ring: #14B8A6;

  /* Cool light mode (faint mint) */
  --bg: #F2FBF8; --surface: #E9F6F1; --surface-2: #FFFFFF;
  --text: #0F1F1B; --muted: #5E726C; --border: #D7ECE4;

  --radius: 16px; --radius-sm: 12px; --radius-pill: 999px;
  --shadow: 0 1px 2px rgba(13,100,90,.06), 0 6px 20px -4px rgba(13,100,90,.10);
  --shadow-halo: 0 8px 24px -6px rgba(13,100,90,.14), 0 0 16px 0 var(--glow);
```

Dark values (use identically in BOTH `:root[data-theme="dark"]` and the `@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) }` block):

```css
  --primary: #2DD4BF; --primary-hover: #5EEAD4; --on-primary: #06231F;
  --gold: #FACC15; --glow: rgba(45, 212, 191, 0.24);
  --accent: #22C55E; --danger: #F87171; --ring: #2DD4BF;
  --bg: #0E1A16; --surface: #15241F; --surface-2: #1C2F29;
  --text: #E6F4EF; --muted: #8FA8A0; --border: #27382F;
  --shadow: 0 4px 20px -2px rgba(5,20,16,.5);
  --shadow-halo: 0 8px 24px -4px rgba(5,20,16,.6), 0 0 16px 0 var(--glow);
```

- [ ] **Step 2: Update stale "amber" comments in `app.css`**

Replace the five comment lines that say "Amber"/"amber" (lines ~174, 184, 201, 219, 232) with "Verdant"/"teal" wording, e.g. `/* ===================== Lightning polish (Kinetic Verdant Precision) ===================== */`, `/* Nav: glowing teal pill tabs */`, `/* Tool-status chips: pill + teal running glow */`, `/* Composer: warm input + teal focus glow */`, `/* Charts: teal "you" fill, dashed muted "league", gradient bars */`. These are comments only — no rule changes.

- [ ] **Step 3: Verify the app builds and existing style-dependent tests still pass**

Run (inside `frontend/`): `npm test -- src/__tests__/useTheme.test.ts`
Expected: PASS (theme toggle logic is unaffected by color values).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/tokens.css frontend/src/styles/app.css
git commit -m "style(ui): re-theme to turquoise/green/yellow (Kinetic Verdant Precision)"
```

---

### Task 9: Frontend API client — new calls + types

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Remove `getDashboard`** (lines ~31-33) and add the new functions + types at the end of the file:

```typescript
// --- Analytics (subject-scoped) ---
export interface CategoryProfile { [cat: string]: { you: number; league_avg: number } }
export interface BuySellRow {
  player_id: string; name: string; nba_team: string;
  signal: "buy_low" | "sell_high"; strength: number;
  efficiency_delta: number | null; volume_delta: number; confidence: number;
  drivers: string[];
}
export interface RecommendedPickup {
  player_id: string; name: string; nba_team: string; games: number; score: number;
  drop: { player_id: string; name: string; value: number } | null;
}

export async function getMyTeamAnalytics() {
  return jget("/analytics/my-team") as Promise<{
    format: "category" | "points";
    weekdays: WeekdayCoverage[];
    category_profile?: CategoryProfile;
  }>;
}
export async function getWaiversAnalytics() {
  return jget("/analytics/waivers") as Promise<{
    format: "category" | "points";
    schedule: Record<string, number>;
    recommended_pickups: RecommendedPickup[];
    streaming_board?: { player_id: string; name: string; nba_team: string;
                        games: number; projected: Record<string, number>; score: number }[];
    points_value_board?: { player_id: string; name: string; nba_team: string;
                           games: number; projected_points: number }[];
  }>;
}
export async function getLeagueAnalytics() {
  return jget("/analytics/league") as Promise<{
    format: "category" | "points";
    teams: Team[]; my_team_key: string;
    category_profile?: CategoryProfile;
    buy_low_sell_high: BuySellRow[];
  }>;
}

// --- Trades: received + suggestions ---
export interface ReceivedOffer {
  from_team: string; date: string; note: string;
  they_give: Player[]; they_want: Player[];
}
export async function getReceivedTrades() {
  return jget("/trades/received") as Promise<{ offers: ReceivedOffer[] }>;
}
export interface TradeSuggestion {
  with_team: string; give: Player[]; get: Player[];
  targeted_categories: string[]; fairness_gap: number; need_fit: number;
}
export async function getTradeSuggestions() {
  return jget("/trades/suggestions") as Promise<{
    format: "category" | "points"; suggestions: TradeSuggestion[];
  }>;
}
```

- [ ] **Step 2: Confirm no syntax errors were introduced**

Do NOT run a full `npm run build` yet — `DashboardView.tsx` still imports the now-removed `getDashboard` and won't compile until it's deleted in Task 16. That's expected: the full build/type-check gate runs in Task 16 Step 3 after the retired view is gone. For now just re-read the appended block to confirm it's well-formed TypeScript.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(ui-api): add analytics-split + received/suggested trade calls"
```

---

### Task 10: Nav + routes for 5 tabs

**Files:**
- Modify: `frontend/src/components/Nav.tsx`
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/__tests__/nav.test.tsx`

- [ ] **Step 1: Update `nav.test.tsx`**

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { Nav } from "../components/Nav";

describe("Nav", () => {
  it("renders the five tabs with the active one marked", () => {
    render(<MemoryRouter initialEntries={["/my-team"]}><Nav /></MemoryRouter>);
    for (const label of [/chat/i, /my team/i, /waivers/i, /trade/i, /league/i]) {
      expect(screen.getByRole("link", { name: label })).toBeInTheDocument();
    }
    expect(screen.getByRole("link", { name: /my team/i })).toHaveAttribute("aria-current", "page");
  });
});
```

- [ ] **Step 2: Run it, confirm it fails**

Run (inside `frontend/`): `npm test -- src/__tests__/nav.test.tsx`
Expected: FAIL (only 4 old tabs, no `/my-team`).

- [ ] **Step 3: Update `Nav.tsx` TABS**

```typescript
const TABS = [
  { to: "/", label: "Chat" },
  { to: "/my-team", label: "My Team" },
  { to: "/waivers", label: "Waivers" },
  { to: "/trade", label: "Trade" },
  { to: "/league", label: "League" },
];
```

- [ ] **Step 4: Update `App.tsx` imports and routes**

Replace the view imports (lines 6-10) and `<Routes>` block:

```typescript
import { ChatView } from "./views/ChatView";
import { MyTeamView } from "./views/MyTeamView";
import { WaiversView } from "./views/WaiversView";
import { TradeView } from "./views/TradeView";
import { LeagueView } from "./views/LeagueView";
import { SettingsView } from "./views/SettingsView";
```

```tsx
          <Routes>
            <Route path="/" element={<ChatView />} />
            <Route path="/my-team" element={<MyTeamView />} />
            <Route path="/waivers" element={<WaiversView />} />
            <Route path="/trade" element={<TradeView />} />
            <Route path="/league" element={<LeagueView />} />
            <Route path="/settings" element={<SettingsView theme={theme} onToggle={toggle} />} />
          </Routes>
```

(`DashboardView` and `TradeHistoryView` route imports are removed; the three new views are created in Tasks 11-13, and the Trade tab absorbs history in Task 15. The app won't build until those exist — that's expected within this phase.)

- [ ] **Step 5: Run the nav test, confirm it passes**

Run (inside `frontend/`): `npm test -- src/__tests__/nav.test.tsx`
Expected: PASS (Nav renders standalone; routes don't need the views to exist for this test).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/Nav.tsx frontend/src/App.tsx frontend/src/__tests__/nav.test.tsx
git commit -m "feat(ui): 5-tab nav + routes (Chat/My Team/Waivers/Trade/League)"
```

---

### Task 11: My Team view

**Files:**
- Create: `frontend/src/views/MyTeamView.tsx`
- Create: `frontend/src/__tests__/myteam.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/__tests__/myteam.test.tsx`

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { MyTeamView } from "../views/MyTeamView";

describe("MyTeamView", () => {
  it("renders my category profile and weekday coverage", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "category",
      weekdays: [{ day: "Mon", count: 5, weak: false }, { day: "Tue", count: 2, weak: true }],
      category_profile: { PTS: { you: 110, league_avg: 100 }, AST: { you: 20, league_avg: 25 } },
    });
    render(<MyTeamView />);
    expect(await screen.findByText(/PTS/)).toBeInTheDocument();
    expect(screen.getByText(/Mon/)).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockRejectedValue(new Error("HTTP 500"));
    render(<MyTeamView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
  });
});
```

- [ ] **Step 2: Run it, confirm it fails**

Run (inside `frontend/`): `npm test -- src/__tests__/myteam.test.tsx`
Expected: FAIL (view doesn't exist).

- [ ] **Step 3: Implement `frontend/src/views/MyTeamView.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getMyTeamAnalytics } from "../lib/api";
import { RadarChart } from "../components/charts/RadarChart";
import { WeekdayBars } from "../components/charts/WeekdayBars";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getMyTeamAnalytics>>;

export function MyTeamView() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null); setData(null);
    getMyTeamAnalytics().then(setData).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load My Team: ${error}`} onRetry={load} />;
  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading…</span>
        <div className="skeleton skeleton-block" />
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  const cats = data.category_profile ? Object.keys(data.category_profile) : [];
  const you = cats.map((c) => data.category_profile![c].you);
  const league = cats.map((c) => data.category_profile![c].league_avg);

  return (
    <div className="dashboard">
      {cats.length > 0 && <RadarChart cats={cats} you={you} league={league} />}
      <WeekdayBars days={data.weekdays} />
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run (inside `frontend/`): `npm test -- src/__tests__/myteam.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/MyTeamView.tsx frontend/src/__tests__/myteam.test.tsx
git commit -m "feat(ui): My Team view (category profile + weekday coverage)"
```

---

### Task 12: Waivers view

**Files:**
- Create: `frontend/src/views/WaiversView.tsx`
- Create: `frontend/src/__tests__/waivers.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/__tests__/waivers.test.tsx`

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { WaiversView } from "../views/WaiversView";

describe("WaiversView", () => {
  it("renders recommended pickups and the streaming board (category)", async () => {
    vi.spyOn(api, "getWaiversAnalytics").mockResolvedValue({
      format: "category",
      schedule: { LAL: 4 },
      recommended_pickups: [
        { player_id: "1", name: "Add Me", nba_team: "LAL", games: 4, score: 80,
          drop: { player_id: "9", name: "Drop Me", value: 5 } }],
      streaming_board: [
        { player_id: "2", name: "Streamer", nba_team: "LAL", games: 4,
          projected: { PTS: 40 }, score: 40 }],
    });
    render(<WaiversView />);
    expect(await screen.findByText(/Add Me/)).toBeInTheDocument();
    expect(screen.getByText(/Streaming board/i)).toBeInTheDocument();
  });

  it("shows an empty state when there are no recommendations", async () => {
    vi.spyOn(api, "getWaiversAnalytics").mockResolvedValue({
      format: "category", schedule: {}, recommended_pickups: [], streaming_board: [],
    });
    render(<WaiversView />);
    expect(await screen.findByText(/no recommendations/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run it, confirm it fails**

Run (inside `frontend/`): `npm test -- src/__tests__/waivers.test.tsx`
Expected: FAIL (view missing).

- [ ] **Step 3: Implement `frontend/src/views/WaiversView.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getWaiversAnalytics, type RecommendedPickup } from "../lib/api";
import { BarList } from "../components/charts/BarList";
import { GamesHeatmap } from "../components/charts/GamesHeatmap";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getWaiversAnalytics>>;

function RecommendedPickups({ items }: { items: RecommendedPickup[] }) {
  return (
    <figure className="chart">
      <figcaption>Recommended pickups</figcaption>
      <ul className="pickups">
        {items.map((r) => (
          <li key={r.player_id} className="pickup-row">
            <span className="pickup-add">Add {r.name} <em>{r.nba_team} · {r.games} gm</em></span>
            {r.drop && <span className="pickup-drop">drop {r.drop.name}</span>}
          </li>
        ))}
      </ul>
      <table className="sr-table">
        <caption>Recommended pickups</caption>
        <thead><tr><th>Add</th><th>Team</th><th>Games</th><th>Drop</th></tr></thead>
        <tbody>{items.map((r) => (
          <tr key={r.player_id}>
            <td>{r.name}</td><td>{r.nba_team}</td><td>{r.games}</td>
            <td>{r.drop ? r.drop.name : "—"}</td>
          </tr>
        ))}</tbody>
      </table>
    </figure>
  );
}

export function WaiversView() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null); setData(null);
    getWaiversAnalytics().then(setData).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load Waivers: ${error}`} onRetry={load} />;
  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading…</span>
        <div className="skeleton skeleton-block" />
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  const hasContent = data.recommended_pickups.length > 0 ||
    (data.format === "points" ? (data.points_value_board?.length ?? 0) > 0
      : (data.streaming_board?.length ?? 0) > 0);
  if (!hasContent) {
    return <div className="empty">No recommendations right now — check back after games tonight.</div>;
  }

  const board = data.format === "points"
    ? (data.points_value_board ?? []).map((r) => ({
        label: r.name, value: r.projected_points, sub: `${r.nba_team} · ${r.games} gm` }))
    : (data.streaming_board ?? []).map((r) => ({
        label: r.name, value: r.score, sub: `${r.nba_team} · ${r.games} gm` }));

  return (
    <div className="dashboard">
      <BarList title={data.format === "points" ? "Points value board" : "Streaming board"}
               items={board} />
      <RecommendedPickups items={data.recommended_pickups} />
      <GamesHeatmap games={data.schedule} />
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run (inside `frontend/`): `npm test -- src/__tests__/waivers.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/WaiversView.tsx frontend/src/__tests__/waivers.test.tsx
git commit -m "feat(ui): Waivers view (pickups + streaming/points board)"
```

---

### Task 13: League view

**Files:**
- Create: `frontend/src/views/LeagueView.tsx`
- Create: `frontend/src/__tests__/league.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/__tests__/league.test.tsx`

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { LeagueView } from "../views/LeagueView";

describe("LeagueView", () => {
  it("renders the teams table and buy-low/sell-high list", async () => {
    vi.spyOn(api, "getLeagueAnalytics").mockResolvedValue({
      format: "category",
      my_team_key: "t1",
      teams: [
        { team_key: "t1", name: "Mine",
          players: [{ player_id: "1", name: "A", nba_team: "LAL", stats: { PTS: 20 } }] },
        { team_key: "t2", name: "Rival",
          players: [{ player_id: "2", name: "B", nba_team: "BOS", stats: { PTS: 10 } }] },
      ],
      category_profile: { PTS: { you: 20, league_avg: 15 } },
      buy_low_sell_high: [
        { player_id: "2", name: "Cold Star", nba_team: "BOS", signal: "buy_low",
          strength: 0.6, efficiency_delta: -1.2, volume_delta: -0.1, confidence: 0.8,
          drivers: ["FG% below season"] }],
    });
    render(<LeagueView />);
    expect(await screen.findByText(/Mine/)).toBeInTheDocument();
    expect(screen.getByText(/Cold Star/)).toBeInTheDocument();
    expect(screen.getByText(/FG% below season/)).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getLeagueAnalytics").mockRejectedValue(new Error("HTTP 500"));
    render(<LeagueView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
  });
});
```

- [ ] **Step 2: Run it, confirm it fails**

Run (inside `frontend/`): `npm test -- src/__tests__/league.test.tsx`
Expected: FAIL (view missing).

- [ ] **Step 3: Implement `frontend/src/views/LeagueView.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getLeagueAnalytics } from "../lib/api";
import { DivergingList } from "../components/charts/DivergingList";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getLeagueAnalytics>>;

export function LeagueView() {
  const [data, setData] = useState<Payload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setError(null); setData(null);
    getLeagueAnalytics().then(setData).catch((e) => setError(String(e)));
  };
  useEffect(load, []);

  if (error) return <ErrorBanner message={`Failed to load League: ${error}`} onRetry={load} />;
  if (!data) {
    return (
      <div className="dashboard" aria-busy="true" aria-live="polite">
        <span className="sr-table">Loading…</span>
        <div className="skeleton skeleton-block" />
      </div>
    );
  }

  // Map the signed strength onto the diverging list: sell_high positive, buy_low negative.
  const divergingItems = data.buy_low_sell_high.map((r) => ({
    label: r.name,
    value: Math.round((r.signal === "sell_high" ? r.strength : -r.strength) * 100),
    signal: r.signal,
  }));

  return (
    <div className="dashboard">
      <figure className="chart">
        <figcaption>League teams</figcaption>
        <table className="delta-table">
          <thead><tr><th>Team</th><th>Players</th></tr></thead>
          <tbody>
            {data.teams.map((t) => (
              <tr key={t.team_key} className={t.team_key === data.my_team_key ? "good" : ""}>
                <td>{t.name}{t.team_key === data.my_team_key && <em> (you)</em>}</td>
                <td>{t.players.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </figure>

      {divergingItems.length > 0 && (
        <figure className="chart">
          <figcaption>Buy-low / sell-high</figcaption>
          <DivergingList items={divergingItems} />
          <ul className="buy-sell-drivers">
            {data.buy_low_sell_high.map((r) => (
              <li key={r.player_id}>
                <strong>{r.name}</strong> — {r.signal === "buy_low" ? "buy low" : "sell high"}
                {r.drivers.length > 0 && <em> ({r.drivers.join(", ")})</em>}
              </li>
            ))}
          </ul>
        </figure>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run (inside `frontend/`): `npm test -- src/__tests__/league.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/LeagueView.tsx frontend/src/__tests__/league.test.tsx
git commit -m "feat(ui): League view (teams table + buy-low/sell-high)"
```

---

### Task 14: Shared AnalyzeTrade component

**Files:**
- Create: `frontend/src/components/AnalyzeTrade.tsx`
- Create: `frontend/src/__tests__/analyzetrade.test.tsx`

- [ ] **Step 1: Write the failing test** `frontend/src/__tests__/analyzetrade.test.tsx`

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as api from "../lib/api";
import { AnalyzeTrade } from "../components/AnalyzeTrade";

describe("AnalyzeTrade", () => {
  it("runs the Claude verdict on click and shows the recommendation", async () => {
    vi.spyOn(api, "analyzeTrade").mockResolvedValue({
      format: "category", delta: { AST: 6 }, summary: { improved: ["AST"], worsened: [] },
      verdict: "You gain assists. ACCEPT", recommendation: "ACCEPT",
    });
    render(<AnalyzeTrade give={["1"]} get={["2"]} />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByText(/ACCEPT/)).toBeInTheDocument();
    expect(screen.getByText(/You gain assists\./)).toBeInTheDocument();
  });

  it("shows an error if analysis fails", async () => {
    vi.spyOn(api, "analyzeTrade").mockRejectedValue(new Error("HTTP 429"));
    render(<AnalyzeTrade give={["1"]} get={["2"]} />);
    await userEvent.click(screen.getByRole("button", { name: /analyze/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to analyze/i);
  });
});
```

- [ ] **Step 2: Run it, confirm it fails**

Run (inside `frontend/`): `npm test -- src/__tests__/analyzetrade.test.tsx`
Expected: FAIL (component missing).

- [ ] **Step 3: Implement `frontend/src/components/AnalyzeTrade.tsx`**

```tsx
import { useState } from "react";
import { analyzeTrade } from "../lib/api";
import { ErrorBanner } from "./ErrorBanner";

interface Result {
  verdict: string;
  recommendation: "ACCEPT" | "DECLINE" | "COUNTER";
  delta: Record<string, number> | { give_value: number; get_value: number; net: number };
}

/** Strip the trailing ACCEPT/DECLINE/COUNTER keyword the backend appends. */
function narrativeOnly(verdict: string, recommendation: string): string {
  return verdict.replace(new RegExp(`\\s*${recommendation}\\.?\\s*$`), "").trim();
}

/** Shared "Analyze" action used by received offers and suggested trades.
 * Pre-fills give/get and runs the existing Claude verdict endpoint on demand. */
export function AnalyzeTrade({ give, get }: { give: string[]; get: string[] }) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  const run = async () => {
    setLoading(true); setError(null);
    try {
      setResult(await analyzeTrade(give, get) as Result);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="analyze-trade">
      <button type="button" className="analyze-btn" disabled={loading} onClick={run}>
        {loading ? "Analyzing…" : "Analyze"}
      </button>
      {error && <ErrorBanner message={`Failed to analyze trade: ${error}`} onRetry={run} />}
      {result && (
        <div className={`verdict-card rec-${result.recommendation.toLowerCase()}`}>
          <span className="badge">{result.recommendation}</span>
          <p>{narrativeOnly(result.verdict, result.recommendation)}</p>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run the test, confirm it passes**

Run (inside `frontend/`): `npm test -- src/__tests__/analyzetrade.test.tsx`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/AnalyzeTrade.tsx frontend/src/__tests__/analyzetrade.test.tsx
git commit -m "feat(ui): shared AnalyzeTrade component (on-demand Claude verdict)"
```

---

### Task 15: Expanded Trade tab (received + suggested + manual + history)

**Files:**
- Modify: `frontend/src/views/TradeView.tsx`
- Modify: `frontend/src/__tests__/trade.test.tsx`

- [ ] **Step 1: Add failing tests** for the new sections (append to `src/__tests__/trade.test.tsx`, inside the `describe` block)

```typescript
  it("lists received offers with an Analyze button", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1", teams: [{ team_key: "t1", name: "Mine", players: [] }],
    });
    vi.spyOn(api, "getReceivedTrades").mockResolvedValue({
      offers: [{ from_team: "Team 2", date: "2026-01-20", note: "swap",
        they_give: [{ player_id: "2", name: "Kyrie", nba_team: "DAL", stats: {} }],
        they_want: [{ player_id: "1", name: "Booker", nba_team: "PHX", stats: {} }] }],
    });
    vi.spyOn(api, "getTradeSuggestions").mockResolvedValue({ format: "category", suggestions: [] });
    vi.spyOn(api, "getTradeHistory").mockResolvedValue({ trades: [] });
    render(<TradeView />);
    expect(await screen.findByText(/Team 2/)).toBeInTheDocument();
    expect(screen.getByText(/Kyrie/)).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /analyze/i }).length).toBeGreaterThan(0);
  });

  it("lists suggested trades with targeted categories", async () => {
    vi.spyOn(api, "getTeams").mockResolvedValue({
      my_team_key: "t1", teams: [{ team_key: "t1", name: "Mine", players: [] }],
    });
    vi.spyOn(api, "getReceivedTrades").mockResolvedValue({ offers: [] });
    vi.spyOn(api, "getTradeSuggestions").mockResolvedValue({
      format: "category",
      suggestions: [{ with_team: "Rival",
        give: [{ player_id: "1", name: "My Star", nba_team: "LAL", stats: {} }],
        get: [{ player_id: "2", name: "Their Dimer", nba_team: "BOS", stats: {} }],
        targeted_categories: ["AST"], fairness_gap: 3.2, need_fit: 12.5 }],
    });
    vi.spyOn(api, "getTradeHistory").mockResolvedValue({ trades: [] });
    render(<TradeView />);
    expect(await screen.findByText(/Their Dimer/)).toBeInTheDocument();
    expect(screen.getByText(/AST/)).toBeInTheDocument();
  });
```

Also add these default mocks so the existing tests (which only mock `getTeams`) still pass — add a `beforeEach` inside the `describe` that stubs the new calls with empty data:

```typescript
  beforeEach(() => {
    vi.spyOn(api, "getReceivedTrades").mockResolvedValue({ offers: [] });
    vi.spyOn(api, "getTradeSuggestions").mockResolvedValue({ format: "category", suggestions: [] });
    vi.spyOn(api, "getTradeHistory").mockResolvedValue({ trades: [] });
  });
```

(Import `beforeEach` from `vitest` at the top of the file. Per-test `vi.spyOn` calls in the new tests override these defaults.)

- [ ] **Step 2: Run the trade tests, confirm the new ones fail**

Run (inside `frontend/`): `npm test -- src/__tests__/trade.test.tsx`
Expected: the two new tests FAIL (sections not rendered yet).

- [ ] **Step 3: Add the sections to `TradeView.tsx`**

Add imports at the top:

```typescript
import { getReceivedTrades, getTradeSuggestions, type ReceivedOffer, type TradeSuggestion } from "../lib/api";
import { AnalyzeTrade } from "../components/AnalyzeTrade";
import { TradeHistoryView } from "./TradeHistoryView";
```

Add state + loaders inside `TradeView`, after the existing `useState` declarations:

```typescript
  const [offers, setOffers] = useState<ReceivedOffer[]>([]);
  const [suggestions, setSuggestions] = useState<TradeSuggestion[]>([]);

  useEffect(() => {
    getReceivedTrades().then((d) => setOffers(d.offers)).catch(() => setOffers([]));
    getTradeSuggestions().then((d) => setSuggestions(d.suggestions)).catch(() => setSuggestions([]));
  }, []);
```

Add the two sections at the very top of the returned `<div className="trade">` (before the existing `trade-pickers`):

```tsx
      <section className="trade-section">
        <h2>Trade offers received</h2>
        {offers.length === 0 && <div className="empty">No offers right now.</div>}
        {offers.map((o, i) => (
          <div key={`${o.from_team}-${i}`} className="offer-card">
            <div className="offer-head"><strong>{o.from_team}</strong> <em>{o.date}</em></div>
            {o.note && <p className="offer-note">{o.note}</p>}
            <div className="offer-sides">
              <div><span className="side-label">They give</span>
                {o.they_give.map((p) => <span key={p.player_id} className="selected-card get">{p.name}</span>)}</div>
              <div><span className="side-label">They want</span>
                {o.they_want.map((p) => <span key={p.player_id} className="selected-card give">{p.name}</span>)}</div>
            </div>
            <AnalyzeTrade give={o.they_want.map((p) => p.player_id)}
                          get={o.they_give.map((p) => p.player_id)} />
          </div>
        ))}
      </section>

      <section className="trade-section">
        <h2>Suggested trades to propose</h2>
        {suggestions.length === 0 && <div className="empty">No strong suggestions this week.</div>}
        {suggestions.map((s, i) => (
          <div key={`${s.with_team}-${i}`} className="offer-card">
            <div className="offer-head"><strong>{s.with_team}</strong></div>
            <div className="offer-sides">
              <div><span className="side-label">You give</span>
                {s.give.map((p) => <span key={p.player_id} className="selected-card give">{p.name}</span>)}</div>
              <div><span className="side-label">You get</span>
                {s.get.map((p) => <span key={p.player_id} className="selected-card get">{p.name}</span>)}</div>
            </div>
            {s.targeted_categories.length > 0 && (
              <p className="offer-note">Targets: {s.targeted_categories.join(", ")} · fairness gap {s.fairness_gap}</p>
            )}
            <AnalyzeTrade give={s.give.map((p) => p.player_id)}
                          get={s.get.map((p) => p.player_id)} />
          </div>
        ))}
      </section>
```

Add the history section at the very end of the returned `<div className="trade">` (after the existing results blocks, before the closing `</div>`):

```tsx
      <section className="trade-section">
        <h2>Trade history</h2>
        <TradeHistoryView />
      </section>
```

- [ ] **Step 4: Run the trade tests, confirm they pass**

Run (inside `frontend/`): `npm test -- src/__tests__/trade.test.tsx`
Expected: PASS (old + new tests).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/TradeView.tsx frontend/src/__tests__/trade.test.tsx
git commit -m "feat(ui): Trade tab — received offers, suggested trades, embedded history"
```

---

### Task 16: Remove DashboardView, finalize build + full suite

**Files:**
- Delete: `frontend/src/views/DashboardView.tsx`
- Delete: `frontend/src/__tests__/dashboard.test.tsx`
- Modify: `frontend/src/__tests__/tradehistory.test.tsx` (if it imports removed APIs)

- [ ] **Step 1: Delete the retired view and its test**

```bash
git rm frontend/src/views/DashboardView.tsx frontend/src/__tests__/dashboard.test.tsx
```

- [ ] **Step 2: Check for lingering references**

Run (inside `frontend/`): `grep -rn "getDashboard\|DashboardView\|\"/dashboard\"\|\"/history\"" src`
Expected: no output. (`tradehistory.test.tsx` renders `TradeHistoryView` directly and is unaffected; that component is unchanged and still used inside `TradeView`. The old `/dashboard` and `/history` routes are gone.) Fix any lingering reference before building.

- [ ] **Step 3: Type-check / build the frontend**

Run (inside `frontend/`): `npm run build`
Expected: build succeeds with no TS errors.

- [ ] **Step 4: Run the full frontend test suite**

Run (inside `frontend/`): `npm test`
Expected: all suites PASS.

- [ ] **Step 5: Run the full backend suite + lint**

Run: `uv run pytest -q && uv run ruff check src tests`
Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore(ui): remove retired Dashboard view; finalize 5-tab reorg"
```

---

## Verification checklist (run after Task 16)

- [ ] Backend: `uv run pytest -q` all pass; `uv run ruff check src tests` clean.
- [ ] Frontend: `npm test` all pass; `npm run build` clean.
- [ ] Manual smoke (optional, demo mode): start the API + frontend, confirm the five tabs load, the Trade tab shows two received offers + suggestions, each Analyze button returns a verdict, and the theme is turquoise/green/yellow in light and dark.
