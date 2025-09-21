#!/usr/bin/env bash
set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_DIR="$XDG_CONFIG_HOME/Ax-Shell"

if command -v uv >/dev/null 2>&1 && [ -d "$APP_DIR/.venv" ]; then
  exec uv run --project "$APP_DIR" python "$APP_DIR/main.py"
elif [ -x "$APP_DIR/.venv/bin/python" ]; then
  exec "$APP_DIR/.venv/bin/python" "$APP_DIR/main.py"
else
  exec python "$APP_DIR/main.py"
fi