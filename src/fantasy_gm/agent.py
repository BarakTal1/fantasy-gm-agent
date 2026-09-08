from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from fantasy_gm.agent_tools import build_tools
from fantasy_gm.config import get_settings
from fantasy_gm.prompts import build_system_prompt
from fantasy_gm.schemas import LeagueSettings


def build_agent(league: LeagueSettings, league_key: str, my_team_key: str,
                model=None, checkpointer=None):
    """Construct the LangGraph agent. Pass `model` in tests (a fake); in
    production it defaults to ChatAnthropic on the configured Claude model."""
    if model is None:
        s = get_settings()
        # Pass the key from our Settings (.env) explicitly — ChatAnthropic only
        # reads it from the OS env otherwise, which pydantic-settings doesn't set.
        model = ChatAnthropic(
            model=s.agent_model, api_key=s.anthropic_api_key, max_tokens=4096)
    lc_tools = build_tools(league_key=league_key, my_team_key=my_team_key)
    return create_react_agent(
        model,
        lc_tools,
        prompt=build_system_prompt(league),
        checkpointer=checkpointer,
    )
