from fantasy_gm import demo


def test_demo_league_has_twelve_teams():
    teams = demo.demo_teams()
    assert len(teams) == 12
    assert teams[0].team_key == "428.l.123456.t.1"
    assert teams[0].name == "My Squad"
    assert all(len(t.players) >= 5 for t in teams)


def test_demo_free_agents_pool():
    fas = demo.demo_free_agents()
    assert len(fas) >= 20
    p = fas[0]
    assert set(p.stats).issuperset({"PTS", "AST", "ST"})  # human category keys


def test_demo_points_settings(monkeypatch):
    from fantasy_gm.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setenv("DEMO_LEAGUE_FORMAT", "points")
    from fantasy_gm import demo
    s = demo.demo_league_settings()
    assert s.is_points
    assert s.point_weights["ST"] == 3.0
    get_settings.cache_clear()
