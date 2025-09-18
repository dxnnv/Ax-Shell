import subprocess

import gi
from fabric.utils.helpers import exec_shell_command_async
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import Gdk, GLib, Gtk

import config.data as data

gi.require_version('Gtk', '3.0')
import modules.icons as icons

def add_hover_cursor(widget):
    widget.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
    widget.connect("enter-notify-event", lambda w, e: w.get_window().set_cursor(Gdk.Cursor.new_from_name(w.get_display(), "pointer")) if w.get_window() else None)
    widget.connect("leave-notify-event", lambda w, e: w.get_window().set_cursor(None) if w.get_window() else None)

    def _initial_update(self):
        self.update_state()
        return False

class NightModeButton(Button):
    def __init__(self):
        self.night_mode_icon = Label(
            name="night-mode-icon",
            markup=icons.night,
        )
        self.night_mode_label = Label(
            name="night-mode-label",
            label="Night Mode",
            justification="left",
        )
        self.night_mode_label_box = Box(children=[self.night_mode_label, Box(h_expand=True)])
        self.night_mode_status = Label(
            name="night-mode-status",
            label="Enabled",
            justification="left",
        )
        self.night_mode_status_box = Box(children=[self.night_mode_status, Box(h_expand=True)])
        self.night_mode_text = Box(
            name="night-mode-text",
            orientation="v",
            h_align="start",
            v_align="center",
            children=[self.night_mode_label_box, self.night_mode_status_box],
        )
        self.night_mode_box = Box(
            h_align="start",
            v_align="center",
            spacing=10,
            children=[self.night_mode_icon, self.night_mode_text],
        )

        super().__init__(
            name="night-mode-button",
            h_expand=True,
            child=self.night_mode_box,
            on_clicked=self.toggle_hyprsunset,
        )
        add_hover_cursor(self)

        self.widgets = [self, self.night_mode_label, self.night_mode_status, self.night_mode_icon]
        self.check_hyprsunset()

    def toggle_hyprsunset(self, *args):
        """
        Toggle the 'hyprsunset' process:
          - If running, kill it and mark as 'Disabled'.
          - If not running, start it and mark as 'Enabled'.
        """
        GLib.Thread.new("hyprsunset-toggle", self._toggle_hyprsunset_thread, None)
    
    def _toggle_hyprsunset_thread(self, user_data):
        """Background thread to check and toggle hyprsunset without blocking UI."""
        try:
            subprocess.check_output(["pgrep", "hyprsunset"])
            exec_shell_command_async("pkill hyprsunset")
            GLib.idle_add(self.night_mode_status.set_label, "Disabled")
            GLib.idle_add(self._add_disabled_style)
        except subprocess.CalledProcessError:
            exec_shell_command_async("hyprsunset -t 3500")
            GLib.idle_add(self.night_mode_status.set_label, "Enabled")
            GLib.idle_add(self._remove_disabled_style)
    
    def _add_disabled_style(self):
        """Helper to add disabled style to all widgets."""
        for widget in self.widgets:
            widget.add_style_class("disabled")
    
    def _remove_disabled_style(self):
        """Helper to remove disabled style from all widgets."""
        for widget in self.widgets:
            widget.remove_style_class("disabled")

    def check_hyprsunset(self, *args):
        """
        Update the button state based on whether hyprsunset is running.
        """
        GLib.Thread.new("hyprsunset-check", self._check_hyprsunset_thread, None)
    
    def _check_hyprsunset_thread(self, user_data):
        """Background thread to check hyprsunset status without blocking UI."""
        try:
            subprocess.check_output(["pgrep", "hyprsunset"])
            GLib.idle_add(self.night_mode_status.set_label, "Enabled")
            GLib.idle_add(self._remove_disabled_style)
        except subprocess.CalledProcessError:
            GLib.idle_add(self.night_mode_status.set_label, "Disabled")
            GLib.idle_add(self._add_disabled_style)

class CaffeineButton(Button):
    def __init__(self):
        self.caffeine_icon = Label(
            name="caffeine-icon",
            markup=icons.coffee,
        )
        self.caffeine_label = Label(
            name="caffeine-label",
            label="Caffeine",
            justification="left",
        )
        self.caffeine_label_box = Box(children=[self.caffeine_label, Box(h_expand=True)])
        self.caffeine_status = Label(
            name="caffeine-status",
            label="Enabled",
            justification="left",
        )
        self.caffeine_status_box = Box(children=[self.caffeine_status, Box(h_expand=True)])
        self.caffeine_text = Box(
            name="caffeine-text",
            orientation="v",
            h_align="start",
            v_align="center",
            children=[self.caffeine_label_box, self.caffeine_status_box],
        )
        self.caffeine_box = Box(
            h_align="start",
            v_align="center",
            spacing=10,
            children=[self.caffeine_icon, self.caffeine_text],
        )
        super().__init__(
            name="caffeine-button",
            h_expand=True,
            child=self.caffeine_box,
            on_clicked=self.toggle_inhibit,
        )
        add_hover_cursor(self)

        self.widgets = [self, self.caffeine_label, self.caffeine_status, self.caffeine_icon]
        self.check_inhibit()

    def toggle_inhibit(self, *args, external=False):
        """
        Toggle the 'ax-inhibit' process:
          - If running, kill it and mark as 'Disabled' (add 'disabled' class).
          - If not running, start it and mark as 'Enabled' (remove 'disabled' class).
        """
        GLib.Thread.new("caffeine-toggle", self._toggle_inhibit_thread, external)
    
    def _toggle_inhibit_thread(self, external):
        """Background thread to toggle inhibit without blocking UI."""
        try:
            subprocess.check_output(["pgrep", "ax-inhibit"])
            exec_shell_command_async("pkill ax-inhibit")
            GLib.idle_add(self.caffeine_status.set_label, "Disabled")
            GLib.idle_add(self._add_disabled_style)
        except subprocess.CalledProcessError:
            exec_shell_command_async(f"python {data.HOME_DIR}/.config/{data.APP_NAME_CAP}/scripts/inhibit.py")
            GLib.idle_add(self.caffeine_status.set_label, "Enabled")
            GLib.idle_add(self._remove_disabled_style)

        if external:
            # Different if enabled or disabled
            status = "Disabled" if self.caffeine_status.get_label() == "Disabled" else "Enabled"
            message = "Disabled 💤" if status == "Disabled" else "Enabled ☀️"
            exec_shell_command_async(f"notify-send '☕ Caffeine' '{message}' -a '{data.APP_NAME_CAP}' -e")
    
    def _add_disabled_style(self):
        """Helper to add disabled style to all widgets."""
        for widget in self.widgets:
            widget.add_style_class("disabled")
    
    def _remove_disabled_style(self):
        """Helper to remove disabled style from all widgets."""
        for widget in self.widgets:
            widget.remove_style_class("disabled")

    def check_inhibit(self, *args):
        GLib.Thread.new("caffeine-check", self._check_inhibit_thread, None)
    
    def _check_inhibit_thread(self, user_data):
        """Background thread to check inhibit status without blocking UI."""
        try:
            subprocess.check_output(["pgrep", "ax-inhibit"])
            GLib.idle_add(self.caffeine_status.set_label, "Enabled")
            GLib.idle_add(self._remove_disabled_style)
        except subprocess.CalledProcessError:
            GLib.idle_add(self.caffeine_status.set_label, "Disabled")
            GLib.idle_add(self._add_disabled_style)

class Buttons(Gtk.Grid):
    def __init__(self, **kwargs):
        super().__init__(name="buttons-grid")
        self.set_row_homogeneous(True)
        self.set_column_homogeneous(True)
        self.set_row_spacing(4)
        self.set_column_spacing(4)
        self.set_vexpand(False)

        self.widgets = kwargs["widgets"]

        self.night_mode_button = NightModeButton()
        self.caffeine_button = CaffeineButton()

        if data.PANEL_THEME == "Panel" and (data.BAR_POSITION in ["Left", "Right"] or data.PANEL_POSITION in ["Start", "End"]):
            self.attach(self.night_mode_button, 0, 1, 1, 1)
            self.attach(self.caffeine_button, 1, 1, 1, 1)
        else:
            self.attach(self.night_mode_button, 2, 0, 1, 1)
            self.attach(self.caffeine_button, 3, 0, 1, 1)

        self.show_all()
