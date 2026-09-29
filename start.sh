#!/bin/bash
set -e

# Start the app from the src directory (dependencies installed by Railway from requirements.txt)
cd /app/src
python -m uvicorn fantasy_gm.api:app --host 0.0.0.0 --port ${PORT:-8000}
