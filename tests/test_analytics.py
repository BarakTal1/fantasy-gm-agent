from fantasy_gm.analytics import (
    buy_low_sell_high,
    category_profile,
    points_value_board,
    recommended_pickups,
    streaming_board,
)
from fantasy_gm.schemas import LeagueSettings, Player, Team

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


def _team(name, players): return Team(team_key=name, name=name, players=players)


def test_recommended_pickups_category_prefers_my_weak_cats(monkeypatch):
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("Mine", [_p("1", PTS=30, AST=1)])          # strong PTS, weak AST
    league = [mine, _team("Rival", [_p("2", PTS=10, AST=9)])]
    fas = [_p("A", PTS=0, AST=8), _p("B", PTS=10, AST=0)]    # A helps my weak AST
    trends = {"A": {"PTS": 0, "AST": 8}, "B": {"PTS": 10, "AST": 0}}
    games = {"LAL": 3}
    recs = recommended_pickups(mine, league, fas, trends, games, cat)
    assert recs[0]["player_id"] == "A"                       # need-weighting favors A
    assert "drop" in recs[0]                                  # suggests a drop


def test_points_value_board_ranks_by_projected_points():
    pts = LeagueSettings(league_key="k", format="points",
                         point_weights={"PTS": 1.0})
    fas = [_p("A", PTS=10), _p("B", PTS=20)]
    trends = {"A": {"PTS": 10}, "B": {"PTS": 20}}
    board = points_value_board(fas, trends, {"LAL": 4}, pts)
    assert board[0]["player_id"] == "B"
    assert board[0]["projected_points"] == 80.0  # 20 * 4
