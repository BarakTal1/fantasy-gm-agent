import uuid
from datetime import datetime, timezone

from langchain_core.messages import AIMessage, ToolMessage
from langsmith.schemas import Example, Run

from evals.run_evals import (
    _collect_names,
    grounding_evaluator,
    run_agent,
    tool_trajectory_evaluator,
)


def _run(outputs: dict) -> Run:
    return Run(id=uuid.uuid4(), name="target", start_time=datetime.now(timezone.utc),
               run_type="chain", outputs=outputs)


def _example(metadata: dict) -> Example:
    return Example(id=uuid.uuid4(), dataset_id=uuid.uuid4(), metadata=metadata)


def test_collect_names_walks_nested_players():
    payload = {"players": [{"name": "Josh Hart", "stats": {}},
                            {"name": "Domantas Sabonis", "stats": {}}]}
    names: set[str] = set()
    _collect_names(payload, names)
    assert names == {"Josh Hart", "Domantas Sabonis"}


def test_collect_names_ignores_non_name_strings():
    names: set[str] = set()
    _collect_names({"team_key": "428.l.123456.t.1", "name": "Team A"}, names)
    assert names == {"Team A"}


class _FakeAgent:
    """Mimics agent.stream(..., stream_mode='updates') for one tool call + answer."""

    def __init__(self, chunks):
        self._chunks = chunks

    def stream(self, *_args, **_kwargs):
        yield from self._chunks


def test_run_agent_captures_tool_calls_names_and_answer():
    tool_call_msg = AIMessage(content="", tool_calls=[
        {"id": "1", "name": "get_free_agents", "args": {}}])
    tool_result_msg = ToolMessage(
        content='[{"name": "Josh Hart", "positions": ["SG"]}]', tool_call_id="1")
    final_msg = AIMessage(content="Pick up Josh Hart.")
    agent = _FakeAgent([
        {"agent": {"messages": [tool_call_msg]}},
        {"tools": {"messages": [tool_result_msg]}},
        {"agent": {"messages": [final_msg]}},
    ])

    result = run_agent("Who should I pick up?", agent)

    assert result["tools_called"] == ["get_free_agents"]
    assert result["known_names"] == ["Josh Hart"]
    assert result["answer"] == "Pick up Josh Hart."


def test_grounding_evaluator_flags_invented_player():
    outputs = {"answer": "Add Josh Hart and LeBron James.", "known_names": ["Josh Hart"]}
    result = grounding_evaluator(outputs)
    assert result == {"key": "grounding", "score": 0.0}


def test_tool_trajectory_evaluator_reads_type_from_example_metadata():
    run = _run({"tools_called": ["get_free_agents", "get_weekly_schedule"]})
    example = _example({"type": "waiver"})
    result = tool_trajectory_evaluator(run, example)
    assert result == {"key": "tool_trajectory", "score": 1.0}


def test_tool_trajectory_evaluator_fails_missing_schedule_for_waiver():
    run = _run({"tools_called": ["get_free_agents"]})
    example = _example({"type": "waiver"})
    result = tool_trajectory_evaluator(run, example)
    assert result == {"key": "tool_trajectory", "score": 0.0}
