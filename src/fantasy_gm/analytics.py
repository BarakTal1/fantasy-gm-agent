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
    """Top-2 categories moving the signal, as human-readable strings."""
    scored = []
    for c in ordered_cats:
        dv = _divergence(form.get(c, p.stat(c)), p.stat(c), c)
        above = dv > 0
        # sell_high cares about cats above season; buy_low about cats below.
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


_DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def weekday_coverage(roster: list[Player], day_teams: dict[str, list[str]],
                     weak_threshold: int = 4) -> list[dict]:
    """Per weekday: how many of my players have an NBA game that day.

    Thin days (few players playing) are flagged so the manager knows which days
    to stream a waiver-wire player into an empty slot. `day_teams` maps a weekday
    abbrev (Mon..Sun) to the NBA teams playing that day.
    """
    out = []
    for d in _DAYS:
        teams = set(day_teams.get(d, []))
        count = sum(1 for p in roster if p.nba_team in teams)
        out.append({"day": d, "count": count,
                    "weak": len(teams) > 0 and count <= weak_threshold})
    return out
