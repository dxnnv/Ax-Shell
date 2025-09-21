#!/bin/bash

set -e  # Exit immediately if a command fails
set -u  # Treat unset variables as errors
set -o pipefail  # Prevent errors in a pipeline from being masked

REPO_URL="https://github.com/dxnnv/Ax-Shell.git"
INSTALL_DIR="$HOME/.config/Ax-Shell"
EXECUTABLE_PATH="$HOME/.local/bin/ax-shell"
PACKAGES=(
  cava
  cliphist
  curl
  ddcutil
  fabric-cli-git
  fontconfig
  gobject-introspection
  gpu-screen-recorder
  hypridle
  hyprlock
  hyprpicker
  hyprshot
  hyprsunset
  imagemagick
  libnotify
  matugen-bin
  noto-fonts-emoji
  nvtop
  openresolv
  playerctl
  python-gobject
#  python-dateutil
#  python-ijson
#  python-numpy
#  python-pillow
#  python-psutil
#  python-pywayland
#  python-requests
#  python-setproctitle
#  python-toml
#  python-tzlocal
#  python-watchdog
  uv
  swappy
  swww-git
  tesseract
  tmux
  ttf-nerd-fonts-symbols-mono
  unzip
  uwsm
  vte3
  webp-pixbuf-loader
  wl-clipboard
)

# Prevent running as root
if [ "$(id -u)" -eq 0 ]; then
    echo "Please do not run this script as root."
    exit 1
fi

aur_helper="yay"

# Check if paru exists, otherwise use yay
if command -v paru &>/dev/null; then
    aur_helper="paru"
elif ! command -v yay &>/dev/null; then
    echo "Installing yay-bin..."
    tmpdir=$(mktemp -d)
    git clone --depth=1 https://aur.archlinux.org/yay-bin.git "$tmpdir/yay-bin"
    (cd "$tmpdir/yay-bin" && makepkg -si --noconfirm)
    rm -rf "$tmpdir"
fi

# Clone or update the repository
if [ -d "$INSTALL_DIR" ]; then
    echo "Updating Ax-Shell..."
    git -C "$INSTALL_DIR" pull
else
    echo "Cloning Ax-Shell..."
    git clone --depth=1 "$REPO_URL" "$INSTALL_DIR"
fi

# Install required packages using the detected AUR helper (only if missing)
echo "Installing required packages..."
$aur_helper -Syy --needed --devel --noconfirm "${PACKAGES[@]}" || true

echo "Installing gray-git..."
yes | $aur_helper -Syy --needed --devel --noconfirm gray-git || true

echo "Installing required fonts..."
FONT_URL="https://github.com/zed-industries/zed-fonts/releases/download/1.2.0/zed-sans-1.2.0.zip"
LOCAL_FONTS="$HOME/.local/share/fonts"
FONT_DIR="$LOCAL_FONTS/zed-sans"
TEMP_ZIP="$(mktemp /tmp/zed-sans-XXXXXX.zip)"

# Check if fonts are already installed
if [ ! -d "$FONT_DIR" ]; then
    echo "Downloading fonts from $FONT_URL..."
    curl -L -o "$TEMP_ZIP" "$FONT_URL"

    echo "Extracting fonts to $FONT_DIR..."
    mkdir -p "$FONT_DIR"
    unzip -o "$TEMP_ZIP" -d "$FONT_DIR"

    echo "Cleaning up..."
    rm -f "$TEMP_ZIP"
else
    echo "Fonts are already installed. Skipping download and extraction."
fi

# Copy local fonts if not already present
mkdir -p "$LOCAL_FONTS"
if [ ! -d "$LOCAL_FONTS/tabler-icons" ]; then
  echo "Copying bundled fonts into $LOCAL_FONTS..."
  mkdir -p "$LOCAL_FONTS/tabler-icons"
  cp -r "$INSTALL_DIR/assets/fonts/"* "$LOCAL_FONTS"
else
  echo "Bundled fonts already present. Skipping copy."
fi

# Refresh font cache
fc-cache -f "$LOCAL_FONTS" || true

install -d "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/shell/run_shell.sh" "$EXECUTABLE_PATH"

install -Dm0644 "$INSTALL_DIR/shell/shell-template.service" \
  "${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user/ax-shell.service"

cd "$INSTALL_DIR"

uv venv --python 3.13 --system-site-packages
uv sync

uv run python config/config.py

systemctl --user daemon-reload
echo "Installation complete."
echo "Starting Ax-Shell..."
"$INSTALL_DIR"/shell/restart_shell.sh init
