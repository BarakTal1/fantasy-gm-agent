from fantasy_gm.yahoo_client.client import (
    parse_free_agents,
    parse_league_settings,
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
