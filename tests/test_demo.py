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
