from fantasy_gm.yahoo_client.client import (
    parse_free_agents,
    parse_league_settings,
    parse_teams_with_rosters,
)


def test_parse_league_settings(fixture):
    s = parse_league_settings(fixture("league_settings.json"))
    assert s.league_key  # non-empty
    assert s.format in {"category", "points"}
    if s.is_category:
        assert len(s.categories) > 0


def test_parse_free_agents_returns_players_with_stats(fixture):
    players = parse_free_agents(fixture("free_agents.json"))
    assert len(players) > 0
    p = players[0]
    assert p.name and p.player_id
    assert isinstance(p.stats, dict)


def test_parse_teams_with_rosters(fixture):
    teams = parse_teams_with_rosters(fixture("roster.json"))
    assert len(teams) == 1
    t = teams[0]
    assert t.name == "My Squad"
    assert {p.name for p in t.players} == {"Tyrese Haliburton", "Myles Turner"}
    hali = next(p for p in t.players if p.name == "Tyrese Haliburton")
    assert hali.stats["16"] == 9.2  # assists


def test_parse_pending_trades_recipient_side(fixture):
    from fantasy_gm.yahoo_client import client
    raw = fixture("pending_trades_yahoo.json")
    offers = client.parse_pending_trades(raw, my_team_key="428.l.123456.t.1")
    assert len(offers) == 1
    o = offers[0]
    # destination == me => offered to me; source == me => my player they want.
    assert o["they_give"] == ["202681"]     # Kyrie, headed to me
    assert o["they_want"] == ["1626164"]    # Booker, leaving me
    assert o["from_team"] == "428.l.123456.t.2"
