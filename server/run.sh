#!/usr/bin/env bash
# Run the maze game server.
# Usage: ./run.sh [uvicorn args...]
# Env overrides (see README.md): MG_TICK_INTERVAL, MG_GRID_SIZE, MG_GEN_SEED, ...
set -euo pipefail

cd "$(dirname "$0")"

HOST="${MG_HOST:-0.0.0.0}"
PORT="${MG_PORT:-8000}"

# Choose venv location: prefer /tmp/Volatile (tmpfs, ephemeral) if present,
# otherwise fall back to ~/venv (persistent across reboots).
if [ -d /tmp/Volatile ]; then
    VENV_DIR="/tmp/Volatile/venv-maze-game"
else
    VENV_DIR="$HOME/venv"
fi

if [ ! -d "$VENV_DIR" ]; then
    echo ">> creating venv at $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$VENV_DIR/bin/pip" install --quiet --upgrade pip
    "$VENV_DIR/bin/pip" install --quiet -r requirements.txt
fi

exec "$VENV_DIR/bin/uvicorn" main:app --host "$HOST" --port "$PORT" "$@"
