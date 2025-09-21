#!/usr/bin/env bash
# Restart ax-shell depending on whether uwsm is active
set -euo pipefail

MODE="${1-}"
PATH="$HOME/.local/bin/ax-shell"

if command -v uwsm >/dev/null 2>&1 && uwsm check is-active >/dev/null 2>&1; then
    systemctl --user daemon-reload
    if [ "$MODE" = "init" ]; then
	    systemctl --user enable --now ax-shell.service
	  else
      systemctl --user restart ax-shell.service
    fi
else
  if command -v setsid >/dev/null 2>&1; then
    setsid -f "$PATH" >/dev/null 2>&1 || true
  else
    nohup "$PATH" >/dev/null 2>&1 &
    disown || true
  fi
fi