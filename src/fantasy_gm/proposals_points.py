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
