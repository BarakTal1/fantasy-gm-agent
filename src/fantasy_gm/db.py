from typing import Any

import psycopg
from psycopg.rows import dict_row

from fantasy_gm.config import get_settings

_DATABASE_URL: str | None = None


def _url() -> str:
    return _DATABASE_URL or get_settings().database_url


def fetch_all(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    with psycopg.connect(_url(), row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchall()


def fetch_one(sql: str, params: tuple = ()) -> dict[str, Any] | None:
    with psycopg.connect(_url(), row_factory=dict_row) as conn:
        return conn.execute(sql, params).fetchone()


def execute(sql: str, params: tuple = ()) -> None:
    with psycopg.connect(_url()) as conn:
        conn.execute(sql, params)
        conn.commit()
