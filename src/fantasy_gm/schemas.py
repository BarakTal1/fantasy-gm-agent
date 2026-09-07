from pydantic import BaseModel, Field


class Player(BaseModel):
    player_id: str
    name: str
    nba_team: str                      # NBA team abbrev, e.g. "LAL"
    positions: list[str] = Field(default_factory=list)
    stats: dict[str, float] = Field(default_factory=dict)  # category -> per-game value

    def stat(self, key: str) -> float:
        return self.stats.get(key, 0.0)


class Team(BaseModel):
    team_key: str
    name: str
    players: list[Player] = Field(default_factory=list)


class LeagueSettings(BaseModel):
    league_key: str
    format: str                        # "category" | "points"
    categories: list[str] = Field(default_factory=list)
    roster_slots: dict[str, int] = Field(default_factory=dict)

    @property
    def is_category(self) -> bool:
        return self.format == "category"
