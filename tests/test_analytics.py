from fantasy_gm.analytics import buy_low_sell_high, category_profile, streaming_board
from fantasy_gm.schemas import Player, Team

CATS = ["PTS", "AST", "TO"]


def _p(pid, **stats):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=stats)


def test_category_profile_you_vs_league_average():
    mine = Team(team_key="t1", name="Mine", players=[_p("1", PTS=20, AST=5)])
    other = Team(team_key="t2", name="Other", players=[_p("2", PTS=10, AST=1)])
    prof = category_profile(mine, [mine, other], CATS)
    assert prof["PTS"]["you"] == 20
    assert prof["PTS"]["league_avg"] == 15  # (20+10)/2


def test_category_profile_averages_percentage_cats():
    # percentages must average across the roster, not sum
    mine = Team(team_key="t1", name="Mine",
                players=[_p("1", **{"FG%": 0.50}), _p("2", **{"FG%": 0.40})])
    prof = category_profile(mine, [mine], ["FG%"])
    assert prof["FG%"]["you"] == 0.45


def test_streaming_board_ranks_by_form_times_games():
    fas = [_p("1", PTS=10), _p("2", PTS=10)]
    trends = {"1": {"PTS": 12.0}, "2": {"PTS": 8.0}}
    games = {"LAL": 4}  # both LAL
    board = streaming_board(fas, trends, games, cats=["PTS"])
    assert board[0]["player_id"] == "1"      # higher form -> higher projected
    assert board[0]["projected"]["PTS"] == 48.0  # 12 * 4


def test_buy_low_sell_high_flags_divergence():
    players = [_p("1", PTS=20)]
    trends = {"1": {"PTS": 10.0}}  # cold vs season -> buy low
    res = buy_low_sell_high(players, trends, cats=["PTS"])
    assert res[0]["signal"] == "buy_low"
