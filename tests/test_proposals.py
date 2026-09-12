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
