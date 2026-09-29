"""Create LangGraph checkpointer tables in Postgres (run once)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from langgraph.checkpoint.postgres import PostgresSaver  # noqa: E402

from fantasy_gm.config import get_settings  # noqa: E402

if __name__ == "__main__":
    with PostgresSaver.from_conn_string(get_settings().database_url) as cp:
        cp.setup()
    print("checkpointer tables created")
