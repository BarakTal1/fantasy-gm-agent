from fantasy_gm import scoring
from fantasy_gm.schemas import LeagueSettings, Player, Team


def _team_totals(team: Team, cats: list[str]) -> dict[str, float]:
    # Counting cats sum across the roster; percentage cats (FG%/FT%) average,
    # since you can't add shooting percentages.
    def agg(c: str) -> float:
        vals = [p.stat(c) for p in team.players]
        if c.endswith("%"):
            return sum(vals) / len(vals) if vals else 0.0
        return sum(vals)
    return {c: round(agg(c), 2) for c in cats}


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
    """Top-2 categories moving the signal, as human-readable strings.

    Relevance/ranking use the same signed contribution the main loop uses (the
    NEGATIVE_CATS sign flip, so fewer TOs than season counts as a positive/
    sell_high-direction contribution, not a "TO above season" mislabel). The
    displayed word still reflects the actual stat movement (above/below season).
    """
    scored = []
    for c in ordered_cats:
        dv = _divergence(form.get(c, p.stat(c)), p.stat(c), c)
        contrib = -dv if c in scoring.NEGATIVE_CATS else dv
        above = dv > 0
        # sell_high cares about cats contributing positively; buy_low, negatively.
        relevant = (contrib > 0) if signal == "sell_high" else (contrib < 0)
        if relevant and contrib != 0:
            scored.append((abs(contrib), c, "above" if above else "below"))
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

        def d(c: str, form=form, p=p) -> float:
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
            strength = (conf * (W_EFF * max(eff, 0.0) + W_VOL * max(vol, 0.0))
                        if eff_cats else conf * abs(vol))
        elif primary <= -SIGNAL_THRESHOLD:
            if eff_cats and vol < -VOL_FLOOR:
                continue                      # opportunity collapsed -> don't buy
            signal = "buy_low"
            strength = (conf * (W_EFF * abs(eff) + W_VOL * abs(min(vol, 0.0)))
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
               "image_url": p.image_url, "positions": p.positions, "games": g,
               "form": signal.get(p.player_id, "neutral")}
        if settings.is_points:
            row["projected_points"] = round(
                scoring.fantasy_points(form, settings.point_weights) * g, 1)
        else:
            row["projected"] = {c: round(form.get(c, 0.0) * g, 1)
                                for c in settings.categories if not c.endswith("%")}
        rows.append(row)
    return rows


# Standard NBA fantasy position slots, in display order.
POSITIONS = ["PG", "SG", "SF", "PF", "C"]


def best_player(roster: list[Player], settings: LeagueSettings) -> dict | None:
    """The single most valuable player on the roster under this league's scoring."""
    if not roster:
        return None
    top = max(roster, key=lambda p: scoring.player_value(p, settings))
    return {"player_id": top.player_id, "name": top.name, "nba_team": top.nba_team,
            "positions": top.positions, "image_url": top.image_url,
            "value": round(scoring.player_value(top, settings), 1)}


def position_strengths(roster: list[Player], settings: LeagueSettings) -> list[dict]:
    """Total & average player value grouped by eligible position (a multi-eligible
    player counts toward each of its positions). Sorted strongest total first, so
    the caller can read the top row as the roster's strongest position group."""
    groups: dict[str, dict] = {}
    for p in roster:
        v = scoring.player_value(p, settings)
        for pos in (p.positions or ["UTIL"]):
            g = groups.setdefault(pos, {"position": pos, "count": 0, "total_value": 0.0})
            g["count"] += 1
            g["total_value"] += v
    rows = [{"position": g["position"], "count": g["count"],
             "total_value": round(g["total_value"], 1),
             "avg_value": round(g["total_value"] / g["count"], 1)}
            for g in groups.values()]
    order = {pos: i for i, pos in enumerate(POSITIONS)}
    rows.sort(key=lambda r: (-r["total_value"], order.get(r["position"], 99)))
    return rows


def positional_balance(roster: list[Player],
                       roster_slots: dict[str, int] | None = None) -> list[dict]:
    """Eligible-player count per standard position, flagged thin when it can't
    cover the league's roster requirement (or, absent one, fewer than two deep)."""
    slots = roster_slots or {}
    counts = {pos: 0 for pos in POSITIONS}
    for p in roster:
        for pos in p.positions:
            if pos in counts:
                counts[pos] += 1
    out = []
    for pos in POSITIONS:
        required = slots.get(pos)
        need = required if required else 2
        out.append({"position": pos, "eligible": counts[pos],
                    "required": required, "thin": counts[pos] < need})
    return out


def team_stat_totals(teams: list[Team], cats: list[str],
                     games: dict[str, int] | None = None) -> list[dict]:
    """Per fantasy team: rostered-player count, this-week game count (sum of each
    player's NBA-team games), and aggregated per-category totals (counting cats
    sum; percentage cats average). Used by the League tab's team-stats table."""
    games = games or {}
    rows = []
    for t in teams:
        totals = _team_totals(t, cats)
        rows.append({"team_key": t.team_key, "name": t.name,
                     "players": len(t.players),
                     "games_week": sum(games.get(p.nba_team, 0) for p in t.players),
                     "stats": totals})
    return rows


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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
