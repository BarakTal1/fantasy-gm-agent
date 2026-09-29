#!/bin/bash
set -e

# Start the app — works in Railway (/app/src) and local dev (./src)
APP_DIR="${APP_DIR:-.}/src"
cd "$APP_DIR"
python -m uvicorn fantasy_gm.api:app --host 0.0.0.0 --port ${PORT:-8000}
