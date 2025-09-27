#!/usr/bin/env bash
set -euo pipefail

XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.config}"
APP_DIR="$XDG_CONFIG_HOME/Ax-Shell"
APP_MAIN="$APP_DIR/main.py"
VENV_PY="$APP_DIR/.venv/bin/python"

if [ -x "$VENV_PY" ]; then
  exec "$VENV_PY" "$APP_MAIN"
elif command -v uv >/dev/null 2>&1; then
  uv venv --system-site-packages "$APP_DIR/.venv"
  "$VENV_PY" -m pip install --no-deps "fabric @ git+https://github.com/Fabric-Development/fabric.git"
  exec "$VENV_PY" "$APP_MAIN"
else
  exec python "$APP_MAIN"
fi
