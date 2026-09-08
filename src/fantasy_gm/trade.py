from fantasy_gm.schemas import Player


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
