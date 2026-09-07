from datetime import date

from langchain_core.tools import StructuredTool

from fantasy_gm import tools


def build_tools(league_key: str, my_team_key: str) -> list:
    """Wrap the toolbox as LangChain tools, binding league/team context."""

    def get_my_roster() -> dict:
        """Get the user's current team roster and each player's stats."""
        return tools.get_my_roster(league_key, my_team_key).model_dump()

    def get_free_agents() -> list[dict]:
        """List available free-agent/waiver players with their stats."""
        return [p.model_dump() for p in tools.get_free_agents(league_key)]

    def get_league_settings() -> dict:
        """Get the league's scoring format, categories, and roster slots."""
        return tools.get_league_settings(league_key).model_dump()

    def get_trends(player_ids: list[str], window_days: int = 14) -> dict:
        """Recent per-game form (mean of each stat) over the trailing window,
        per player id. Use for buy-low/sell-high and short-term decisions."""
        return tools.get_trends(player_ids, window_days, date.today())

    def get_weekly_schedule(week: int) -> dict:
        """How many games each NBA team plays this week and how many remain.
        Use for waiver/streaming/start-sit value, NOT for long-term trade value."""
        return tools.get_weekly_schedule(week)

    return [
        StructuredTool.from_function(get_my_roster),
        StructuredTool.from_function(get_free_agents),
        StructuredTool.from_function(get_league_settings),
        StructuredTool.from_function(get_trends),
        StructuredTool.from_function(get_weekly_schedule),
    ]
