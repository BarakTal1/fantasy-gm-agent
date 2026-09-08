from fantasy_gm.schemas import LeagueSettings, Player
from fantasy_gm.scoring import fantasy_points, player_value


def _p(**s): return Player(player_id="1", name="P", nba_team="LAL", stats=s)


def test_fantasy_points_weighted_sum():
    w = {"PTS": 1.0, "AST": 1.5, "TO": -1.0}
    assert fantasy_points({"PTS": 20, "AST": 4, "TO": 2}, w) == 24.0  # 20+6-2


def test_player_value_points_league_is_scalar():
    s = LeagueSettings(league_key="k", format="points",
                       point_weights={"PTS": 1.0, "AST": 1.5})
    v = player_value(_p(PTS=20, AST=4), s)
    assert v == 26.0  # scalar fantasy points


def test_player_value_category_league_excludes_turnovers_from_score():
    s = LeagueSettings(league_key="k", format="category",
                       categories=["PTS", "AST", "TO"])
    v = player_value(_p(PTS=20, AST=4, TO=3), s)
    assert v == 24.0  # counting-cat sum, TO excluded from the "more is better" score
