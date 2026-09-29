from fantasy_gm import received_trades
from fantasy_gm.schemas import Player


def _p(pid, name):
    return Player(player_id=pid, name=name, nba_team="LAL", stats={"PTS": 10.0})


def test_build_offers_resolves_players_and_direction():
    by_id = {"1626164": _p("1626164", "Booker"), "202681": _p("202681", "Kyrie")}
    raw = [{"from_team": "Team 2", "date": "2026-01-20", "note": "need scoring",
            "they_give": ["202681"], "they_want": ["1626164"]}]
    offers = received_trades.build_offers(raw, by_id)
    assert len(offers) == 1
    o = offers[0]
    assert o["from_team"] == "Team 2" and o["note"] == "need scoring"
    assert o["they_give"][0]["name"] == "Kyrie"       # offered TO me
    assert o["they_want"][0]["name"] == "Booker"      # my player they want


def test_build_offers_skips_unknown_ids():
    by_id = {"202681": _p("202681", "Kyrie")}
    raw = [{"from_team": "Team 2", "date": "2026-01-20",
            "they_give": ["202681"], "they_want": ["does-not-exist"]}]
    offers = received_trades.build_offers(raw, by_id)
    assert offers[0]["they_give"][0]["name"] == "Kyrie"
    assert offers[0]["they_want"] == []


def test_build_offers_empty():
    assert received_trades.build_offers([], {}) == []
