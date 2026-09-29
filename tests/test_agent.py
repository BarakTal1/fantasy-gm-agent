from langchain_core.messages import AIMessage, HumanMessage

from fantasy_gm.agent import build_agent
from fantasy_gm.schemas import LeagueSettings
from tests.support.fake_chat import FakeToolCallingModel


def _league():
    return LeagueSettings(league_key="428.l.1", format="category",
                          categories=["PTS", "AST"])


def test_agent_calls_tool_then_answers(monkeypatch):
    # Script: first turn asks for the weekly schedule tool, second turn answers.
    scripted = FakeToolCallingModel(responses=[
        AIMessage(content="", tool_calls=[{
            "name": "get_weekly_schedule", "args": {"week": 15}, "id": "call_1"}]),
        AIMessage(content="Pick up players with 4 games this week."),
    ])
    agent = build_agent(
        league=_league(), league_key="428.l.1", my_team_key="428.l.1.t.1",
        model=scripted, checkpointer=None,
    )
    import fantasy_gm.tools as tools_mod
    # stub the underlying tool so no DB is needed (monkeypatch auto-restores
    # this after the test, avoiding cross-test pollution of the shared module)
    monkeypatch.setattr(
        tools_mod, "get_weekly_schedule",
        lambda week: {"LAL": {"games_total": 4, "games_remaining": 4}},
    )
    result = agent.invoke({"messages": [HumanMessage("Who should I pick up?")]})
    final = result["messages"][-1]
    assert "4 games" in final.content
