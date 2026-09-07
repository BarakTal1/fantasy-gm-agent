import json
from pathlib import Path

import psycopg
import pytest

from fantasy_gm import db as db_module
from fantasy_gm.config import get_settings
from scripts.run_migrations import run as run_migrations


@pytest.fixture
def db(monkeypatch):
    test_url = get_settings().test_database_url
    run_migrations(test_url)
    # Point the db module at the test database for the duration of the test.
    monkeypatch.setattr(db_module, "_DATABASE_URL", test_url)
    yield
    # Clean all tables between tests.
    with psycopg.connect(test_url) as conn:
        conn.execute(
            "TRUNCATE league_config, player_stat_snapshots, "
            "weekly_schedule, oauth_tokens"
        )
        conn.commit()


@pytest.fixture
def fixture():
    def _load(name: str) -> dict:
        return json.loads((Path("tests/fixtures") / name).read_text())

    return _load
