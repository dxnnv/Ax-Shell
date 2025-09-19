#!/usr/bin/env bash

# Capture with hyprshot (region selection) and send RAW image to stdout
ocr_text=$(hyprshot -m region -z -r -s | tesseract -l eng - - 2>/dev/null)

# Check if Tesseract returned anything
if [[ -n "$ocr_text" ]]; then
    # Copy the recognized text to the clipboard
    echo -n "$ocr_text" | wl-copy
    notify-send -a "Ax-Shell" "OCR Success" "Text Copied to Clipboard"
else
    notify-send -a "Ax-Shell" "OCR Failed" "No text recognized or operation failed"
fi
