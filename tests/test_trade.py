from fantasy_gm.schemas import LeagueSettings, Player
from fantasy_gm.trade import category_delta, points_delta


def _p(pid, **s):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=s)


def test_category_delta_net_per_category():
    give = [_p("1", AST=8, PTS=10)]     # you send away
    get = [_p("2", AST=2, PTS=20)]      # you receive
    d = category_delta(give, get, cats=["AST", "PTS", "TO"])
    assert d["AST"] == -6.0   # lose 6 assists
    assert d["PTS"] == 10.0   # gain 10 points
    assert d["TO"] == 0.0


def test_category_delta_lower_is_better_for_turnovers_is_caller_concern():
    # engine reports raw net; TO interpretation happens in the verdict prompt
    give = [_p("1", TO=3)]
    get = [_p("2", TO=1)]
    assert category_delta(give, get, cats=["TO"])["TO"] == -2.0


def test_points_delta_net_fantasy_points():
    s = LeagueSettings(league_key="k", format="points",
                       point_weights={"PTS": 1.0, "AST": 1.5})
    give = [_p("1", PTS=10, AST=2)]   # value 13
    get = [_p("2", PTS=20, AST=0)]    # value 20
    d = points_delta(give, get, s)
    assert d["net"] == 7.0
    assert d["give_value"] == 13.0 and d["get_value"] == 20.0
