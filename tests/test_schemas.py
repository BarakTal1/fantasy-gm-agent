from fantasy_gm.schemas import LeagueSettings, Player


def test_player_defaults_missing_stats_to_zero():
    p = Player(player_id="1", name="X", nba_team="LAL", positions=["PG"], stats={"AST": 6.0})
    assert p.stats["AST"] == 6.0
    assert p.stat("REB") == 0.0  # missing stat reads as 0

def test_league_settings_is_category():
    s = LeagueSettings(league_key="428.l.1", format="category",
                       categories=["PTS", "AST"], roster_slots={"PG": 1})
    assert s.is_category is True

def test_league_settings_points_format():
    from fantasy_gm.schemas import LeagueSettings
    s = LeagueSettings(league_key="k", format="points",
                       point_weights={"PTS": 1.0, "AST": 1.5})
    assert s.is_points is True
    assert s.is_category is False
    assert s.point_weights["AST"] == 1.5


def test_format_label():
    from fantasy_gm.schemas import LeagueSettings
    cat = LeagueSettings(league_key="k", format="category",
                         categories=["PTS", "AST", "REB"])
    pts = LeagueSettings(league_key="k", format="points")
    assert cat.format_label == "3-cat"
    assert pts.format_label == "Points"
