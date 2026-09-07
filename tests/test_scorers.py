from evals.scorers import grounding_score, tool_trajectory_score


def test_grounding_score_penalizes_invented_players():
    known = {"Josh Hart"}
    assert grounding_score("Add Josh Hart.", known) == 1.0
    assert grounding_score("Add Josh Hart and LeBron James.", known) == 0.0


def test_tool_trajectory_requires_schedule_for_waiver():
    assert tool_trajectory_score(
        question_type="waiver",
        tools_called=["get_free_agents", "get_weekly_schedule"]) == 1.0
    assert tool_trajectory_score(
        question_type="waiver",
        tools_called=["get_free_agents"]) == 0.0   # missing schedule
    # a trade question must NOT hinge on weekly schedule
    assert tool_trajectory_score(
        question_type="trade",
        tools_called=["get_my_roster", "get_trends"]) == 1.0
