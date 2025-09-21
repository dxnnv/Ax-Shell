import json
import os

import gi
from aiofiles import stderr

gi.require_version("Gtk", "3.0")
from fabric.utils.helpers import get_relative_path
from gi.repository import Gdk, GLib

APP_NAME = "ax-shell"
APP_NAME_CAP = "Ax-Shell"
LOG_LEVEL = "INFO"

PANEL_POSITION_KEY = "panel_position"
PANEL_POSITION_DEFAULT = "Center"
NOTIF_POS_KEY = "notif_pos"
NOTIF_POS_DEFAULT = "Top"

CACHE_DIR = f"{GLib.get_user_cache_dir()}/{APP_NAME}"

USERNAME = os.getlogin()
HOSTNAME = os.uname().nodename
HOME_DIR = os.path.expanduser("~")

CONFIG_DIR = f"{HOME_DIR}/.config/{APP_NAME_CAP}"

screen = Gdk.Screen.get_default()
CURRENT_WIDTH = screen.get_width()
CURRENT_HEIGHT = screen.get_height()


WALLPAPERS_DIR_DEFAULT = get_relative_path("../assets/wallpapers_example")
CONFIG_FILE = get_relative_path("../config/config.json")
DEFAULT_CONFIG_PATH = f"{CONFIG_DIR}/config/config.json"
MATUGEN_STATE_FILE = os.path.join(CONFIG_DIR, "matugen")


BAR_WORKSPACE_USE_CHINESE_NUMERALS = False
BAR_THEME = "Pills"

DOCK_THEME = "Pills"

PANEL_THEME = "Notch"
DATETIME_12H_FORMAT = False
DATETIME_SHOW_SECONDS = False

def load_config(config_path = DEFAULT_CONFIG_PATH):
    """Load the configuration from config.json"""
    lconfig = {}

    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                lconfig = json.load(f)
        except Exception as e:
            stderr.write(f"Unable to load config: {e}")

    return lconfig


# Import defaults from settings_constants to avoid duplication
from .settings_constants import DEFAULTS

# Load configuration once and use throughout the module
config = load_config(CONFIG_FILE)

# Set configuration values using defaults from settings_constants
WALLPAPERS_DIR = config.get("wallpapers_dir", DEFAULTS["wallpapers_dir"])
BAR_POSITION = config.get("bar_position", DEFAULTS["bar_position"])
VERTICAL = BAR_POSITION in ["Left", "Right"]
CENTERED_BAR = config.get("centered_bar", DEFAULTS["centered_bar"])
DATETIME_12H_FORMAT = config.get("datetime_12h_format", DEFAULTS["datetime_12h_format"])
DATETIME_SHOW_SECONDS = config.get('datetime_show_seconds', False)
TERMINAL_COMMAND = config.get("terminal_command", DEFAULTS["terminal_command"])
DOCK_ENABLED = config.get("dock_enabled", DEFAULTS["dock_enabled"])
DOCK_ALWAYS_OCCLUDED = config.get("dock_always_occluded", DEFAULTS["dock_always_occluded"])
DOCK_ICON_SIZE = config.get("dock_icon_size", DEFAULTS["dock_icon_size"])
BAR_WORKSPACE_SHOW_NUMBER = config.get("bar_workspace_show_number", DEFAULTS["bar_workspace_show_number"])
BAR_WORKSPACE_USE_CHINESE_NUMERALS = config.get("bar_workspace_use_chinese_numerals", DEFAULTS["bar_workspace_use_chinese_numerals"])
BAR_HIDE_SPECIAL_WORKSPACE = config.get("bar_hide_special_workspace", DEFAULTS["bar_hide_special_workspace"])
BAR_THEME = config.get("bar_theme", DEFAULTS["bar_theme"])
DOCK_THEME = config.get("dock_theme", DEFAULTS["dock_theme"])
PANEL_THEME = config.get("panel_theme", DEFAULTS["panel_theme"])

PANEL_POSITION = config.get(PANEL_POSITION_KEY, DEFAULTS[PANEL_POSITION_KEY])
NOTIF_POS = config.get(NOTIF_POS_KEY, DEFAULTS[NOTIF_POS_KEY])

BAR_COMPONENTS_VISIBILITY = {
    "button_apps": config.get("bar_button_apps_visible", DEFAULTS["bar_button_apps_visible"]),
    "systray": config.get("bar_systray_visible", DEFAULTS["bar_systray_visible"]),
    "control": config.get("bar_control_visible", DEFAULTS["bar_control_visible"]),
    "button_tools": config.get("bar_button_tools_visible", DEFAULTS["bar_button_tools_visible"]),
    "button_overview": config.get("bar_button_overview_visible", DEFAULTS["bar_button_overview_visible"]),
    "ws_container": config.get("bar_ws_container_visible", DEFAULTS["bar_ws_container_visible"]),
    "weather": config.get("bar_weather_visible", DEFAULTS["bar_weather_visible"]),
    "metrics": config.get("bar_metrics_visible", DEFAULTS["bar_metrics_visible"]),
    "language": config.get("bar_language_visible", DEFAULTS["bar_language_visible"]),
    "date_time": config.get("bar_date_time_visible", DEFAULTS["bar_date_time_visible"]),
    "button_power": config.get("bar_button_power_visible", DEFAULTS["bar_button_power_visible"]),
}

BAR_METRICS_DISKS = config.get("bar_metrics_disks", DEFAULTS["bar_metrics_disks"])
GPU_DEVICE_INDEX = 0
METRICS_VISIBLE = config.get("metrics_visible", DEFAULTS["metrics_visible"])
METRICS_SMALL_VISIBLE = config.get("metrics_small_visible", DEFAULTS["metrics_small_visible"])
SELECTED_MONITORS = config.get("selected_monitors", DEFAULTS["selected_monitors"])
SETTINGS_WINDOW_RESIZABLE = False
LOG_LEVEL = config.get("log_level", DEFAULTS["log_level"])