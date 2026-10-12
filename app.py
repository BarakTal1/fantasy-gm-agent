"""Vercel entrypoint: expose the FastAPI app (source lives in src/)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from fantasy_gm.api import app  # noqa: E402,F401
