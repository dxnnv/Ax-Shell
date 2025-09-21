#!/usr/bin/env bash
# Restart ax-shell depending on whether uwsm is active
set -euo pipefail

if command -v uwsm >/dev/null 2>&1 && uwsm check is-active >/dev/null 2>&1; then
    if [ "$1" = "init" ]; then
	    systemctl --user stop ax-shell.service
	    systemctl --user enable --now ax-shell.service
	  else
      systemctl --user restart ax-shell.service
    fi
else
    killall -eI ax-shell >/dev/null 2>&1 || true
    exec "$HOME/.local/bin/ax-shell" &
    disown
fi