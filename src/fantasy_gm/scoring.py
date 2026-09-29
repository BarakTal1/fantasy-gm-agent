from fantasy_gm.schemas import LeagueSettings, Player

# Categories where a lower value is better (excluded from "more is better" sums).
NEGATIVE_CATS = {"TO"}


def fantasy_points(stats: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(stats.get(c, 0.0) * w for c, w in weights.items()), 2)


def player_value(player: Player, settings: LeagueSettings) -> float:
    """A single comparable value for a player under this league's scoring.
    Points league: weighted fantasy points. Category league: sum of counting
    categories the player helps (turnovers excluded from the positive score)."""
    if settings.is_points:
        return fantasy_points(player.stats, settings.point_weights)
    return round(sum(player.stat(c) for c in settings.categories
                     if c not in NEGATIVE_CATS and not c.endswith("%")), 2)
