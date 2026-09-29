import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from fantasy_gm.config import get_settings  # noqa: E402


def run(database_url: str) -> None:
    with open("db/schema.sql") as f:
        sql = f.read()
    with psycopg.connect(database_url) as conn:
        conn.execute(sql)
        conn.commit()
    print(f"migrations applied to {database_url}")


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else get_settings().database_url
    run(url)
