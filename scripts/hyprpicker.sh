#!/bin/bash
set -Eeuo pipefail

case "$1" in
  -rgb|-hex|-hsv) ;;
  *) echo "Usage: $0 [-rgb|-hex|-hsv]"; exit 1 ;;
esac

MODE="${1#-}"
ICON="$(mktemp -t hyprcolor.XXXXXX.png)"
trap 'rm -f "$ICON"' EXIT

# Pick once; copy to clipboard for consistency across modes.
VAL="$(hyprpicker -n -f "$MODE" || true)"
[[ -n "$val" ]] || exit 2

printf %s "$VAL" | wl-copy -n

if [[ "$MODE" == "hex" ]]; then
    IM_COLOR="$VAL"
else
    IM_COLOR="${MODE}(${VAL})"
fi

magick -size 64x64 xc:"$IM_COLOR" "$ICON"
notify-send "$MODE color picked" "$IM_COLOR" -i "$ICON" -a "Hyprpicker"