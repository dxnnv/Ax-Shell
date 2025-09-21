import os
import gi

gi.require_version("GLib", "2.0")
import setproctitle
from fabric import Application
from fabric.core import service as _core_service
from fabric.utils import exec_shell_command_async, get_relative_path
from gi.repository import GLib, GObject
from typing import Any, Callable, cast

from config.data import APP_NAME, APP_NAME_CAP, CACHE_DIR, CONFIG_FILE
from config.loguru_config import setup_logging, logger
from modules.bar import Bar
from modules.corners import Corners
from modules.dock import Dock
from modules.notch import Notch
from modules.notifications import NotificationPopup
from modules.updater import run_updater

fonts_updated_file = f"{CACHE_DIR}/fonts_updated"

Service = _core_service.Service
NotifyType = Callable[..., None]
_OriginalNotify = _core_service.Service.notify

def _safe_notify(self: Any, *properties: str) -> None:
    """Only notify for properties that actually exist on this GObject."""
    valid: list[str] = []
    for prop in properties:
        p = prop.split("::")[-1]
        try:
            if any(ps.name == p for ps in GObject.list_properties(self)):
                valid.append(p)
        except Exception:
            valid.append(p)
    if valid:
        _OriginalNotify(self, *valid)

_core_service.Service.notify = _safe_notify
setattr(Service, "notify", cast(NotifyType, _safe_notify))

if __name__ == "__main__":
    setproctitle.setproctitle(APP_NAME)

    if not os.path.isfile(CONFIG_FILE):
        config_script_path = get_relative_path("config/config.py")
        exec_shell_command_async(f"python {config_script_path}")

    current_wallpaper = os.path.expanduser("~/.current.wall")
    if not os.path.exists(current_wallpaper):
        example_wallpaper = os.path.expanduser(
            f"~/.config/{APP_NAME_CAP}/assets/wallpapers_example/example-1.jpg"
        )
        os.symlink(example_wallpaper, current_wallpaper)

    # Load configuration
    from config.data import load_config

    config = load_config()
    log_level = config.get("log_level", "INFO")

    # Setup logging
    setup_logging(level="DEBUG", capture_stdlib=True)
    logger = logger.bind(name="Ax-Shell", type="Main", tag="Main")

    GLib.idle_add(run_updater)
    # Every hour
    GLib.timeout_add(3600000, run_updater)

    # Initialize multi-monitor services
    try:
        from utils.monitor_manager import get_monitor_manager
        from services.monitor_focus import get_monitor_focus_service
        from utils.global_keybinds import init_global_keybind_objects
        
        monitor_manager = get_monitor_manager()
        monitor_focus_service = get_monitor_focus_service()
        monitor_manager.set_monitor_focus_service(monitor_focus_service)
        init_global_keybind_objects()
        
        # Get all available monitors
        all_monitors = monitor_manager.get_monitors()
        multi_monitor_enabled = True
    except ImportError:
        get_monitor_manager = None
        get_monitor_focus_service = None
        init_global_keybind_objects = None

        # Fallback to single monitor mode
        all_monitors = [{'id': 0, 'name': 'default'}]
        monitor_manager = None
        multi_monitor_enabled = False
    
    # Filter monitors based on the selected_monitors configuration
    selected_monitors_config = config.get("selected_monitors", [])
    
    # If selected_monitors is empty, show on all monitors (current behavior)
    if not selected_monitors_config:
        monitors = all_monitors
        logger.debug("No specific monitors selected, showing on all monitors")
    else:
        # Filter monitors to only include selected ones
        monitors = []
        selected_monitor_names = set(selected_monitors_config)
        
        for monitor in all_monitors:
            monitor_name = monitor.get('name', f'monitor-{monitor.get("id", 0)}')
            if monitor_name in selected_monitor_names:
                monitors.append(monitor)
                logger.debug(f"Including monitor '{monitor_name}' (selected)")
            else:
                logger.debug(f"Excluding monitor '{monitor_name}' (not selected)")
        
        # Fallback: if no valid monitors found, use all monitors
        if not monitors:
            logger.debug("No valid selected monitors found, falling back to all monitors")
            monitors = all_monitors
    
    # Create the application components list
    app_components = []
    corners = None
    notification = None

    bar_monitors = monitors
    active_bar_monitor_ids = [m['id'] for m in bar_monitors]
    single_bar_mode = (len(active_bar_monitor_ids) == 1)

    # Create components for each monitor
    for monitor in monitors:
        monitor_id = monitor['id']

        if monitor_id == 0:
            corners = Corners()
            corners_visible = config.get("corners_visible", True)
            corners.set_visible(corners_visible)
            app_components.append(corners)

        notch = Notch(monitor_id=monitor_id) if multi_monitor_enabled else Notch()
        dock = Dock(monitor_id=monitor_id) if multi_monitor_enabled else Dock()

        if multi_monitor_enabled:
            bar = Bar(
                monitor_id=monitor_id,
                single_bar_mode=single_bar_mode,
                active_bar_monitor_ids=active_bar_monitor_ids,
            )
        else:
            bar = Bar(single_bar_mode=True, active_bar_monitor_ids=[0])

        bar.notch = notch
        notch.bar = bar
        bar.set_notch(notch)

        if monitor_id == 0:
            notification = NotificationPopup(widgets=notch.dashboard.widgets)
            app_components.append(notification)
        
        # Register instances in the monitor manager if available
        if multi_monitor_enabled and monitor_manager:
            monitor_manager.register_monitor_instances(monitor_id, {
                'bar': bar,
                'notch': notch,
                'dock': dock,
                'corners': corners if monitor_id == 0 else None
            })
        
        # Add components to the app list
        app_components.extend([bar, notch, dock])

    # Create the application with all components
    app = Application(f"{APP_NAME}", *app_components)

    def set_css():
        app.set_stylesheet_from_file(get_relative_path("main.css"),)

    app.set_css = set_css
    app.set_css()
    app.run()
