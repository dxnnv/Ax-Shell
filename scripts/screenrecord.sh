#!/bin/bash

# Check if XDG_VIDEOS_DIR is not set
if [ -z "$XDG_VIDEOS_DIR" ]; then
  XDG_VIDEOS_DIR="$HOME/Videos"
fi

# Directory where the recordings will be saved
SAVE_DIR="$XDG_VIDEOS_DIR/Recordings"
mkdir -p "$SAVE_DIR"

# If gpu-screen-recorder is already running, SIGINT is sent to stop it gracefully.
if pgrep -f "gpu-screen-recorder" >/dev/null; then
  pkill -SIGINT -f "gpu-screen-recorder"

  # Wait a moment to make sure the recording has stopped and the file is ready.
  sleep 1

  # Gets the last recorded file
  LAST_VIDEO=$(ls -t "$SAVE_DIR"/*.mp4 2>/dev/null | head -n 1)

  # Notification with actions: "View" opens the file, "Open folder" opens the folder
  ACTION=$(notify-send -a "Ax-Shell" "⬜ Recording stopped" -A "view=View" -A "open=Open folder")

  if [ "$ACTION" = "view" ] && [ -n "$LAST_VIDEO" ]; then
    xdg-open "$LAST_VIDEO"
  elif [ "$ACTION" = "open" ]; then
    xdg-open "$SAVE_DIR"
  fi
  exit 0
fi

# Output file name for the new recording
OUTPUT_FILE="$SAVE_DIR/$(date +%Y-%m-%d-%H-%M-%S).mp4"

# Start recording
notify-send -a "Ax-Shell" "🔴 Recording started"
gpu-screen-recorder -w screen -q ultra -a default_output -ac opus -cr full -f 60 -o "$OUTPUT_FILE"
