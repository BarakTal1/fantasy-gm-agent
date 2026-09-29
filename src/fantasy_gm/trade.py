from fantasy_gm import scoring
from fantasy_gm.schemas import LeagueSettings, Player


def category_delta(give: list[Player], get: list[Player],
                   cats: list[str]) -> dict[str, float]:
    """Net per-category change to YOUR team from the trade (get - give).
    Percentage cats (FG%/FT%) are reported as a simple mean-of-means delta;
    note in the verdict that they should be volume-weighted for a real call."""
    def total(players, c):
        vals = [p.stat(c) for p in players]
        if c.endswith("%"):
            return sum(vals) / len(vals) if vals else 0.0
        return sum(vals)
    return {c: round(total(get, c) - total(give, c), 2) for c in cats}


def summarize(delta: dict[str, float]) -> dict:
    """Count categories improved vs worsened (TO: lower is better)."""
    improved, worsened = [], []
    for c, v in delta.items():
        good = v < 0 if c == "TO" else v > 0
        if v == 0:
            continue
        (improved if good else worsened).append(c)
    return {"improved": improved, "worsened": worsened}


def points_delta(give, get, settings: LeagueSettings) -> dict:
    gv = round(sum(scoring.fantasy_points(p.stats, settings.point_weights)
                   for p in give), 2)
    tv = round(sum(scoring.fantasy_points(p.stats, settings.point_weights)
                   for p in get), 2)
    return {"give_value": gv, "get_value": tv, "net": round(tv - gv, 2)}
