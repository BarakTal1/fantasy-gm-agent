"""Player valuation.

short_term_value: for waivers/streaming/start-sit. Weighs games *this week*.
long_term_value:  for core-player trade evaluation. Season value; schedule ignored.

Both take a stat map (category -> per-game value). v1 uses an equal-weight sum as
the baseline aggregate; category weights can be layered on later without changing
the interface.
"""


def _aggregate(stats: dict[str, float]) -> float:
    return sum(stats.values())


def short_term_value(recent_form: dict[str, float], games_remaining: int) -> float:
    """Expected contribution over the rest of this week."""
    return _aggregate(recent_form) * games_remaining


def long_term_value(season_stats: dict[str, float]) -> float:
    """Sustained per-game value; deliberately independent of weekly schedule."""
    return _aggregate(season_stats)
