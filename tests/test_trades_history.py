from fantasy_gm.schemas import Player
from fantasy_gm.trades_history import build_history


def _p(pid, **s):
    return Player(player_id=pid, name=f"P{pid}", nba_team="LAL", stats=s)


def test_build_history_before_after():
    by_id = {"1": _p("1", PTS=20.0), "2": _p("2", PTS=10.0)}
    trades = [{"date": "2025-12-14", "with_team": "Team 4",
               "gave": ["1"], "got": ["2"]}]
    hist = build_history(trades, by_id)
    t = hist[0]
    assert t["with_team"] == "Team 4"
    p = t["got"][0]
    assert p["name"] == "P2"
    assert p["before"]["PTS"] == 10.0
    assert p["after"]["PTS"] > p["before"]["PTS"]        # synthetic since-trade bump


def test_build_history_skips_unknown_ids():
    hist = build_history([{"date": "d", "with_team": "T",
                           "gave": ["missing"], "got": []}], {})
    assert hist[0]["gave"] == []
