from fantasy_gm.guardrails import ungrounded_players


def grounding_score(answer: str, known_names: set[str]) -> float:
    """1.0 if every player named in the answer came from tool data, else 0.0."""
    return 0.0 if ungrounded_players(answer, known_names) else 1.0


def tool_trajectory_score(question_type: str, tools_called: list[str]) -> float:
    """Did the agent use the right tools/lens for the question type?"""
    called = set(tools_called)
    if question_type == "waiver":
        # short-term value must factor games this week
        return 1.0 if {"get_free_agents", "get_weekly_schedule"} <= called else 0.0
    if question_type == "trade":
        # long-term value: must use trends/roster, must NOT hinge on schedule
        needs = {"get_my_roster", "get_trends"} <= called
        return 1.0 if needs and "get_weekly_schedule" not in called else 0.0
    return 1.0
