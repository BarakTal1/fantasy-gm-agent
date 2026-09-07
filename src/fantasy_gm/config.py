from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    yahoo_client_id: str = ""
    yahoo_client_secret: str = ""
    yahoo_redirect_uri: str = "oob"
    yahoo_league_key: str = ""

    database_url: str = "postgresql://fgm:fgm@localhost:5432/fantasy_gm"
    test_database_url: str = "postgresql://fgm:fgm@localhost:5432/fantasy_gm_test"

    # NBA schedule source (see docs/design.md §14). Keyed API chosen over free
    # hidden endpoints because those block datacenter IPs (breaks cloud sync).
    balldontlie_api_key: str = ""

    anthropic_api_key: str = ""

    # Claude model for the agent. Default is the most capable; override via env
    # AGENT_MODEL=claude-sonnet-5 for a cheaper/faster option.
    agent_model: str = "claude-opus-5"


@lru_cache
def get_settings() -> Settings:
    return Settings()
