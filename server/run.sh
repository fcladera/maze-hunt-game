#!/usr/bin/env bash
# Run the maze game server.
# Usage: ./run.sh [uvicorn args...]
# Env overrides (see README.md): MG_TICK_INTERVAL, MG_GRID_SIZE, MG_GEN_SEED, ...
set -euo pipefail

cd "$(dirname "$0")"

HOST="${MG_HOST:-0.0.0.0}"
PORT="${MG_PORT:-8000}"

if [ ! -d .venv ]; then
    echo ">> creating .venv"
    python3 -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet -r requirements.txt
fi

exec .venv/bin/uvicorn main:app --host "$HOST" --port "$PORT" "$@"
