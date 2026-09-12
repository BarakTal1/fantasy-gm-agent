from fantasy_gm import proposals
from fantasy_gm.schemas import LeagueSettings, Player, Team


def _p(pid, **stats):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=stats)


def _team(key, name, players):
    return Team(team_key=key, name=name, players=players)


def test_category_suggestion_targets_my_weak_category():
    # I'm strong PTS, weak AST. A rival has a cold (buy-low) AST player, and I
    # hold a mid-value asset whose value is close enough to pass fairness.
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("t1", "Mine", [_p("m1", PTS=20, AST=2), _p("m2", PTS=12, AST=3)])
    rival = _team("t2", "Rival", [_p("r1", PTS=6, AST=11)])   # season value ~17
    league = [mine, rival]
    # Rival's dimer is cold across the board lately -> buy_low (both cats ~-0.5).
    trends = {"r1": {"PTS": 3, "AST": 5}}
    out = proposals.suggest_trades(mine, league, trends, cat)
    assert out, "expected at least one proposal"
    top = out[0]
    assert top["with_team"] == "Rival"
    assert "r1" in [p["player_id"] for p in top["get"]]
    assert "AST" in top["targeted_categories"]
    assert top["need_fit"] > 0
    assert top["fairness_gap"] >= 0


def test_packages_capped_at_two_per_side():
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("t1", "Mine",
                 [_p("m1", PTS=20, AST=2), _p("m2", PTS=12, AST=3), _p("m3", PTS=10, AST=4)])
    rival = _team("t2", "Rival", [_p("r1", PTS=6, AST=11), _p("r2", PTS=5, AST=9)])
    league = [mine, rival]
    trends = {"r1": {"PTS": 3, "AST": 5}, "r2": {"PTS": 2, "AST": 4}}
    out = proposals.suggest_trades(mine, league, trends, cat)
    assert out, "expected proposals to exercise the cap"
    for prop in out:
        assert 1 <= len(prop["give"]) <= 2
        assert 1 <= len(prop["get"]) <= 2


def test_no_suggestions_when_no_buy_low_targets():
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS", "AST"])
    mine = _team("t1", "Mine", [_p("m1", PTS=30, AST=1)])
    rival = _team("t2", "Rival", [_p("r1", PTS=20, AST=5)])
    trends = {}                                   # no trends -> nobody flagged buy_low
    out = proposals.suggest_trades(mine, [mine, rival], trends, cat)
    assert out == []


def test_unfair_pairing_excluded():
    # Two rival teams each offer one buy-low target for my single asset (PTS=20).
    # RivalFair's target (PTS=22) is close enough in value to pass the 25%
    # fairness tolerance; RivalUnfair's target (PTS=60) has a value gap far
    # beyond it and must never show up as a "get", even though its need-fit
    # (a bigger positive PTS swing) would otherwise be even stronger.
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS"])
    mine = _team("t1", "Mine", [_p("m1", PTS=20)])
    rival_fair = _team("t2", "RivalFair", [_p("rf1", PTS=22)])
    rival_unfair = _team("t3", "RivalUnfair", [_p("ru1", PTS=60)])
    league = [mine, rival_fair, rival_unfair]
    # Both targets are cold by the same -50% relative to season -> both buy_low.
    trends = {"rf1": {"PTS": 11}, "ru1": {"PTS": 30}}
    out = proposals.suggest_trades(mine, league, trends, cat)
    got_ids = {p["player_id"] for prop in out for p in prop["get"]}
    assert "ru1" not in got_ids, "value gap (40) exceeds the 25% fairness tolerance (15)"
    assert "rf1" in got_ids, "fair pairing (gap 2 <= tolerance 5.5) should survive"


def test_pkg_pool_caps_candidate_targets():
    # Rival offers 7 buy-low targets with clearly varying values; PKG_POOL (6)
    # keeps only the 6 highest-value ones before packages are ever built. The
    # lowest-value target (PTS=44) is deliberately close in value to my asset
    # (PTS=40, gap 4 <= tolerance 11) and would have positive need-fit (delta
    # +4) -- i.e. it would pass every filter if it reached candidate-building,
    # so its absence from the output can only be explained by the pool cap.
    cat = LeagueSettings(league_key="k", format="category", categories=["PTS"])
    mine = _team("t1", "Mine", [_p("m1", PTS=40)])
    rival_vals = [100, 90, 80, 70, 60, 50, 44]
    rival_players = [_p(f"r{v}", PTS=v) for v in rival_vals]
    rival = _team("t2", "Rival", rival_players)
    # -50% relative to season for every target -> all 7 are flagged buy_low.
    trends = {f"r{v}": {"PTS": v / 2} for v in rival_vals}
    out = proposals.suggest_trades(mine, [mine, rival], trends, cat)
    got_ids = {p["player_id"] for prop in out for p in prop["get"]}
    assert "r44" not in got_ids, "lowest-value target should be dropped by PKG_POOL"
    assert got_ids, "expected at least one higher-value target to survive"


def test_points_suggestion_is_net_positive_points():
    pts = LeagueSettings(league_key="k", format="points", categories=["PTS"],
                         point_weights={"PTS": 1.0})
    mine = _team("t1", "Mine", [_p("m1", PTS=18)])
    rival = _team("t2", "Rival", [_p("r1", PTS=22)])
    trends = {"r1": {"PTS": 11}}                 # rival star slumping -> buy_low
    out = proposals.suggest_trades(mine, [mine, rival], trends, pts)
    assert out, "expected a points proposal"
    assert out[0]["need_fit"] > 0               # projected points gained
    assert out[0]["with_team"] == "Rival"
