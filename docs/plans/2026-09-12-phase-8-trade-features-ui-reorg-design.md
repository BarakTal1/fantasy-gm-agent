# Phase 8 — Received Trades, Suggested Trades & 5-Tab UI Reorg (Design)

> **Status:** Design/spec. Implementation plan to follow via `writing-plans` (this doc is the input to that step).

## Goal

Add two trade features and reorganize the UI around them:

1. **Received trades** — surface pending trade offers other managers sent you, each with an on-demand **Analyze** button that runs the existing Claude verdict.
2. **Suggested trades** — a deterministic league scan that proposes packages you could offer, targeting **buy-low** players who fill your **weak categories** while giving up **sell-high / surplus** players. Small packages (up to 2 players/side) allowed. Each shows targeted weak categories + fairness gap, plus an **Analyze** button for the Claude verdict.
3. **Improve `buy_low / sell_high`** into a research-grounded formula (below), used both by the League analytics view and as the targeting backbone for suggested trades.
4. **Reorganize the frontend into 5 tabs:** Chat · My Team · Waivers · Trade · League (retiring the single Dashboard tab and the standalone History tab).
5. **Re-theme the UI** from warm amber/orange to a cool **turquoise / green / yellow** palette (token swap in one file).

## Non-goals (YAGNI)

- No roster/trade **writes** to Yahoo — the app stays read-only by design; the human executes.
- No packages larger than 2 players per side.
- No new external data sources. We work with what we carry today (season `stats` + a ~14-day recent-form `trend`), and **document** the live-Yahoo upgrades (usage rate, minutes, multi-year career mean) as flip-on-at-approval enhancements rather than building speculative plumbing.
- No Claude verdict pre-computed for lists — verdicts are on-demand per item to keep the list scan fast and cheap.

---

## Architecture overview

Everything follows the established **demo-shell → live-Yahoo-gated** pattern already used by `trades_history` and the rest of `yahoo_client`: pure functions over clean schema objects, demo mode reads committed fixtures, the live parser is built + validated against fixtures and flips on with the demo flag at Yahoo approval.

```
Trade tab (frontend)
  ├── Offers received      → GET /trades/received      → received_trades.py  (fixture | live-gated)
  ├── Suggested trades     → GET /trades/suggestions    → proposals.py       (deterministic)
  ├── Manual analyzer      → POST /trade/analyze         → trade.py + Claude  (UNCHANGED, reused)
  └── Trade history        → GET /trades/history         → trades_history.py  (UNCHANGED, relocated in UI)

Analyze button (received + suggested) → POST /trade/analyze  (reuses existing verdict engine)

Analytics split by subject
  ├── My Team → GET /analytics/my-team
  ├── Waivers → GET /analytics/waivers
  └── League  → GET /analytics/league   (uses the improved buy_low/sell_high)
```

---

## Component 1 — Improved buy-low / sell-high (`analytics.py`)

Replaces the current `buy_low_sell_high()` (a lumped `(recent_total − season_total)/season_total > 15%` ratio that ignores efficiency vs volume and lets a big PTS number dominate).

### Research basis

Professional analysts (RotoWire, Athlon, Fantasy Analytics Authority, ESPN, Dunkest) converge on:

- **Efficiency regression is the primary signal** — shooting %s reverting to baseline. Anchor: FG% **>4 pct points above** the ~3-year career mean = regression (sell) risk; well below = bounce-back (buy).
- **Opportunity must be intact** — buy-low only holds if minutes/usage are steady; a usage drop means the decline is *real*. Avg usage ≈ 20%, elite >28–30%.
- **Sample size** — under **20 games**, counting-stat variance is ±15–20%; **30 games** = stable baseline. **STL/BLK** unreliable beyond ~15-game windows → down-weight.
- **Recent-form window** analysts watch: last 3–5 games; one week (2–4 games) is a tiny sample.

Sources are cited inline in the module docstring.

### Formula (buildable on our data)

Baseline = **season `stats`**; current = **recent-form `trend`** (~14-day window). For each player with a trend:

1. **Normalize** each category's divergence so categories are comparable (fixes the magnitude-dominance flaw):
   `d_c = (recent_c − season_c) / scale_c`, where `scale_c` is the league-average magnitude (or spread) of category `c`. Percentage cats use percentage-point difference over a typical spread.
2. **Split** the signal:
   - **Efficiency `E`** = weighted mean of `d_c` over % cats {FG%, FT%} + 3PM (shooting proxy) — **highest weight** (the reliable regression signal).
   - **Volume `V`** = weighted mean of `d_c` over counting cats (PTS/REB/AST); **STL/BLK down-weighted**; TO inverted (fewer is better).
3. **Classify:**
   - **Sell-high** when `E ≥ +τ_eff` (shooting running hot) → strength `= w_e·E + w_v·max(0, V)`.
   - **Buy-low** when `E ≤ −τ_eff` **and** `V ≥ −vol_floor` (volume/opportunity not collapsed — our proxy for "opportunity intact") → strength `= |w_e·E|`.
   - Otherwise: no signal.
4. **Confidence** multiplier from sample size: `×0.6` under 20 games, `×1.0` at 30+ (uses real games-played when live; assumed medium in demo). Applied to strength.

All tunables (`τ_eff`, `vol_floor`, `w_e`, `w_v`, STL/BLK weight, confidence cutoffs) are **named constants at the top of the module**, each commented with its research anchor (4-pct-pt, 15–20%, 20/30-game).

### Output shape (per flagged player)

```json
{"player_id": "...", "name": "...", "nba_team": "...",
 "signal": "buy_low" | "sell_high", "strength": 0.42,
 "efficiency_delta": -0.31, "volume_delta": 0.05, "confidence": 0.6,
 "drivers": ["FG% below season", "FT% below season"]}
```

`drivers` is a short list of the categories moving the signal, for a human-readable rationale in the UI.

### Documented live-data upgrades (comments in code)

- Replace the season baseline with a **multi-year career mean** as the regression anchor.
- Gate "opportunity intact" on true **usage rate** and **minutes** stability instead of the volume proxy.
- Feed real **games-played** into the confidence multiplier.

---

## Component 2 — Received trades (`received_trades.py`, `GET /trades/received`)

### Data

- **Demo:** new `demo_data/pending_trades.json` — a list of offers other managers sent you. Each: `{from_team, date, note?, they_give: [player_id...], they_want: [player_id...]}`.
  - `they_give` = players the other manager is offering you.
  - `they_want` = your players they're asking for.
- **Live (gated):** parse Yahoo `league/{league_key}/transactions;types=pending`, keep trades where **you are the recipient** (not the proposer). Built behind the demo flag, validated against the fixture shape, flips on at approval — same as `trades_history` and the other `yahoo_client` parsers. The Yahoo parser lives in `yahoo_client/client.py` (`parse_pending_trades` + `fetch_pending_trades`), matching the existing module boundary.

### Module

`received_trades.py` resolves player ids to full `Player` objects (via the same by-id index `api.py` already builds for `/trades/history`) and returns:

```json
{"offers": [
  {"from_team": "Team 4", "date": "2026-01-20", "note": "need scoring",
   "they_give": [<player>...], "they_want": [<player>...]}
]}
```

### Endpoint

`GET /trades/received` → `{offers: [...]}`. No Claude call. The frontend's Analyze button maps an offer to `POST /trade/analyze` with **`give = they_want` (your players) and `get = they_give` (their players)** — the existing verdict engine, unchanged.

---

## Component 3 — Suggested trades (`proposals.py`, `GET /trades/suggestions`)

Deterministic generator. No Claude at generation time.

### Algorithm (category leagues)

1. **My weak categories** — reuse `analytics._need_weights(my_team, all_teams, cats)` (weight > 1 where I trail the league average).
2. **My tradeable assets** — my players that are either `sell_high`-flagged by the improved formula **or** surplus (strong in categories I'm already deep in, i.e. low need-weight cats). Each carries a `scoring.player_value`.
3. **Targets, per other team** — their players flagged `buy_low` **and** whose category profile helps my weak cats.
4. **Form packages** (cap **2 players per side**):
   - Try **1-for-1** first (one asset ↔ one target).
   - Then **2-for-1 / 1-for-2** only where a single swap can't balance value.
   - Keep the **fairness gap** `|Σ value(give) − Σ value(get)|` within a tolerance (within X% of the larger side) so the other team might plausibly accept.
5. **Score** each package by **need-fit**: the need-weighted improvement to my weak categories (`category_delta(give, get, cats)` weighted by need weights, positive-only), minus a small fairness penalty.
6. **Rank**, dedupe (don't propose the same asset in many near-identical packages), return top **N** (default 8).

### Algorithm (points leagues)

Simpler: target `buy_low` players whose projected fantasy points (`scoring.fantasy_points`) exceed what I give, with a small fairness gap and net-positive points. Same package cap and ranking-by-net.

### Output shape (per proposal)

```json
{"with_team": "Team 7",
 "give": [<player>...], "get": [<player>...],
 "targeted_categories": ["STL", "3PM"],
 "fairness_gap": 4.2,
 "need_fit": 12.7}
```

`give`/`get` are resolved player objects so the Analyze button can pre-fill `POST /trade/analyze` directly (`give` = my players, `get` = theirs).

### Endpoint

`GET /trades/suggestions` → `{format, suggestions: [...]}`. Deterministic, cheap; each item's Claude verdict is on-demand via the existing analyzer.

### Tunables

Package cap (2), fairness tolerance %, result count N, min need-fit to include — named constants at the top of `proposals.py`.

---

## Component 4 — Analytics split by subject (`api.py`, `analytics.py`)

Replace the single `GET /analytics/dashboard` with three subject-scoped endpoints, each computing **only its slice** (so three tabs don't each recompute the full bundle). No new analytics functions beyond the improved buy/sell — this is re-slicing existing ones.

| Endpoint | Contents (category league) | Contents (points league) |
|---|---|---|
| `GET /analytics/my-team` | `category_profile` (you vs league avg) + `weekday_coverage` | `weekday_coverage` |
| `GET /analytics/waivers` | `recommended_pickups` + `streaming_board` | `recommended_pickups` + `points_value_board` |
| `GET /analytics/league` | all-teams table + league-wide `category_profile` comparison + improved `buy_low_sell_high` | all-teams table + `buy_low_sell_high` (where meaningful) |

`GET /analytics/weekdays`, `GET /league/teams`, `GET /league/info` stay as-is. `GET /analytics/dashboard` is **removed** (no external consumers other than our own frontend, which is being rewritten in the same phase).

---

## Component 5 — Frontend 5-tab reorg (`frontend/`)

`Nav` tabs become: **Chat · My Team · Waivers · Trade · League**. Old `Dashboard` and `History` tabs are removed; their content is redistributed.

- **My Team** (`MyTeamView`): your roster, category profile, weekday coverage. Consumes `/analytics/my-team`, `/analytics/weekdays`, `/league/teams`.
- **Waivers** (`WaiversView`): pickup + streaming/points boards. Consumes `/analytics/waivers`.
- **Trade** (`TradeView`, expanded): stacked sections in this order —
  1. **Offers received** — one card per offer (from-team, both player lists), each with an **Analyze** button that expands the Claude verdict inline (ACCEPT/DECLINE/COUNTER badge + narrative, reusing the existing verdict rendering).
  2. **Suggested trades** — ranked cards showing `with_team`, give/get players, **targeted weak categories**, and **fairness gap**, each with the same **Analyze** button.
  3. **Manual analyzer** — the existing give/get picker + result, unchanged.
  4. **Trade history** — the existing `TradeHistoryView` content, relocated here as a section.
- **League** (`LeagueView`): all-teams table, league-wide category comparison, buy-low/sell-high list. Consumes `/analytics/league`.

Existing dashboard chart components (radar, ranked bars, diverging list, games heatmap) are **moved, not rewritten**, into their new host views. The shared Analyze flow is factored into a small reusable component/hook so received + suggested + manual all render the verdict consistently.

`frontend/src/lib/api.ts` gains: `getReceivedTrades()`, `getTradeSuggestions()`, `getMyTeamAnalytics()`, `getWaiversAnalytics()`, `getLeagueAnalytics()`; `getDashboard()` is removed.

---

## Component 6 — Re-theme: turquoise / green / yellow (`frontend/src/styles/tokens.css`)

Swap the "Kinetic Amber Precision" warm palette for a cool **turquoise-primary / green-accent / yellow-highlight** scheme. Almost entirely a value swap in `tokens.css` (the app is fully token-driven); the few hardcoded warm-brown tints in `--grad`, `--glow`, and the `--shadow` rgba values shift to cool teal. `--danger` stays red. Backgrounds shift to **cool-tinted neutrals** (faint mint/teal) to match.

**Decisions locked:** turquoise is the dominant/primary brand color (buttons, links, logo bolt, active tab); green is the secondary accent; yellow powers highlights and the hero gradient; neutrals get a faint cool tint.

| Token | Role | Light | Dark |
|---|---|---|---|
| `--primary` | turquoise (brand) | `#14B8A6` | `#2DD4BF` |
| `--primary-hover` | | `#0D9488` | `#5EEAD4` |
| `--on-primary` | text on primary | `#06231F` | `#06231F` |
| `--accent` | green | `#16A34A` | `#22C55E` |
| `--gold` | yellow | `#FACC15` | `#FACC15` |
| `--grad` | hero gradient | `linear-gradient(135deg, #FACC15 0%, #14B8A6 100%)` | same |
| `--glow` | brand glow | `rgba(20,184,166,.20)` | `rgba(45,212,191,.24)` |
| `--ring` | focus ring | `#14B8A6` | `#2DD4BF` |
| `--danger` | | `#DC2626` | `#F87171` |
| `--bg` | page bg | `#F2FBF8` | `#0E1A16` |
| `--surface` | card bg | `#E9F6F1` | `#15241F` |
| `--surface-2` | raised bg | `#FFFFFF` | `#1C2F29` |
| `--text` | | `#0F1F1B` | `#E6F4EF` |
| `--muted` | | `#5E726C` | `#8FA8A0` |
| `--border` | | `#D7ECE4` | `#27382F` |
| `--shadow` tints | brown → teal | `rgba(13,100,90,.08/.12)` | cool dark `rgba(5,20,16,.5/.6)` |

Fonts, radii, and structure are unchanged. The theme comment/name is updated (e.g. "Kinetic Verdant Precision"). The existing light/dark token blocks and the `prefers-color-scheme` block are all updated in lockstep (the dark values are currently duplicated across `[data-theme="dark"]` and the media query — both get the same new values). Contrast of text on `--primary`/`--gold` is verified to stay AA.

**Confirmed scope:** a grep of `frontend/src` found **no hardcoded amber hexes** outside `tokens.css` — every component reads `var(--*)` tokens, so the swap is isolated to the one file. The logo is an inline `<Zap fill="currentColor">` icon (inherits `--primary`), and `hero.png` is an orphan asset (not referenced anywhere), so there are no baked-in raster colors to replace. Stale "amber" wording in `app.css` comments is updated to match, but those are comments only — no behavior change.

## Data flow (Analyze on a received/suggested trade)

```
User clicks Analyze on a card
  → frontend maps card to {give: my_players, get: their_players}
  → POST /trade/analyze  (existing endpoint, rate-limited, Claude verdict)
  → verdict + delta rendered inline in the card (same UI as manual analyzer)
```

## Error handling

- New GET endpoints follow existing conventions: return clean JSON; demo fixtures are committed so they never 404 in demo mode. Live-gated parsers raise the same classified `yahoo_client` errors on real failures.
- `proposals.py` and `received_trades.py` are pure and total: empty inputs (no assets, no targets, no offers) return empty lists, and the frontend renders an empty-state ("No offers right now", "No strong suggestions this week"), mirroring existing empty states.
- The Analyze button reuses the existing `/trade/analyze` rate-limit + error banner path.

## Testing

- **`tests/test_analytics.py`** — extend for the improved `buy_low_sell_high`: efficiency-vs-volume split, normalization, confidence dampening, threshold edges, STL/BLK down-weighting.
- **`tests/test_proposals.py`** (new) — need-fit ranking, fairness cap, 1-for-1 before packages, package sizing (≤2/side), dedupe, points-league variant, empty inputs.
- **`tests/test_received_trades.py`** (new) — fixture parsing, player-id resolution, direction correctness (they_give vs they_want), empty offers.
- **`tests/test_api.py`** — the three new analytics endpoints + `/trades/received` + `/trades/suggestions`; confirm `/analytics/dashboard` is gone.
- **Frontend** — view tests for the new Trade sections (received card, suggested card, targeted-cats + fairness-gap display) and the shared Analyze flow, mirroring existing `trade.test.tsx` / `tradehistory.test.tsx`; smoke tests that each of the 5 tabs renders.

## Phasing (single plan, ordered)

1. **Backend trade features** — improved `buy_low_sell_high`; `received_trades.py` + fixture + endpoint; `proposals.py` + endpoint; live-gated Yahoo `pending_trades` parser. Tests.
2. **Analytics endpoint split** — three subject endpoints; remove `/analytics/dashboard`. Tests.
3. **Frontend 5-tab reorg + re-theme** — new Nav; My Team / Waivers / League views (relocated charts); expanded Trade tab with received + suggested sections + shared Analyze flow; `api.ts` updates; the `tokens.css` palette swap (Component 6). Tests. (The theme swap is independent of the other frontend work and can land first or last within this phase.)

Each phase leaves the app runnable and tests green before the next.
