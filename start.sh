#!/bin/bash
set -e

# Install dependencies using uv
uv sync --frozen

# Start the app
PYTHONPATH=src uv run uvicorn fantasy_gm.api:app --host 0.0.0.0 --port ${PORT:-8000}
