import json
import os
import shutil
import subprocess
import time

import gi
import toml

gi.require_version("Gtk", "3.0")
from fabric.utils.helpers import exec_shell_command_async

from config.loguru_config import logger

logger = logger.bind(name="Settings Utils", type="Config")

# Import settings_constants for DEFAULTS
from . import settings_constants
from .data import (APP_NAME, APP_NAME_CAP)  # CONFIG_DIR, HOME_DIR are not used here directly

# Global variable to store binding variables, managed by this module
bind_vars = {}  # It is initialized as empty, load_bind_vars will populate it


def deep_update(target: dict, update: dict) -> dict:
    """
    Recursively update a nested dictionary with values from another dictionary.
    Modifies target in-place.
    """
    for key, value in update.items():
        if isinstance(value, dict) and key in target and isinstance(target[key], dict):
            # If the value is a dictionary and the key already exists in target as a dictionary,
            # then update recursively.
            deep_update(target[key], value)
        else:
            # Otherwise, it simply sets/overwrites the value.
            target[key] = value
    return target  # Although modifying in-place, returning it is a common convention


def ensure_matugen_config():
    """
    Ensure that the matugen configuration file exists and is updated
    with the expected settings.
    """
    expected_config = {
        "config": {
            "reload_apps": True,
            "wallpaper": {
                "command": "swww",
                "arguments": [
                    "img",
                    "-t",
                    "fade",
                    "--transition-duration",
                    "0.5",
                    "--transition-step",
                    "255",
                    "--transition-fps",
                    "180",
                    "-f",
                    "Nearest",
                ],
                "set": True,
            },
            "custom_colors": {
                "red": {"color": "#FF0000", "blend": True},
                "green": {"color": "#00FF00", "blend": True},
                "yellow": {"color": "#FFFF00", "blend": True},
                "blue": {"color": "#0000FF", "blend": True},
                "magenta": {"color": "#FF00FF", "blend": True},
                "cyan": {"color": "#00FFFF", "blend": True},
                "white": {"color": "#FFFFFF", "blend": True},
            },
        },
        "templates": {
            "hyprland": {
                "input_path": f"~/.config/{APP_NAME_CAP}/config/matugen/templates/hyprland-colors.conf",
                "output_path": f"~/.config/{APP_NAME_CAP}/config/hypr/colors.conf",
                "post_hook": "hyprctl reload || true",
            },
            f"{APP_NAME}": {
                "input_path": f"~/.config/{APP_NAME_CAP}/config/matugen/templates/{APP_NAME}.css",
                "output_path": f"~/.config/{APP_NAME_CAP}/styles/colors.css",
                "post_hook": f"fabric-cli exec {APP_NAME} 'app.set_css()' &",
            },
            "kitty": {
                "input_path": f"~/.config/{APP_NAME_CAP}/config/matugen/templates/kitty-colors.conf",
                "output_path": "~/.config/kitty/colors.conf",
                "post_hook": "kitty @ set-colors --all ~/.config/kitty/colors.conf || true",
            },
            "rofi": {
                "input_path": f"~/.config/{APP_NAME_CAP}/config/matugen/templates/rofi-colors.rasi",
                "output_path": "~/.config/rofi/colors.rasi"
            },
            "gtk4": {
                "input_path": "~/.config/Ax-Shell/config/matugen/templates/gtk-4.0/gtk.css",
                "output_path": "~/.config/gtk-4.0/gtk.css"
            },
            "gtk3": {
                "input_path": "~/.config/Ax-Shell/config/matugen/templates/gtk-3.0/gtk.css",
                "output_path": "~/.config/gtk-3.0/gtk.css"
            },
            "qt5ct": {
                "input_path": "~/.config/Ax-Shell/config/matugen/templates/qt/colors/Matugen.conf",
                "output_path": "~/.config/qt5ct/colors/Matugen.conf"
            },
            "qt6ct": {
                "input_path": "~/.config/Ax-Shell/config/matugen/templates/qt/colors/Matugen.conf",
                "output_path": "~/.config/qt6ct/colors/Matugen.conf"
            },
            "wlogout": {
                "input_path": "~/.config/Ax-Shell/config/matugen/templates/wayland/wlogout/colors.css",
                "output_path": "~/.config/wlogout/colors.css"
            },
            "pywalfox": {
                "input_path": "~/.config/Ax-Shell/config/matugen/templates/wal/colors.json",
                "output_path": "~/.cache/wal/colors.json",
                "post_hook": "pywalfox update || true"
            },
        },
    }

    config_path = os.path.expanduser("~/.config/matugen/config.toml")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)

    existing_config = {}
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                existing_config = toml.load(f)
            shutil.copyfile(config_path, config_path + ".bak")
        except toml.TomlDecodeError:
            logger.warning(f"Could not decode TOML from {config_path}. A new default config will be created.")
            existing_config = {}  # Reset if corrupted
        except Exception as e:
            logger.error(f"Error reading or backing up {config_path}: {e}")
            # existing_config might be partially loaded or empty.
            # Continue to attempt to merge with defaults.

    # We use a copy of existing_config for deep_update if we don't want to modify it directly.
    # Or make sure that deep_update doesn't do so if unwanted.
    # The current implementation of deep_update modifies 'target'.
    # To be extra safe, we can pass a copy if existing_config shouldn't change.
    # merged_config = deep_update(existing_config.copy(), expected_config)
    # Or if existing_config can be modified:
    merged_config = deep_update(
        existing_config, expected_config
    )  # existing_config is modified in-place

    try:
        with open(config_path, "w") as f:
            toml.dump(merged_config, f)
    except Exception as e:
        logger.error(f"Unable to write matugen config to {config_path}: {e}")

    current_wall = os.path.expanduser("~/.current.wall")
    hypr_colors = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/config/hypr/colors.conf")
    css_colors = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/styles/colors.css")

    if (
            not os.path.exists(current_wall)
            or not os.path.exists(hypr_colors)
            or not os.path.exists(css_colors)
    ):
        os.makedirs(os.path.dirname(hypr_colors), exist_ok=True)
        os.makedirs(os.path.dirname(css_colors), exist_ok=True)

        image_path = ""
        if not os.path.exists(current_wall):
            example_wallpaper_path = os.path.expanduser(
                f"~/.config/{APP_NAME_CAP}/assets/wallpapers_example/example-1.jpg")
            if os.path.exists(example_wallpaper_path):
                try:
                    # If it already exists (possibly a broken link or regular file), delete and re-link
                    if os.path.lexists(current_wall):  # use lexists to not follow the link if it is one
                        os.remove(current_wall)
                    os.symlink(example_wallpaper_path, current_wall)
                    image_path = example_wallpaper_path
                except Exception as e:
                    logger.error(f"Unable to create symlink for wallpaper: {e}")
        else:
            image_path = (
                os.path.realpath(current_wall)
                if os.path.islink(current_wall)
                else current_wall
            )

        if image_path and os.path.exists(image_path):
            logger.info(f"Generating color theme from wallpaper: {image_path}")
            try:
                matugen_cmd = f"matugen image '{image_path}'"
                exec_shell_command_async(matugen_cmd)
                logger.debug("Matugen color theme generation initiated.")
            except FileNotFoundError:
                logger.critical("Matugen command not found. Please install matugen.")
            except Exception as e:
                logger.error(f"Unable to initiate matugen: {e}")
        elif not image_path:
            logger.warning("No wallpaper path determined to generate matugen theme from.")
        else:  # image_path exists but the file does not
            logger.warning(f"Wallpaper at {image_path} not found. Cannot generate matugen theme.")


def load_bind_vars():
    """
    Load saved key binding variables from JSON, if available.
    Populates the global `bind_vars` in-place.
    """
    global bind_vars  # Required to modify the global bind_vars object

    # 1. Clear the existing bind_vars dictionary.
    bind_vars.clear()
    # 2. Update it with a copy of DEFAULTS.
    bind_vars.update(settings_constants.DEFAULTS.copy())  # Use .copy() to avoid accidentally modifying DEFAULTS

    config_json = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/config/config.json")
    if os.path.exists(config_json):
        try:
            with open(config_json, "r") as f:
                saved_vars = json.load(f)
                # 3. Use deep_update to merge saved_vars into the existing bind_vars.
                deep_update(bind_vars, saved_vars)

                # The logic for securing the structure of nested dictionaries
                # such as 'metrics_visible' and 'metrics_small_visible'
                # must operate on the already updated 'bind_vars'.
                for vis_key in ["metrics_visible", "metrics_small_visible"]:
                    # Ensure the key exists in DEFAULTS as a structure reference
                    if vis_key in settings_constants.DEFAULTS:
                        default_sub_dict = settings_constants.DEFAULTS[vis_key]
                        # If the key is not in bind_vars or is not a dictionary after deep_update,
                        # restore it from a copy of DEFAULTS for that key.
                        if not isinstance(bind_vars.get(vis_key), dict):
                            bind_vars[vis_key] = default_sub_dict.copy()
                        else:
                            # If it is a dictionary, ensure that all subkeys of DEFAULTS are present.
                            current_sub_dict = bind_vars[vis_key]
                            for m_key, m_val in default_sub_dict.items():
                                if m_key not in current_sub_dict:
                                    current_sub_dict[m_key] = m_val
        except json.JSONDecodeError:
            logger.warning(f"Could not decode JSON from {config_json}. Using defaults (already initialized).")
        except Exception as e:
            logger.error(f"Unable to load config from {config_json}: {e}. Using defaults (already initialized).")
        # bind_vars is already populated with DEFAULTS.


def generate_hyprconf() -> str:
    """
    Generate the Hypr configuration string using the current bind_vars.
    """
    home = os.path.expanduser("~")
    # Determine an animation type based on bar position
    bar_position = bind_vars.get("bar_position", "Top")
    is_vertical = bar_position in ["Left", "Right"]
    animation_type = "slidefadevert" if is_vertical else "slidefade"

    return f"""
exec = pgrep -x "hypridle" > /dev/null || uwsm app -- hypridle
exec-once = uwsm app -- swww-daemon
exec-once =  wl-paste --type text --watch cliphist store
exec-once =  wl-paste --type image --watch cliphist store

$fabricSend = fabric-cli exec {APP_NAME}

bind = {bind_vars.get('prefix_restart', 'SUPER ALT')}, {bind_vars.get('suffix_restart', 'B')}, exec, {home}/.config/{APP_NAME_CAP}/shell/restart_shell.sh # Reload {APP_NAME_CAP}
bind = {bind_vars.get("prefix_dash", "SUPER")}, {bind_vars.get("suffix_dash", "D")}, exec, $fabricSend 'notch.open_notch("dashboard")' # Dashboard
bind = {bind_vars.get("prefix_pins", "SUPER")}, {bind_vars.get("suffix_pins", "Q")}, exec, $fabricSend 'notch.open_notch("pins")' # Pins
bind = {bind_vars.get("prefix_kanban", "SUPER")}, {bind_vars.get("suffix_kanban", "N")}, exec, $fabricSend 'notch.open_notch("kanban")' # Kanban
bind = {bind_vars.get("prefix_launcher", "SUPER")}, {bind_vars.get("suffix_launcher", "R")}, exec, $fabricSend 'notch.open_notch("launcher")' # App Launcher
bind = {bind_vars.get("prefix_tmux", "SUPER")}, {bind_vars.get("suffix_tmux", "T")}, exec, $fabricSend 'notch.open_notch("tmux")' # Tmux
bind = {bind_vars.get("prefix_cliphist", "SUPER")}, {bind_vars.get("suffix_cliphist", "V")}, exec, $fabricSend 'notch.open_notch("cliphist")' # Clipboard History
bind = {bind_vars.get("prefix_toolbox", "SUPER")}, {bind_vars.get("suffix_toolbox", "S")}, exec, $fabricSend 'notch.open_notch("tools")' # Toolbox
bind = {bind_vars.get("prefix_overview", "SUPER")}, {bind_vars.get("suffix_overview", "TAB")}, exec, $fabricSend 'notch.open_notch("overview")' # Overview
bind = {bind_vars.get("prefix_wallpapers", "SUPER")}, {bind_vars.get("suffix_wallpapers", "COMMA")}, exec, $fabricSend 'notch.open_notch("wallpapers")' # Wallpapers
bind = {bind_vars.get("prefix_randwall", "SUPER")}, {bind_vars.get("suffix_randwall", "COMMA")}, exec, $fabricSend 'notch.dashboard.wallpapers.set_random_wallpaper(None, external=True)' # Random Wallpaper
bind = {bind_vars.get("prefix_mixer", "SUPER")}, {bind_vars.get("suffix_mixer", "M")}, exec, $fabricSend 'notch.open_notch("mixer")' # Audio Mixer
bind = {bind_vars.get("prefix_emoji", "SUPER")}, {bind_vars.get("suffix_emoji", "PERIOD")}, exec, $fabricSend 'notch.open_notch("emoji")' # Emoji Picker
bind = {bind_vars.get("prefix_power", "SUPER")}, {bind_vars.get("suffix_power", "ESCAPE")}, exec, $fabricSend 'notch.open_notch("power")' # Power Menu
bind = {bind_vars.get('prefix_weather', 'SUPER ALT')}, {bind_vars.get('suffix_weather', 'J')}, exec, $fabricSend 'notch.open_notch("weather")' # Weather
bind = {bind_vars.get("prefix_caffeine", "SUPER SHIFT")}, {bind_vars.get("suffix_caffeine", "M")}, exec, $fabricSend 'notch.dashboard.widgets.buttons.caffeine_button.toggle_inhibit(external=True)' # Toggle Caffeine
bind = {bind_vars.get("prefix_css", "SUPER SHIFT")}, {bind_vars.get("suffix_css", "B")}, exec, $fabricSend 'app.set_css()' # Reload CSS
bind = {bind_vars.get('prefix_restart_inspector', 'SUPER CTRL ALT')}, {bind_vars.get('suffix_restart_inspector', 'B')}, exec, killall {APP_NAME}; bash -c \"uwsm -- app \$(GTK_DEBUG=interactive uv run {home}/.config/{APP_NAME_CAP}/main.py)" # Restart with inspector

# Wallpapers directory: {bind_vars.get("wallpapers_dir", "~/.config/Ax-Shell/assets/wallpapers_example")}

source = {home}/.config/{APP_NAME_CAP}/config/hypr/colors.conf

layerrule = noanim, fabric

exec = cp $wallpaper ~/.current.wall

general {{
    col.active_border = rgb($primary)
    col.inactive_border = rgb($surface)
    gaps_in = 2
    gaps_out = 4
    border_size = 2
    layout = dwindle
}}

cursor {{
  no_warps=true
}}

decoration {{
    blur {{
        enabled = yes
        size = 1
        passes = 3
        new_optimizations = yes
        contrast = 1
        brightness = 1
    }}
    rounding = 14
    shadow {{
      enabled = true
      range = 10
      render_power = 2
      color = rgba(0, 0, 0, 0.25)
    }}
}}

animations {{
    enabled = yes
    bezier = myBezier, 0.4, 0.0, 0.2, 1.0
    animation = windows, 1, 2.5, myBezier, popin 80%
    animation = border, 1, 2.5, myBezier
    animation = fade, 1, 2.5, myBezier
    animation = workspaces, 1, 2.5, myBezier, {animation_type} 20%
}}
"""


def ensure_face_icon():
    """
    Ensure the face icon exists. If not, copy the default icon.
    """
    face_icon_path = os.path.expanduser("~/.face.icon")
    default_icon_path = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/assets/default.png")
    if not os.path.exists(face_icon_path) and os.path.exists(default_icon_path):
        try:
            shutil.copy(default_icon_path, face_icon_path)
        except Exception as e:
            logger.error(f"Unable to copy default face icon: {e}")


def backup_and_replace(src: str, dest: str, config_name: str):
    """
    Create a backup of the existing configuration file and replace it with a new one.
    """
    try:
        if os.path.exists(dest):
            backup_path = dest + ".bak"
            # Make sure the backup directory exists if it is different
            # os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy(dest, backup_path)
            logger.info(f"{config_name} config backed up to {backup_path}")
        os.makedirs(os.path.dirname(dest), exist_ok=True)  # Ensure dest directory exists
        shutil.copy(src, dest)
        logger.info(f"{config_name} config replaced from {src}")
    except Exception as e:
        logger.error(f"Unable to backup/replace {config_name} config: {e}")


def start_config():
    """
    Run final configuration steps: ensure the necessary configs are present, write the hyprconf, and reload.
    """
    logger.debug(f"{time.time():.4f}: start_config: Ensuring matugen config...")
    ensure_matugen_config()
    logger.debug(f"{time.time():.4f}: start_config: Ensuring face icon...")
    ensure_face_icon()
    logger.debug(f"{time.time():.4f}: start_config: Generating hypr conf...")

    hypr_config_dir = os.path.expanduser(f"~/.config/{APP_NAME_CAP}/config/hypr/")
    os.makedirs(hypr_config_dir, exist_ok=True)
    # Using APP_NAME for .conf file name to match SOURCE_STRING fixed
    hypr_conf_path = os.path.join(hypr_config_dir, f"{APP_NAME}.conf")
    try:
        with open(hypr_conf_path, "w") as f:
            f.write(generate_hyprconf())
        logger.debug(f"Generated Hyprland config at {hypr_conf_path}")
    except Exception as e:
        logger.error(f"Unable to write Hyprland config: {e}")
    logger.debug(f"{time.time():.4f}: start_config: Finished generating hypr conf.")

    logger.debug(f"{time.time():.4f}: start_config: Initiating hyprctl reload...")
    try:
        # subprocess.run(["hyprctl", "reload"], check=True, capture_output=True, text=True)
        exec_shell_command_async("hyprctl reload")  # Keep async to avoid blocking
        logger.debug(f"{time.time():.4f}: start_config: Hyprland configuration reload initiated.")
    except FileNotFoundError:
        logger.critical("hyprctl command not found. Cannot reload Hyprland.")
    except subprocess.CalledProcessError as e:  # If we used subprocess.run with check=True
        logger.critical(f"Unable to reload Hyprland with hyprctl: {e}\nOutput:\n{e.stdout}\n{e.stderr}")
    except Exception as e:
        logger.error(f"An error occurred initiating hyprctl reload: {e}")
    logger.debug(f"{time.time():.4f}: start_config: Finished initiating hyprctl reload.")
