from fantasy_gm.schemas import LeagueSettings, Player


def test_player_defaults_missing_stats_to_zero():
    p = Player(player_id="1", name="X", nba_team="LAL", positions=["PG"], stats={"AST": 6.0})
    assert p.stats["AST"] == 6.0
    assert p.stat("REB") == 0.0  # missing stat reads as 0

def test_league_settings_is_category():
    s = LeagueSettings(league_key="428.l.1", format="category",
                       categories=["PTS", "AST"], roster_slots={"PG": 1})
    assert s.is_category is True
