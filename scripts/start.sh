#!/usr/bin/env sh
set -e
export PYTHONPATH=/app/src
# --no-sync: deps were installed at build time; don't re-sync (avoids the
# uv local-package rebuild quirk). The app imports via PYTHONPATH, not an install.
uv run --no-sync python scripts/run_migrations.py
uv run --no-sync python scripts/setup_checkpointer.py
uv run --no-sync python scripts/seed_demo_data.py
exec uv run --no-sync uvicorn fantasy_gm.api:app --host 0.0.0.0 --port "${PORT:-8000}"
