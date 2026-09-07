from fantasy_gm.guardrails import ungrounded_players


def test_flags_player_not_in_tool_data():
    answer = "Pick up Josh Hart and drop LeBron James."
    known = {"Josh Hart", "Alex Caruso"}
    assert ungrounded_players(answer, known) == ["LeBron James"]


def test_no_flags_when_all_grounded():
    answer = "Pick up Josh Hart over Alex Caruso."
    known = {"Josh Hart", "Alex Caruso"}
    assert ungrounded_players(answer, known) == []
