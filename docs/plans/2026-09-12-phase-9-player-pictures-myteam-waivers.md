# Phase 9 — Player Pictures, My Team Cards & Waivers Weekday/Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Attach headshots to every player, turn My Team into per-player cards (projected week stats + form tag) followed by the radar, and move the weekday analysis to Waivers with a teams-to-target section and an overload (10+) warning.

**Architecture:** Backend stays pure-function + demo-shell/live-gated. `Player` gains an optional `image_url`; a `player_images` resolver fills it (NBA CDN derived for demo, Yahoo field on live). Two new analytics fns (`roster_week_outlook`, `teams_to_target`) and a `weekday_coverage` flag. Frontend adds a `PlayerAvatar` and reworks the My Team / Waivers views.

**Tech Stack:** Existing (Python/FastAPI/pytest; Vite+React+TS/Vitest). No new deps.

**Design doc:** [docs/plans/2026-09-12-phase-9-player-pictures-myteam-waivers-design.md](2026-09-12-phase-9-player-pictures-myteam-waivers-design.md)

**Run commands:** backend `uv run pytest <path> -q`, lint `uv run ruff check src tests`; frontend (inside `frontend/`) `npx vitest run <path>`, build `npm run build`.

---

## File Structure
- Modify `src/fantasy_gm/schemas.py` — add `Player.image_url`.
- Create `src/fantasy_gm/player_images.py` — headshot resolver.
- Create `scripts/gen_player_images.py` — generate the committed table.
- Create `demo_data/player_images.json` — generated table (id → url).
- Modify `src/fantasy_gm/demo.py` — set `image_url` in `_player`.
- Modify `src/fantasy_gm/yahoo_client/client.py` — set `image_url` in `_parse_player` (live-gated).
- Modify `src/fantasy_gm/analytics.py` — `roster_week_outlook`, `teams_to_target`, `weekday_coverage` heavy flag.
- Modify `src/fantasy_gm/api.py` — `/analytics/my-team` + `/analytics/waivers` payloads.
- Tests: `tests/test_player_images.py` (new), `tests/test_analytics.py`, `tests/test_api.py`.
- Frontend: `src/lib/api.ts` (types), `src/components/PlayerAvatar.tsx` (new), `src/views/MyTeamView.tsx`, `src/views/WaiversView.tsx`, `src/components/charts/WeekdayBars.tsx`, `src/views/TradeView.tsx`; tests under `src/__tests__/`.

---

## PHASE 1 — Player pictures

### Task 1: `Player.image_url` + resolver

**Files:** Modify `src/fantasy_gm/schemas.py`; Create `src/fantasy_gm/player_images.py`; Test `tests/test_player_images.py`

- [ ] **Step 1: Add the field to `Player`** in `schemas.py` (after the `stats` line, before `def stat`):

```python
    image_url: str | None = None       # headshot; resolved at the data boundary
```

- [ ] **Step 2: Write the failing test** `tests/test_player_images.py`

```python
from fantasy_gm import player_images


def test_resolve_from_table(tmp_path, monkeypatch):
    monkeypatch.setattr(player_images, "_TABLE", {"203999": "http://example/jokic.png"})
    assert player_images.resolve_image("203999") == "http://example/jokic.png"


def test_derive_from_numeric_id(monkeypatch):
    monkeypatch.setattr(player_images, "_TABLE", {})
    url = player_images.resolve_image("1626164")
    assert url == "https://cdn.nba.com/headshots/nba/latest/260x190/1626164.png"


def test_none_for_unknown_non_numeric(monkeypatch):
    monkeypatch.setattr(player_images, "_TABLE", {})
    assert player_images.resolve_image("yahoo-abc") is None
```

- [ ] **Step 3: Run it, confirm it fails**

Run: `uv run pytest tests/test_player_images.py -q`
Expected: FAIL (`No module named 'fantasy_gm.player_images'`).

- [ ] **Step 4: Implement `src/fantasy_gm/player_images.py`**

```python
"""Player headshot resolver.

A committed table (demo_data/player_images.json) maps player_id -> headshot URL;
it's generated from the demo roster/FA ids (see scripts/gen_player_images.py)
using the official NBA CDN pattern. For any id missing from the table we derive
the same CDN URL when the id is an NBA person-id (all digits); otherwise return
None and let the UI fall back to an initials avatar. On live Yahoo data the
image comes from Yahoo's own player metadata instead (see yahoo_client.client).
"""
import json
from functools import cache
from pathlib import Path

_DEMO_DIR = Path(__file__).resolve().parent.parent.parent / "demo_data"
_CDN = "https://cdn.nba.com/headshots/nba/latest/260x190/{id}.png"


@cache
def _load_table() -> dict[str, str]:
    path = _DEMO_DIR / "player_images.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text())


# Module-level handle so tests can monkeypatch a table in place.
_TABLE = _load_table()


def resolve_image(player_id: str) -> str | None:
    if player_id in _TABLE:
        return _TABLE[player_id]
    if player_id.isdigit():
        return _CDN.format(id=player_id)
    return None
```

- [ ] **Step 5: Run it, confirm it passes**

Run: `uv run pytest tests/test_player_images.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/schemas.py src/fantasy_gm/player_images.py tests/test_player_images.py
git commit -m "feat(players): Player.image_url + headshot resolver (table/derive/none)"
```

---

### Task 2: Generate the table + attach image_url in loaders

**Files:** Create `scripts/gen_player_images.py`; Create `demo_data/player_images.json` (generated); Modify `src/fantasy_gm/demo.py`, `src/fantasy_gm/yahoo_client/client.py`; Test `tests/test_demo.py`

- [ ] **Step 1: Write the generator** `scripts/gen_player_images.py`

```python
"""Generate demo_data/player_images.json from the demo roster + free agents.

Maps every demo player_id to its official NBA CDN headshot URL. Re-run if the
demo league is regenerated: `uv run python scripts/gen_player_images.py`.
"""
import json
from pathlib import Path

DEMO = Path(__file__).resolve().parent.parent / "demo_data"
CDN = "https://cdn.nba.com/headshots/nba/latest/260x190/{id}.png"


def main() -> None:
    ids: set[str] = set()
    league = json.loads((DEMO / "league.json").read_text())
    for team in league["teams"]:
        for p in team["players"]:
            ids.add(p["player_id"])
    fas = json.loads((DEMO / "free_agents.json").read_text())
    for p in fas["players"]:
        ids.add(p["player_id"])
    table = {pid: CDN.format(id=pid) for pid in sorted(ids)}
    (DEMO / "player_images.json").write_text(json.dumps(table, indent=2) + "\n")
    print(f"wrote {len(table)} entries to demo_data/player_images.json")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Generate the table**

Run: `uv run python scripts/gen_player_images.py`
Expected: prints "wrote N entries…" and creates `demo_data/player_images.json`. Open it and confirm it's a JSON object of `"<id>": "https://cdn.nba.com/headshots/nba/latest/260x190/<id>.png"`.

- [ ] **Step 3: Attach in `demo._player`** — replace the `_player` function in `src/fantasy_gm/demo.py`:

```python
def _player(d: dict) -> Player:
    from fantasy_gm import player_images
    return Player(player_id=d["player_id"], name=d["name"], nba_team=d["nba_team"],
                  positions=d.get("positions", []), stats=d["stats"],
                  image_url=player_images.resolve_image(d["player_id"]))
```

- [ ] **Step 4: Attach in live `_parse_player`** — in `src/fantasy_gm/yahoo_client/client.py`, add `image_url` to the `Player(...)` built in `_parse_player` (Yahoo supplies it in player metadata; validate on approval):

```python
    return Player(
        player_id=_meta(meta, "player_id"),
        name=name["full"] if isinstance(name, dict) else name,
        nba_team=_meta(meta, "editorial_team_abbr"),
        positions=_positions(meta),
        stats={s["stat"]["stat_id"]: float(s["stat"]["value"] or 0) for s in stats},
        image_url=_meta(meta, "image_url") or None,
    )
```
(`_meta` returns `""` when absent, so `or None` normalizes to `None`.)

- [ ] **Step 5: Write the failing test** — append to `tests/test_demo.py`:

```python
def test_demo_players_have_headshots():
    from fantasy_gm import demo
    teams = demo.demo_teams()
    p = teams[0].players[0]
    assert p.image_url and p.image_url.startswith("https://cdn.nba.com/headshots/")
    fas = demo.demo_free_agents()
    assert fas[0].image_url and fas[0].image_url.startswith("https://cdn.nba.com/")
```

- [ ] **Step 6: Run tests, confirm pass**

Run: `uv run pytest tests/test_demo.py -q`
Expected: PASS. Then `uv run pytest -q` — full suite still green.

- [ ] **Step 7: Commit**

```bash
git add scripts/gen_player_images.py demo_data/player_images.json src/fantasy_gm/demo.py src/fantasy_gm/yahoo_client/client.py tests/test_demo.py
git commit -m "feat(players): generate headshot table; attach image_url in demo + live loaders"
```

---

## PHASE 2 — My Team per-player cards

### Task 3: `roster_week_outlook`

**Files:** Modify `src/fantasy_gm/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_analytics.py` (the `_p`, `LeagueSettings` imports already exist at top):

```python
def test_roster_week_outlook_category_projects_and_tags():
    from fantasy_gm.analytics import roster_week_outlook
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    roster = [_p("1", PTS=20, AST=5)]
    trends = {"1": {"PTS": 10.0, "AST": 2.0}}        # cold vs season -> buy_low
    games = {"LAL": 3}                                # _p defaults nba_team="LAL"
    rows = roster_week_outlook(roster, trends, games, cat)
    assert rows[0]["games"] == 3
    assert rows[0]["projected"]["PTS"] == 30.0        # recent 10 * 3 games
    assert rows[0]["form"] == "buy_low"


def test_roster_week_outlook_points_and_neutral():
    from fantasy_gm.analytics import roster_week_outlook
    pts = LeagueSettings(league_key="k", format="points", categories=["PTS"],
                         point_weights={"PTS": 1.0})
    roster = [_p("1", PTS=20)]
    rows = roster_week_outlook(roster, trends={}, games={"LAL": 4}, settings=pts)
    assert rows[0]["projected_points"] == 80.0        # season 20 (no trend) * 4
    assert rows[0]["form"] == "neutral"               # no trend -> no signal
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `uv run pytest tests/test_analytics.py -k roster_week_outlook -q`
Expected: FAIL (function missing).

- [ ] **Step 3: Implement `roster_week_outlook`** in `analytics.py` (add after `points_value_board`; `scoring` and `buy_low_sell_high` are already in this module):

```python
def roster_week_outlook(roster: list[Player], trends: dict[str, dict],
                        games: dict[str, int], settings: LeagueSettings) -> list[dict]:
    """Per roster player: games this week, a projected-week stat line, and a
    form tag (buy_low / sell_high / neutral) from the buy-low/sell-high engine."""
    signal = {r["player_id"]: r["signal"]
              for r in buy_low_sell_high(roster, trends, settings.categories)}
    rows = []
    for p in roster:
        form = trends.get(p.player_id) or dict(p.stats)
        g = games.get(p.nba_team, 0)
        row = {"player_id": p.player_id, "name": p.name, "nba_team": p.nba_team,
               "image_url": p.image_url, "games": g,
               "form": signal.get(p.player_id, "neutral")}
        if settings.is_points:
            row["projected_points"] = round(
                scoring.fantasy_points(form, settings.point_weights) * g, 1)
        else:
            row["projected"] = {c: round(form.get(c, 0.0) * g, 1)
                                for c in settings.categories if not c.endswith("%")}
        rows.append(row)
    return rows
```

- [ ] **Step 4: Run tests, confirm pass**

Run: `uv run pytest tests/test_analytics.py -k roster_week_outlook -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): roster_week_outlook (projected week stats + form tag)"
```

---

### Task 4: `/analytics/my-team` — drop weekdays, add roster

**Files:** Modify `src/fantasy_gm/api.py`; Test `tests/test_api.py`

- [ ] **Step 1: Update the my-team test** in `tests/test_api.py` — in `test_my_team_analytics_category`, REMOVE the line `assert len(body["weekdays"]) == 7` and add:

```python
    assert body["roster"][0]["form"] in {"buy_low", "sell_high", "neutral"}
    assert "games" in body["roster"][0]
    assert "weekdays" not in body            # weekdays moved to /analytics/waivers
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `uv run pytest tests/test_api.py::test_my_team_analytics_category -q`
Expected: FAIL (`roster` missing / `weekdays` still present).

- [ ] **Step 3: Rewrite the `analytics_my_team` endpoint** in `api.py`:

```python
@app.get("/analytics/my-team")
def analytics_my_team(request: Request) -> dict:
    league = _league_for(request)
    teams = _all_teams()
    mine = next((t for t in teams if t.team_key == MY_TEAM_KEY), teams[0])
    games = _week_games()
    roster_trends = _trends_for([p.player_id for p in mine.players])
    out = {"format": league.format,
           "roster": analytics.roster_week_outlook(
               mine.players, roster_trends, games, league)}
    if league.is_category:
        out["category_profile"] = analytics.category_profile(
            mine, teams, league.categories)
    return out
```
(The `json`/`_DEMO_DIR`/`schedule_by_day` read is no longer used here — it moves to waivers in Task 6. Leave the imports; they're still used elsewhere.)

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_api.py::test_my_team_analytics_category -q`
Expected: PASS. Then `uv run pytest tests/test_api.py -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat(api): /analytics/my-team returns per-player roster outlook (weekdays move out)"
```

---

## PHASE 3 — Waivers weekday + teams-to-target

### Task 5: `weekday_coverage` heavy flag + `teams_to_target`

**Files:** Modify `src/fantasy_gm/analytics.py`; Test `tests/test_analytics.py`

- [ ] **Step 1: Write failing tests** — append to `tests/test_analytics.py`:

```python
def test_weekday_coverage_flags_overloaded_days():
    from fantasy_gm.analytics import weekday_coverage
    from fantasy_gm.schemas import Player
    roster = [Player(player_id=str(i), name=f"P{i}", nba_team="LAL") for i in range(11)]
    day_teams = {"Mon": ["LAL"], "Tue": ["BOS"]}
    cov = {c["day"]: c for c in weekday_coverage(roster, day_teams)}
    assert cov["Mon"]["count"] == 11 and cov["Mon"]["heavy"] is True
    assert cov["Tue"]["heavy"] is False


def test_teams_to_target_joins_thin_days_to_free_agents():
    from fantasy_gm.analytics import teams_to_target
    from fantasy_gm.schemas import LeagueSettings, Player
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS"])
    # Thin everywhere (roster tiny). PHX plays Wed+Fri; a PHX free agent exists.
    roster = [Player(player_id="r1", name="Mine", nba_team="LAL", stats={"PTS": 20})]
    day_teams = {"Wed": ["PHX"], "Fri": ["PHX", "BOS"]}
    fas = [Player(player_id="f1", name="Sun Guy", nba_team="PHX", stats={"PTS": 15}),
           Player(player_id="f2", name="Celtic", nba_team="BOS", stats={"PTS": 10})]
    out = teams_to_target(roster, fas, day_teams, cat)
    phx = next(t for t in out if t["nba_team"] == "PHX")
    assert phx["weak_days"] == ["Wed", "Fri"]
    assert phx["free_agents"][0]["name"] == "Sun Guy"
    assert phx["free_agents"][0]["nba_team"] == "PHX"


def test_teams_to_target_skips_teams_without_free_agents():
    from fantasy_gm.analytics import teams_to_target
    from fantasy_gm.schemas import LeagueSettings, Player
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS"])
    roster = [Player(player_id="r1", name="Mine", nba_team="LAL")]
    day_teams = {"Wed": ["PHX"]}
    out = teams_to_target(roster, free_agents=[], day_teams=day_teams, settings=cat)
    assert out == []
```

- [ ] **Step 2: Run them, confirm they fail**

Run: `uv run pytest tests/test_analytics.py -k "overloaded or teams_to_target" -q`
Expected: FAIL (heavy key missing / function missing).

- [ ] **Step 3: Add the heavy flag to `weekday_coverage`** — replace its signature + appended dict:

```python
def weekday_coverage(roster: list[Player], day_teams: dict[str, list[str]],
                     weak_threshold: int = 4, heavy_threshold: int = 10) -> list[dict]:
    """Per weekday: how many of my players have an NBA game that day.

    Thin days (few players playing) are flagged to stream a waiver player in;
    heavy days (more than heavy_threshold playing) are flagged as wasted
    production — only ~10 roster slots start. `day_teams` maps a weekday abbrev
    (Mon..Sun) to the NBA teams playing that day.
    """
    out = []
    for d in _DAYS:
        teams = set(day_teams.get(d, []))
        count = sum(1 for p in roster if p.nba_team in teams)
        out.append({"day": d, "count": count,
                    "weak": len(teams) > 0 and count <= weak_threshold,
                    "heavy": count > heavy_threshold})
    return out
```

- [ ] **Step 4: Add `teams_to_target`** immediately after `weekday_coverage`:

```python
def teams_to_target(roster: list[Player], free_agents: list[Player],
                    day_teams: dict[str, list[str]], settings: LeagueSettings,
                    weak_threshold: int = 4, limit_fas: int = 3) -> list[dict]:
    """NBA teams that play on your thin weekdays, with their available free agents.

    For each thin day, the teams playing that day are candidates — adding one of
    their players fills an empty slot on that day. Teams with no available free
    agent are skipped (nothing to add). Sorted by thin-days-covered then FA count.
    """
    cov = weekday_coverage(roster, day_teams, weak_threshold)
    weak_days = [c["day"] for c in cov if c["weak"]]
    team_days: dict[str, list[str]] = {}
    for d in weak_days:                       # _DAYS order preserved by weekday_coverage
        for t in day_teams.get(d, []):
            team_days.setdefault(t, [])
            if d not in team_days[t]:
                team_days[t].append(d)
    fas_by_team: dict[str, list[Player]] = {}
    for p in free_agents:
        fas_by_team.setdefault(p.nba_team, []).append(p)
    out = []
    for team, days in team_days.items():
        fas = sorted(fas_by_team.get(team, []),
                     key=lambda p: scoring.player_value(p, settings), reverse=True)[:limit_fas]
        if not fas:
            continue
        out.append({"nba_team": team, "weak_days": days,
                    "free_agents": [{"player_id": p.player_id, "name": p.name,
                                     "nba_team": p.nba_team, "image_url": p.image_url}
                                    for p in fas]})
    out.sort(key=lambda r: (len(r["weak_days"]), len(r["free_agents"])), reverse=True)
    return out
```

- [ ] **Step 5: Run tests, confirm pass**

Run: `uv run pytest tests/test_analytics.py -q`
Expected: PASS (new + existing, including the original `test_weekday_coverage_flags_thin_days` which doesn't check `heavy`).

- [ ] **Step 6: Commit**

```bash
git add src/fantasy_gm/analytics.py tests/test_analytics.py
git commit -m "feat(analytics): weekday overload flag + teams_to_target"
```

---

### Task 6: `/analytics/waivers` — add weekdays + teams_to_target

**Files:** Modify `src/fantasy_gm/api.py`; Test `tests/test_api.py`

- [ ] **Step 1: Update the waivers test** in `tests/test_api.py` — in `test_waivers_analytics_category`, add:

```python
    assert len(body["weekdays"]) == 7
    assert "teams_to_target" in body and isinstance(body["teams_to_target"], list)
```

- [ ] **Step 2: Run it, confirm it fails**

Run: `uv run pytest tests/test_api.py::test_waivers_analytics_category -q`
Expected: FAIL (`weekdays` missing).

- [ ] **Step 3: Extend `analytics_waivers`** in `api.py` — after the existing board logic, before `return out`, add the weekday + targets (and the `day_teams` read):

```python
    day_teams = json.loads((_DEMO_DIR / "schedule_by_day.json").read_text())
    out["weekdays"] = analytics.weekday_coverage(mine.players, day_teams)
    out["teams_to_target"] = analytics.teams_to_target(mine.players, fas, day_teams, league)
    return out
```
(`mine`, `fas`, `league` are already in scope in that endpoint; `json` and `_DEMO_DIR` are imported at module top.)

- [ ] **Step 4: Run it, confirm pass**

Run: `uv run pytest tests/test_api.py::test_waivers_analytics_category -q`
Expected: PASS. Then `uv run pytest -q && uv run ruff check src tests` — all green.

- [ ] **Step 5: Commit**

```bash
git add src/fantasy_gm/api.py tests/test_api.py
git commit -m "feat(api): /analytics/waivers adds weekday coverage + teams_to_target"
```

---

## PHASE 4 — Frontend

### Task 7: `image_url` type + `PlayerAvatar`

**Files:** Modify `frontend/src/lib/api.ts`; Create `frontend/src/components/PlayerAvatar.tsx`; Test `frontend/src/__tests__/playeravatar.test.tsx`

- [ ] **Step 1: Add `image_url` to the `Player` TS type** in `api.ts` (inside `export interface Player`):

```typescript
  image_url?: string | null;
```

- [ ] **Step 2: Write the failing test** `frontend/src/__tests__/playeravatar.test.tsx`

```typescript
import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { PlayerAvatar } from "../components/PlayerAvatar";

describe("PlayerAvatar", () => {
  it("renders an image when image_url is present", () => {
    render(<PlayerAvatar name="Devin Booker" image_url="http://x/booker.png" />);
    const img = screen.getByRole("img", { name: /devin booker/i }) as HTMLImageElement;
    expect(img.src).toContain("booker.png");
  });

  it("falls back to initials when no url", () => {
    render(<PlayerAvatar name="Devin Booker" image_url={null} />);
    expect(screen.getByText("DB")).toBeInTheDocument();
  });

  it("falls back to initials when the image errors", () => {
    render(<PlayerAvatar name="Kevin Durant" image_url="http://x/broken.png" />);
    fireEvent.error(screen.getByRole("img", { name: /kevin durant/i }));
    expect(screen.getByText("KD")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run it, confirm it fails** (module missing).

Run (inside `frontend/`): `npx vitest run src/__tests__/playeravatar.test.tsx`

- [ ] **Step 4: Implement `frontend/src/components/PlayerAvatar.tsx`**

```tsx
import { useState } from "react";

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? parts[parts.length - 1][0] : "";
  return (first + last).toUpperCase() || "?";
}

/** Player headshot with an initials-circle fallback (no url, or image error). */
export function PlayerAvatar({ name, image_url, size = 40 }:
  { name: string; image_url?: string | null; size?: number }) {
  const [failed, setFailed] = useState(false);
  const dim = { width: size, height: size };
  if (!image_url || failed) {
    return (
      <span className="avatar avatar-fallback" style={dim} aria-label={name} role="img">
        {initials(name)}
      </span>
    );
  }
  return (
    <img className="avatar" style={dim} src={image_url} alt={name}
         loading="lazy" onError={() => setFailed(true)} />
  );
}
```

- [ ] **Step 5: Add avatar styles** to `frontend/src/styles/app.css` (near the other component styles):

```css
.avatar { border-radius: 50%; object-fit: cover; background: var(--surface-2);
  border: 1px solid var(--border); flex: none; }
.avatar-fallback { display: inline-grid; place-items: center; font-size: 13px;
  font-weight: 700; color: var(--on-primary); background: var(--primary); }
```

- [ ] **Step 6: Run the test, confirm pass**

Run (inside `frontend/`): `npx vitest run src/__tests__/playeravatar.test.tsx`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/components/PlayerAvatar.tsx frontend/src/__tests__/playeravatar.test.tsx frontend/src/styles/app.css
git commit -m "feat(ui): PlayerAvatar with initials fallback + image_url on Player"
```

---

### Task 8: api.ts types for the new payloads

**Files:** Modify `frontend/src/lib/api.ts`

- [ ] **Step 1: Update `WeekdayCoverage`** to add the heavy flag:

```typescript
export interface WeekdayCoverage { day: string; count: number; weak: boolean; heavy: boolean }
```

- [ ] **Step 2: Replace the `getMyTeamAnalytics` return type** (drop `weekdays`, add `roster`):

```typescript
export interface RosterOutlookRow {
  player_id: string; name: string; nba_team: string; image_url?: string | null;
  games: number; form: "buy_low" | "sell_high" | "neutral";
  projected?: Record<string, number>; projected_points?: number;
}
export async function getMyTeamAnalytics() {
  return jget("/analytics/my-team") as Promise<{
    format: "category" | "points";
    roster: RosterOutlookRow[];
    category_profile?: CategoryProfile;
  }>;
}
```

- [ ] **Step 3: Extend the `getWaiversAnalytics` return type** (add `weekdays` + `teams_to_target`):

```typescript
export interface TeamTarget {
  nba_team: string; weak_days: string[];
  free_agents: { player_id: string; name: string; nba_team: string; image_url?: string | null }[];
}
```
And inside the `getWaiversAnalytics` return Promise type, add these two fields alongside the existing ones:
```typescript
    weekdays: WeekdayCoverage[];
    teams_to_target: TeamTarget[];
```

- [ ] **Step 4: Type-check**

Run (inside `frontend/`): `npx tsc --noEmit`
Expected: clean (views updated in later tasks; these type additions alone compile since the views using them are rewritten next — if tsc reports errors ONLY in MyTeamView/WaiversView about the removed `weekdays`, that's expected and fixed in Tasks 9-10; proceed).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(ui-api): types for roster outlook, weekday heavy flag, teams_to_target"
```

---

### Task 9: MyTeamView — roster cards then radar

**Files:** Modify `frontend/src/views/MyTeamView.tsx`; Test `frontend/src/__tests__/myteam.test.tsx`

- [ ] **Step 1: Rewrite `myteam.test.tsx`** to the new shape:

```typescript
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as api from "../lib/api";
import { MyTeamView } from "../views/MyTeamView";

describe("MyTeamView", () => {
  it("renders per-player cards (form tag + projected) then the radar", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "category",
      roster: [{ player_id: "1", name: "Devin Booker", nba_team: "PHX",
        image_url: null, games: 4, form: "sell_high", projected: { PTS: 120, AST: 20 } }],
      category_profile: { PTS: { you: 110, league_avg: 100 } },
    });
    render(<MyTeamView />);
    expect(await screen.findByText(/Devin Booker/)).toBeInTheDocument();
    expect(screen.getByText(/sell high/i)).toBeInTheDocument();
    expect(screen.getAllByText(/PTS/).length).toBeGreaterThan(0);  // projected + radar
  });

  it("renders projected points for points leagues", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockResolvedValue({
      format: "points",
      roster: [{ player_id: "1", name: "A B", nba_team: "LAL",
        image_url: null, games: 3, form: "neutral", projected_points: 99 }],
    });
    render(<MyTeamView />);
    expect(await screen.findByText("99")).toBeInTheDocument();
  });

  it("shows an error state with retry on failure", async () => {
    vi.spyOn(api, "getMyTeamAnalytics").mockRejectedValue(new Error("HTTP 500"));
    render(<MyTeamView />);
    expect(await screen.findByRole("alert")).toHaveTextContent(/failed to load/i);
  });
});
```

- [ ] **Step 2: Run it, confirm it fails.**

Run (inside `frontend/`): `npx vitest run src/__tests__/myteam.test.tsx`

- [ ] **Step 3: Rewrite `MyTeamView.tsx`**

```tsx
import { useEffect, useState } from "react";
import { getMyTeamAnalytics, type RosterOutlookRow } from "../lib/api";
import { RadarChart } from "../components/charts/RadarChart";
import { PlayerAvatar } from "../components/PlayerAvatar";
import { ErrorBanner } from "../components/ErrorBanner";

type Payload = Awaited<ReturnType<typeof getMyTeamAnalytics>>;

const FORM_LABEL = { buy_low: "buy low", sell_high: "sell high", neutral: "neutral" } as const;

function RosterCard({ p }: { p: RosterOutlookRow }) {
  const proj = p.projected
    ? Object.entries(p.projected).filter(([c]) => c !== "TO")
        .map(([c, v]) => `${c} ${v}`).join(" · ")
    : `${p.projected_points ?? 0} pts`;
  return (
    <li className="roster-card">
      <PlayerAvatar name={p.name} image_url={p.image_url} />
      <div className="roster-main">
        <div className="roster-name">{p.name} <em>{p.nba_team} · {p.games} gm</em></div>
        <div className="roster-proj">{proj}</div>
      </div>
      <span className={`form-tag form-${p.form}`}>{FORM_LABEL[p.form]}</span>
    </li>
  );
}

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
      </div>
    );
  }

  const cats = data.category_profile ? Object.keys(data.category_profile) : [];
  const you = cats.map((c) => data.category_profile![c].you);
  const league = cats.map((c) => data.category_profile![c].league_avg);

  return (
    <div className="dashboard">
      <figure className="chart">
        <figcaption>Your roster — this week</figcaption>
        <ul className="roster-list">
          {data.roster.map((p) => <RosterCard key={p.player_id} p={p} />)}
        </ul>
      </figure>
      {cats.length > 0 && <RadarChart cats={cats} you={you} league={league} />}
    </div>
  );
}
```

- [ ] **Step 4: Add roster-card + form-tag styles** to `frontend/src/styles/app.css`:

```css
.roster-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 8px; }
.roster-card { display: flex; align-items: center; gap: 12px; padding: 8px 10px;
  border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); }
.roster-main { flex: 1; min-width: 0; }
.roster-name { font-weight: 600; } .roster-name em { font-style: normal; color: var(--muted); font-weight: 400; margin-left: 6px; }
.roster-proj { font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; }
.form-tag { font-size: 12px; font-weight: 700; padding: 3px 10px; border-radius: var(--radius-pill); white-space: nowrap; }
.form-buy_low { color: var(--accent); background: color-mix(in srgb, var(--accent) 14%, transparent); }
.form-sell_high { color: var(--danger); background: color-mix(in srgb, var(--danger) 14%, transparent); }
.form-neutral { color: var(--muted); background: color-mix(in srgb, var(--muted) 14%, transparent); }
```

- [ ] **Step 5: Run the test, confirm pass**

Run (inside `frontend/`): `npx vitest run src/__tests__/myteam.test.tsx`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/views/MyTeamView.tsx frontend/src/__tests__/myteam.test.tsx frontend/src/styles/app.css
git commit -m "feat(ui): My Team per-player cards (avatar, projected week, form tag) + radar"
```

---

### Task 10: WeekdayBars overload + Waivers weekday/teams sections

**Files:** Modify `frontend/src/components/charts/WeekdayBars.tsx`, `frontend/src/views/WaiversView.tsx`; Test `frontend/src/__tests__/waivers.test.tsx`, `frontend/src/__tests__/weekdaybars.test.tsx` (new)

- [ ] **Step 1: Write a WeekdayBars test** `frontend/src/__tests__/weekdaybars.test.tsx`

```typescript
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { WeekdayBars } from "../components/charts/WeekdayBars";

describe("WeekdayBars", () => {
  it("flags thin and overloaded days", () => {
    render(<WeekdayBars days={[
      { day: "Mon", count: 12, weak: false, heavy: true },
      { day: "Tue", count: 2, weak: true, heavy: false },
      { day: "Wed", count: 6, weak: false, heavy: false },
    ]} />);
    expect(screen.getByText(/stream/i)).toBeInTheDocument();     // thin Tue
    expect(screen.getByText(/waste|overloaded|10\+/i)).toBeInTheDocument(); // heavy Mon
  });
});
```

- [ ] **Step 2: Update `WeekdayBars.tsx`** — add heavy handling (class, tag, hint, table column):

```tsx
import type { WeekdayCoverage } from "../../lib/api";

export function WeekdayBars({ days }: { days: WeekdayCoverage[] }) {
  const max = Math.max(1, ...days.map((d) => d.count));
  const weakDays = days.filter((d) => d.weak).map((d) => d.day);
  const heavyDays = days.filter((d) => d.heavy).map((d) => d.day);
  const hints = [];
  if (weakDays.length) hints.push(`Thin on ${weakDays.join(" & ")} — grab waiver players who play those days.`);
  if (heavyDays.length) hints.push(`Overloaded on ${heavyDays.join(" & ")} — 10+ players, wasted production; spread your games out.`);
  if (!hints.length) hints.push("Balanced coverage every day this week.");

  return (
    <figure className="chart">
      <figcaption>Games this week by day</figcaption>
      <div className="weekbars">
        {days.map((d) => (
          <div className={"weekcol" + (d.weak ? " weak" : "") + (d.heavy ? " heavy" : "")} key={d.day}>
            <span className="weekcount">{d.count}</span>
            <span className="weektrack">
              <span className="weekfill" style={{ height: `${(d.count / max) * 100}%` }} />
            </span>
            <span className="weekday">{d.day}</span>
            {d.weak && <span className="weektag">stream</span>}
            {d.heavy && <span className="weektag heavy">waste</span>}
          </div>
        ))}
      </div>
      {hints.map((h) => <p className="chart-hint" key={h}>{h}</p>)}
      <table className="sr-table">
        <caption>Players with a game each day this week</caption>
        <thead><tr><th>Day</th><th>Players</th><th>Thin</th><th>Overloaded</th></tr></thead>
        <tbody>{days.map((d) => (
          <tr key={d.day}><td>{d.day}</td><td>{d.count}</td>
            <td>{d.weak ? "yes" : "no"}</td><td>{d.heavy ? "yes" : "no"}</td></tr>
        ))}</tbody>
      </table>
    </figure>
  );
}
```

- [ ] **Step 3: Add a heavy-tag style** to `app.css` (near the existing `.weektag`):

```css
.weekcol.heavy .weekfill { background: var(--danger); }
.weektag.heavy { color: var(--danger); }
```

- [ ] **Step 4: Add Waivers tests** — append two tests to `frontend/src/__tests__/waivers.test.tsx` (extend the existing category mock to include the new fields, OR add new tests). Add:

```typescript
  it("renders weekday coverage and teams to target", async () => {
    vi.spyOn(api, "getWaiversAnalytics").mockResolvedValue({
      format: "category", schedule: { PHX: 4 }, recommended_pickups: [], streaming_board: [],
      weekdays: [{ day: "Wed", count: 3, weak: true, heavy: false },
                 { day: "Fri", count: 3, weak: true, heavy: false }],
      teams_to_target: [{ nba_team: "PHX", weak_days: ["Wed", "Fri"],
        free_agents: [{ player_id: "f1", name: "Sun Guy", nba_team: "PHX", image_url: null }] }],
    });
    render(<WaiversView />);
    expect(await screen.findByText(/Teams to target/i)).toBeInTheDocument();
    expect(screen.getByText(/Sun Guy/)).toBeInTheDocument();
    expect(screen.getAllByText(/PHX/).length).toBeGreaterThan(0);
  });
```
Also update the EXISTING two waivers tests' mocks to include `weekdays: []` and `teams_to_target: []` so they still type-check and render (the view reads these fields).

- [ ] **Step 5: Run, confirm new tests fail** (sections not rendered yet).

Run (inside `frontend/`): `npx vitest run src/__tests__/waivers.test.tsx src/__tests__/weekdaybars.test.tsx`

- [ ] **Step 6: Update `WaiversView.tsx`** — import the new pieces and restructure so the weekday/teams sections ALWAYS render (they're independent of free-agent recommendations).

Add imports near the top:
```typescript
import { WeekdayBars } from "../components/charts/WeekdayBars";
import { PlayerAvatar } from "../components/PlayerAvatar";
```

**Remove the `if (!hasContent) return <div className="empty">…</div>;` early return.** Keep the `hasContent` computation and the `board` computation, then replace the final `return (...)` with this — the boards show (or an inline empty note) while weekday coverage + teams-to-target always render:

```tsx
  return (
    <div className="dashboard">
      {hasContent ? (
        <>
          <BarList title={data.format === "points" ? "Points value board" : "Streaming board"}
                   items={board} />
          <RecommendedPickups items={data.recommended_pickups} />
        </>
      ) : (
        <div className="empty">No free-agent recommendations right now — check back after games tonight.</div>
      )}
      <GamesHeatmap games={data.schedule} />
      <WeekdayBars days={data.weekdays} />
      {data.teams_to_target.length > 0 && (
        <figure className="chart">
          <figcaption>Teams to target on thin days</figcaption>
          <ul className="target-list">
            {data.teams_to_target.map((t) => (
              <li key={t.nba_team} className="target-team">
                <div className="target-head">
                  <strong>{t.nba_team}</strong> <em>plays {t.weak_days.join(" & ")}</em>
                </div>
                <div className="target-fas">
                  {t.free_agents.map((p) => (
                    <span key={p.player_id} className="target-fa">
                      <PlayerAvatar name={p.name} image_url={p.image_url} size={24} /> {p.name}
                    </span>
                  ))}
                </div>
              </li>
            ))}
          </ul>
        </figure>
      )}
    </div>
  );
```

Note: the existing `waivers.test.tsx` "empty state" test asserts `/no recommendations/i` — the new copy "No free-agent recommendations…" still matches that regex, so it keeps passing; confirm when you run the suite.

- [ ] **Step 7: Add target-section styles** to `app.css`:

```css
.target-list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 10px; }
.target-team { padding: 8px 10px; border: 1px solid var(--border); border-radius: var(--radius-sm); background: var(--surface-2); }
.target-head em { font-style: normal; color: var(--muted); margin-left: 6px; }
.target-fas { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
.target-fa { display: inline-flex; align-items: center; gap: 6px; font-size: 13px; }
```

- [ ] **Step 8: Run the tests, confirm pass**

Run (inside `frontend/`): `npx vitest run src/__tests__/waivers.test.tsx src/__tests__/weekdaybars.test.tsx`
Expected: PASS (old + new).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/charts/WeekdayBars.tsx frontend/src/views/WaiversView.tsx frontend/src/__tests__/waivers.test.tsx frontend/src/__tests__/weekdaybars.test.tsx frontend/src/styles/app.css
git commit -m "feat(ui): Waivers weekday coverage (with overload) + teams-to-target"
```

---

### Task 11: Avatars on Trade cards + final gates

**Files:** Modify `frontend/src/views/TradeView.tsx`; verify full build + suites

- [ ] **Step 1: Add avatars to the Trade offer/suggestion/received cards** in `TradeView.tsx`. Import `PlayerAvatar`:
```typescript
import { PlayerAvatar } from "../components/PlayerAvatar";
```
In the received-offer and suggested-trade sections, the player names currently render as `<span className="selected-card ...">{p.name}</span>`. Wrap each with a small avatar so they read as `<span className="selected-card ..."><PlayerAvatar name={p.name} image_url={p.image_url} size={20} /> {p.name}</span>`. Apply to all four player lists (offer `they_give`/`they_want`, suggestion `give`/`get`). Keep the existing `give`/`get` CSS classes.

- [ ] **Step 2: Confirm the existing trade tests still pass**

Run (inside `frontend/`): `npx vitest run src/__tests__/trade.test.tsx`
Expected: PASS (the mocks' players have no `image_url`, so avatars render the initials fallback — name text is unchanged, so the assertions still match).

- [ ] **Step 3: Full frontend build + suite**

Run (inside `frontend/`): `npm run build` then `npx vitest run`
Expected: build clean; all suites pass.

- [ ] **Step 4: Full backend suite + lint**

Run: `uv run pytest -q && uv run ruff check src tests`
Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/views/TradeView.tsx
git commit -m "feat(ui): player avatars on trade offer/suggestion cards"
```

---

## Verification checklist (after Task 11)
- [ ] Backend `uv run pytest -q` green; `uv run ruff check src tests` clean.
- [ ] Frontend `npm run build` clean; `npx vitest run` all pass.
- [ ] Manual (demo): My Team shows player cards with headshots + form tags, then the radar; Waivers shows weekday bars (thin + overload) and a teams-to-target list with FA avatars; trade cards show avatars.
