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
