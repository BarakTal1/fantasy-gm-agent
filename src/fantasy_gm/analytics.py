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
