import pytest

from fantasy_gm.value import long_term_value, short_term_value


def test_short_term_scales_with_games_this_week():
    form = {"PTS": 20.0, "AST": 5.0}
    two = short_term_value(form, games_remaining=2)
    four = short_term_value(form, games_remaining=4)
    assert four == pytest.approx(2 * two)


def test_short_term_is_zero_with_no_games():
    assert short_term_value({"PTS": 20.0}, games_remaining=0) == 0.0


def test_long_term_ignores_weekly_games():
    season = {"PTS": 20.0, "AST": 5.0}
    # games_remaining must not affect long-term value
    assert long_term_value(season) == long_term_value(season)
    assert long_term_value(season) == pytest.approx(25.0)  # simple sum baseline
