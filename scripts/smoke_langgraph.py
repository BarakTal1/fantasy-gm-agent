"""Verify the LangGraph/LangChain/Anthropic import surface this plan uses.
Run once after installing deps. If anything here fails, the API has drifted;
adjust the plan's later tasks to match what actually imports."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import inspect  # noqa: E402

from langchain_anthropic import ChatAnthropic  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langchain_core.tools import StructuredTool, tool  # noqa: E402
from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402
from langgraph.prebuilt import create_react_agent  # noqa: E402

sig = inspect.signature(create_react_agent)
print("create_react_agent params:", list(sig.parameters))
print("ChatAnthropic ok:", ChatAnthropic.__name__)
print("messages ok:", AIMessage.__name__, HumanMessage.__name__, ToolMessage.__name__)
print("tool/StructuredTool ok:", tool.__name__, StructuredTool.__name__)
print("PostgresSaver ok:", PostgresSaver.__name__)
print("SMOKE OK")
