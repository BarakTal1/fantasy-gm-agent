from fantasy_gm.analytics import (
    best_player,
    buy_low_sell_high,
    category_profile,
    points_value_board,
    position_strengths,
    positional_balance,
    recommended_pickups,
    streaming_board,
    team_stat_totals,
)
from fantasy_gm.schemas import LeagueSettings, Player, Team

CATS = ["PTS", "AST", "TO"]


def _p(pid, positions=None, **stats):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL",
                  positions=positions or [], stats=stats)


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


def test_buy_low_volume_only_league_flags_cold_form():
    # No percentage cats: classification falls back to volume divergence.
    players = [_p("1", PTS=20)]
    trends = {"1": {"PTS": 10.0}}          # -50% vs season -> buy_low
    res = buy_low_sell_high(players, trends, cats=["PTS"])
    assert res and res[0]["signal"] == "buy_low"
    assert res[0]["efficiency_delta"] is None
    assert res[0]["drivers"] == ["PTS below season"]


def test_sell_high_on_hot_shooting():
    players = [_p("1", **{"FG%": 0.40, "PTS": 20})]
    trends = {"1": {"FG%": 0.55, "PTS": 21}}   # +15 FG pts -> regression risk
    res = buy_low_sell_high(players, trends, cats=["FG%", "PTS"])
    assert res and res[0]["signal"] == "sell_high"
    assert res[0]["efficiency_delta"] > 0


def test_buy_low_rejected_when_volume_collapsed():
    # Cold shooting but counting volume also cratered -> opportunity gone, no buy.
    players = [_p("1", **{"FG%": 0.50, "PTS": 20})]
    trends = {"1": {"FG%": 0.40, "PTS": 8}}    # FG cold AND PTS -60%
    res = buy_low_sell_high(players, trends, cats=["FG%", "PTS"])
    assert res == []


def test_buy_low_on_cold_shooting_with_volume_intact():
    # Headline success path: efficiency down, counting volume unchanged (not
    # collapsed) -> opportunity is intact -> buy_low fires.
    players = [_p("1", **{"FG%": 0.50, "PTS": 20})]
    trends = {"1": {"FG%": 0.40, "PTS": 20}}   # FG cold, PTS steady
    res = buy_low_sell_high(players, trends, cats=["FG%", "PTS"])
    assert res and res[0]["signal"] == "buy_low"
    assert res[0]["efficiency_delta"] < 0


def test_3pm_folds_into_efficiency():
    # 3PM is a shooting-proxy counting cat and should be treated as an
    # efficiency category (via _EFF_EXTRA), not a volume category.
    players = [_p("1", **{"3PM": 1.0})]
    trends = {"1": {"3PM": 2.5}}
    res = buy_low_sell_high(players, trends, cats=["3PM"])
    assert res and res[0]["signal"] == "sell_high"
    assert res[0]["efficiency_delta"] is not None


def test_drivers_labels_turnover_improvement_correctly():
    # Fewer TOs than season is a *positive* (sell_high) signal; drivers must
    # surface it using the same signed contribution the main loop applies for
    # NEGATIVE_CATS, not the raw (unflipped) divergence which would exclude or
    # mislabel it.
    players = [_p("1", TO=5)]
    trends = {"1": {"TO": 1.0}}   # -80% TO -> fewer turnovers -> sell_high
    res = buy_low_sell_high(players, trends, cats=["TO"])
    assert res and res[0]["signal"] == "sell_high"
    assert res[0]["drivers"] == ["TO below season"]


def test_confidence_dampens_low_sample():
    players = [_p("1", PTS=20)]
    trends = {"1": {"PTS": 10.0}}
    hi = buy_low_sell_high(players, trends, cats=["PTS"], games={"1": 40})
    lo = buy_low_sell_high(players, trends, cats=["PTS"], games={"1": 5})
    assert hi[0]["strength"] > lo[0]["strength"]
    assert hi[0]["confidence"] == 1.0 and lo[0]["confidence"] == 0.6


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


def test_weekday_coverage_flags_thin_days():
    from fantasy_gm.analytics import weekday_coverage
    from fantasy_gm.schemas import Player
    roster = [Player(player_id="1", name="A", nba_team="LAL"),
              Player(player_id="2", name="B", nba_team="BOS")]
    day_teams = {"Mon": ["LAL", "BOS"], "Tue": ["LAL"], "Wed": []}
    cov = weekday_coverage(roster, day_teams, weak_threshold=1)
    by_day = {c["day"]: c for c in cov}
    assert by_day["Mon"]["count"] == 2 and by_day["Mon"]["weak"] is False
    assert by_day["Tue"]["count"] == 1 and by_day["Tue"]["weak"] is True
    assert by_day["Wed"]["count"] == 0 and by_day["Wed"]["weak"] is False  # no games
    assert [c["day"] for c in cov][:3] == ["Mon", "Tue", "Wed"]            # ordered


def test_roster_week_outlook_category_projects_and_tags():
    from fantasy_gm.analytics import roster_week_outlook
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    roster = [_p("1", PTS=20, AST=5)]
    trends = {"1": {"PTS": 10.0, "AST": 2.0}}        # cold vs season -> buy_low
    games = {"LAL": 3}                                # _p defaults nba_team="LAL"
    rows = roster_week_outlook(roster, trends, games, cat)
    assert rows[0]["games"] == 3
    assert rows[0]["projected"]["PTS"] == 30.0        # recent 10 * 3 games
    assert rows[0]["form"] == "buy_low"


def test_roster_week_outlook_points_and_neutral():
    from fantasy_gm.analytics import roster_week_outlook
    pts = LeagueSettings(league_key="k", format="points", categories=["PTS"],
                         point_weights={"PTS": 1.0})
    roster = [_p("1", PTS=20)]
    rows = roster_week_outlook(roster, trends={}, games={"LAL": 4}, settings=pts)
    assert rows[0]["projected_points"] == 80.0        # season 20 (no trend) * 4
    assert rows[0]["form"] == "neutral"               # no trend -> no signal


def test_weekday_coverage_flags_overloaded_days():
    from fantasy_gm.analytics import weekday_coverage
    from fantasy_gm.schemas import Player
    roster = [Player(player_id=str(i), name=f"P{i}", nba_team="LAL") for i in range(11)]
    day_teams = {"Mon": ["LAL"], "Tue": ["BOS"]}
    cov = {c["day"]: c for c in weekday_coverage(roster, day_teams)}
    assert cov["Mon"]["count"] == 11 and cov["Mon"]["heavy"] is True
    assert cov["Tue"]["heavy"] is False


def test_teams_to_target_joins_thin_days_to_free_agents():
    from fantasy_gm.analytics import teams_to_target
    from fantasy_gm.schemas import LeagueSettings, Player
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS"])
    roster = [Player(player_id="r1", name="Mine", nba_team="LAL", stats={"PTS": 20})]
    day_teams = {"Wed": ["PHX"], "Fri": ["PHX", "BOS"]}
    fas = [Player(player_id="f1", name="Sun Guy", nba_team="PHX", stats={"PTS": 15}),
           Player(player_id="f2", name="Celtic", nba_team="BOS", stats={"PTS": 10})]
    out = teams_to_target(roster, fas, day_teams, cat)
    phx = next(t for t in out if t["nba_team"] == "PHX")
    assert phx["weak_days"] == ["Wed", "Fri"]
    assert phx["free_agents"][0]["name"] == "Sun Guy"
    assert phx["free_agents"][0]["nba_team"] == "PHX"


def test_teams_to_target_skips_teams_without_free_agents():
    from fantasy_gm.analytics import teams_to_target
    from fantasy_gm.schemas import LeagueSettings, Player
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS"])
    roster = [Player(player_id="r1", name="Mine", nba_team="LAL")]
    day_teams = {"Wed": ["PHX"]}
    out = teams_to_target(roster, free_agents=[], day_teams=day_teams, settings=cat)
    assert out == []


# --- Roster analytics (positions / best player / balance / team stats) ---

_CAT = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])


def test_best_player_picks_top_value():
    roster = [_p("1", PTS=30, AST=8), _p("2", PTS=10, AST=2)]
    top = best_player(roster, _CAT)
    assert top["player_id"] == "1"
    assert top["value"] == 38


def test_position_strengths_credits_each_eligible_position():
    roster = [_p("1", positions=["PG", "SG"], PTS=20, AST=5),
              _p("2", positions=["SG"], PTS=10, AST=1)]
    rows = position_strengths(roster, _CAT)
    sg = next(r for r in rows if r["position"] == "SG")
    assert sg["count"] == 2 and sg["total_value"] == 36  # 25 + 11
    # sorted strongest total first
    assert rows[0]["total_value"] >= rows[-1]["total_value"]


def test_positional_balance_flags_thin_slots():
    roster = [_p("1", positions=["PG"]), _p("2", positions=["C"]), _p("3", positions=["C"])]
    bal = {b["position"]: b for b in positional_balance(roster)}
    assert bal["PG"]["eligible"] == 1 and bal["PG"]["thin"] is True   # <2 deep
    assert bal["C"]["eligible"] == 2 and bal["C"]["thin"] is False
    assert bal["SF"]["eligible"] == 0 and bal["SF"]["thin"] is True


def test_positional_balance_respects_roster_slots():
    roster = [_p("1", positions=["C"]), _p("2", positions=["C"]), _p("3", positions=["C"])]
    bal = {b["position"]: b for b in positional_balance(roster, {"C": 2})}
    assert bal["C"]["required"] == 2 and bal["C"]["thin"] is False   # 3 >= 2


def test_team_stat_totals_aggregates_and_counts_games():
    teams = [Team(team_key="t1", name="Mine",
                  players=[_p("1", PTS=20, AST=5), _p("2", PTS=10, AST=3)])]
    rows = team_stat_totals(teams, ["PTS", "AST"], games={"LAL": 3})
    assert rows[0]["players"] == 2
    assert rows[0]["stats"]["PTS"] == 30
    assert rows[0]["games_week"] == 6      # two LAL players x 3 games
