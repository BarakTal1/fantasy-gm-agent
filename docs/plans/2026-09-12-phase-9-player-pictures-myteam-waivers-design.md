# Phase 9 — Player Pictures, My Team Cards & Waivers Weekday/Targets (Design)

> **Status:** Design/spec. Implementation plan follows via `writing-plans`.

## Goal

Four adjustments to the live app:

1. **Player pictures** — attach a headshot `image_url` to every `Player`, sourced from a committed `player_images` table (auto-derived NBA CDN headshots for demo; Yahoo's `image_url` on live), with an initials-avatar fallback. Pictures render wherever players appear as cards/rows.
2. **My Team tab** — show a per-player card for each of your players (picture, team, games this week, a projected upcoming-week stat line, and a **form tag**: buy-low / sell-high / neutral). Order: **player cards first, then the you-vs-league radar**.
3. **Waivers tab** — move the **weekday analysis** here from My Team, and add a **"Teams to target on thin days"** section: the NBA teams that play on your thin weekdays, cross-referenced with the available free agents from those teams.
4. **Weekday overload warning** — flag days where **more than 10** of your players play (wasted production, since only ~10 start).

## Non-goals (YAGNI)

- No new external services; NBA CDN headshot URLs are derived from the existing NBA person-ids (no image files hosted by us). No image proxying.
- Avatars render in **card/list** player displays (My Team cards, Trade offer/suggestion/received cards, Teams-to-target FAs). Bar-chart/streaming rows stay text — there's no room for an avatar in a bar row, and forcing one would break those layouts. This is the practical reading of "everywhere players render."
- No change to the trade engine, proposals, or buy-low/sell-high formula (reused as-is for the form tag).

---

## Component A — Player pictures

### Schema
Add an optional field to `Player` (`src/fantasy_gm/schemas.py`):
```python
image_url: str | None = None
```
Optional + defaulted, so every existing `Player(...)` construction keeps working.

### Resolver + table (`src/fantasy_gm/player_images.py`)
- A committed table `demo_data/player_images.json` mapping `player_id -> url`, generated from the demo roster + free-agent ids via a small script (`scripts/gen_player_images.py`) using the official NBA CDN headshot pattern `https://cdn.nba.com/headshots/nba/latest/260x190/{id}.png`.
- `resolve_image(player_id) -> str | None`:
  - Reads the cached table; returns the mapped url if present.
  - Else, if the id is all-digits (an NBA person-id), derives the same CDN url from it.
  - Else returns `None` (frontend shows an initials avatar).

### Attach at the data boundary
- **Demo:** `demo._player(d)` sets `image_url=player_images.resolve_image(d["player_id"])`.
- **Live Yahoo (gated):** `client._parse_player` sets `image_url=_meta(meta, "image_url") or None` (Yahoo supplies a headshot url in player metadata; re-verify on approval — same validate-on-approval convention as the rest of `yahoo_client`).

### Frontend
- `Player` TS type gains `image_url?: string | null`.
- New `<PlayerAvatar name image_url size? />` component: renders an `<img>` with `onError` → a generated **initials circle** (first letters of the name, token-colored background). Used on My Team cards, Trade offer/suggestion/received cards, and Teams-to-target FA chips.

---

## Component B — My Team per-player cards

### Analytics (`analytics.py`)
New `roster_week_outlook(roster, trends, games, settings) -> list[dict]`:
- `form` tag from the existing engine: `buy_low_sell_high(roster, trends, settings.categories)` → map each player's `signal` to `buy_low`/`sell_high`, default `neutral`.
- Projection (upcoming week), reusing the `streaming_board` pattern (`recent form × games this week`):
  - **Category:** `projected` = `{c: round(form.get(c,0)*g, 1)}` for each non-`%` category.
  - **Points:** `projected_points` = `round(fantasy_points(form, point_weights) * g, 1)`.
- Each row: `{player_id, name, nba_team, image_url, games, form, projected | projected_points}` (`image_url` read from the `Player` object).

### Endpoint (`/analytics/my-team`)
- **Remove** `weekdays` from this endpoint (moves to Waivers).
- **Add** `roster` = `roster_week_outlook(mine.players, roster_trends, _week_games(), league)`.
- Keep `category_profile` (category leagues only). Needs `_trends_for(my roster ids)` + `_week_games()`.

### View (`MyTeamView.tsx`)
- Render **roster cards first** (avatar, name + team, games-this-week, projected stat line, form-tag pill), **then** the you-vs-league radar below. Remove `WeekdayBars` from this view.
- Form-tag pill styling reuses the buy/sell color language already in `DivergingList` (`--accent` for buy-low, `--danger` for sell-high, muted for neutral).

---

## Component C — Waivers weekday analysis + teams-to-target + overload

### `weekday_coverage` gains overload flag (`analytics.py`)
```python
def weekday_coverage(roster, day_teams, weak_threshold=4, heavy_threshold=10):
    ...
    out.append({"day": d, "count": count,
                "weak": len(teams) > 0 and count <= weak_threshold,
                "heavy": count > heavy_threshold})
```
Each day now returns `{day, count, weak, heavy}`.

### `teams_to_target` (`analytics.py`)
New `teams_to_target(roster, free_agents, day_teams, settings, weak_threshold=4, limit_fas=3) -> list[dict]`:
1. Compute `weekday_coverage` → the thin (`weak`) days.
2. For each thin day, collect the NBA teams playing that day (`day_teams[day]`); accumulate, per team, the thin days it covers (kept in Mon→Sun order).
3. Index free agents by `nba_team`; for each target team, take the top `limit_fas` available FAs by `scoring.player_value`. **Skip teams with no available FA** (nothing to add).
4. Return `[{nba_team, weak_days:[...], free_agents:[{player_id,name,nba_team,image_url}]}]`, sorted by (number of thin days covered, number of FAs) descending.

### Endpoint (`/analytics/waivers`)
Add to the existing payload:
- `weekdays` = `weekday_coverage(mine.players, day_teams)` (now with `heavy`).
- `teams_to_target` = `teams_to_target(mine.players, fas, day_teams, league)`.
(`day_teams` read from `demo_data/schedule_by_day.json`, as My Team did before.)

### Views
- `WeekdayBars` (`components/charts/WeekdayBars.tsx`): also flag **heavy** days — a distinct "overloaded" style + a hint line ("10+ players on Mon — wasted production, spread your games out"). The accessible table gains an "Overloaded" column. `WeekdayCoverage` TS type gains `heavy: boolean`.
- `WaiversView.tsx`: render the existing boards, **add** `WeekdayBars` (fed by `data.weekdays`), **add** a "Teams to target on thin days" section (each team → its thin days + FA chips with avatars). Empty-state when `teams_to_target` is empty (e.g. no thin days).

---

## Data-shape contracts (backend ↔ frontend)

| Endpoint | Removed | Added |
|---|---|---|
| `/analytics/my-team` | `weekdays` | `roster: RosterOutlookRow[]` |
| `/analytics/waivers` | — | `weekdays: WeekdayCoverage[]`, `teams_to_target: TeamTarget[]` |

- `RosterOutlookRow` = `{player_id, name, nba_team, image_url: string|null, games, form: "buy_low"|"sell_high"|"neutral", projected?: Record<string,number>, projected_points?: number}`.
- `TeamTarget` = `{nba_team, weak_days: string[], free_agents: {player_id,name,nba_team,image_url}[]}`.
- `WeekdayCoverage` gains `heavy: boolean`.
- `Player` (TS) gains `image_url?: string | null`.

## Error handling
- `resolve_image` is total (returns `None` on anything non-derivable); `PlayerAvatar` always renders (initials fallback on null or `<img>` error).
- New analytics fns are pure and total: empty roster / no thin days / no FAs → empty lists; views render empty states.
- `teams_to_target` only surfaces teams with an addable FA, so it never points you at a dead end.

## Testing
- `tests/test_analytics.py`: `roster_week_outlook` (projection math, form tag mapping, points vs category), `weekday_coverage` heavy flag, `teams_to_target` (thin-day→team→FA join, skip-empty, ordering).
- `tests/test_player_images.py` (new): table lookup, derive-from-id, `None` for non-numeric unknown id.
- `tests/test_api.py`: `/analytics/my-team` returns `roster` and no longer `weekdays`; `/analytics/waivers` returns `weekdays` + `teams_to_target`.
- Frontend: `PlayerAvatar` (renders img; falls back to initials on error), MyTeamView (roster cards + radar order), WaiversView (weekday bars + teams-to-target), WeekdayBars heavy flag.

## Phasing (one plan, ordered)
1. **Pictures** — schema field, `player_images.py` + generator script + generated table, attach in demo/live loaders. Tests.
2. **My Team analytics** — `roster_week_outlook`; `/analytics/my-team` (drop weekdays, add roster). Tests.
3. **Waivers analytics** — `weekday_coverage` heavy flag; `teams_to_target`; `/analytics/waivers` additions. Tests.
4. **Frontend** — `image_url` type + `PlayerAvatar`; MyTeamView cards+radar; WaiversView weekday+teams; WeekdayBars heavy; api.ts type updates. Tests + build.

Each phase leaves the app runnable and green before the next.
