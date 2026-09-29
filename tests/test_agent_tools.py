from fantasy_gm import agent_tools


def test_build_tools_returns_named_langchain_tools(monkeypatch):
    from fantasy_gm import tools
    monkeypatch.setattr(tools, "get_weekly_schedule",
                        lambda week: {"LAL": {"games_total": 4, "games_remaining": 3}})
    lc_tools = agent_tools.build_tools(league_key="428.l.1", my_team_key="428.l.1.t.1")
    names = {t.name for t in lc_tools}
    assert {"get_weekly_schedule", "get_free_agents", "get_my_roster",
            "get_trends"}.issubset(names)
    # tools are invocable and carry a description the LLM can read
    sched = next(t for t in lc_tools if t.name == "get_weekly_schedule")
    assert sched.description
    assert sched.invoke({"week": 15}) == {"LAL": {"games_total": 4, "games_remaining": 3}}


def test_build_tools_includes_league_teams(monkeypatch):
    from fantasy_gm import agent_tools, tools
    from fantasy_gm.schemas import Team
    monkeypatch.setattr(tools, "get_all_teams",
                        lambda k: [Team(team_key="428.l.1.t.2", name="Rivals", players=[])])
    lc = agent_tools.build_tools(league_key="428.l.1", my_team_key="428.l.1.t.1")
    names = {t.name for t in lc}
    assert "get_league_teams" in names
    teams_tool = next(t for t in lc if t.name == "get_league_teams")
    assert teams_tool.invoke({})[0]["name"] == "Rivals"
