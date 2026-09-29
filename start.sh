#!/bin/bash
set -e

# Start the app (dependencies installed by Railway from requirements.txt)
PYTHONPATH=src uvicorn fantasy_gm.api:app --host 0.0.0.0 --port ${PORT:-8000}
