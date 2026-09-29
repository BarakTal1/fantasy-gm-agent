from fantasy_gm.db import execute, fetch_all


def test_insert_and_fetch(db):
    execute(
        "INSERT INTO league_config (league_key, format) VALUES (%s, %s)",
        ("428.l.1", "category"),
    )
    rows = fetch_all("SELECT league_key, format FROM league_config")
    assert rows == [{"league_key": "428.l.1", "format": "category"}]
