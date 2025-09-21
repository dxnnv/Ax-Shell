from fabric.audio.service import Audio
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.scale import Scale

import gi

from utils.monitor_manager import get_monitor_manager

gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib

import json
import config.data as data
import modules.icons as icons
from services.brightness import Brightness
from utils.debounce import DebouncedSetter
from config.loguru_config import logger

logger = logger.bind(name="Controls", type="UI")

def pct_int(x) -> int:
    try:
        return max(0, min(100, int(round(float(x)))))
    except Exception:
        return 0

class VolumeSmall(Box):
    def __init__(self, **kwargs):
        super().__init__(name="button-bar-vol", **kwargs)
        self.audio = Audio()
        self.progress_bar = CircularProgressBar(
            name="button-volume", size=28, line_width=2,
            start_angle=150, end_angle=390,
        )
        self.vol_label = Label(name="vol-label", markup=icons.vol_high)
        self.vol_button = Button(on_clicked=self.toggle_mute, child=self.vol_label)
        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=Overlay(child=self.progress_bar, overlays=self.vol_button),
        )
        self.audio.connect("notify::speaker", self.on_new_speaker)
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self.on_speaker_changed)
        self.event_box.connect("scroll-event", self.on_scroll)
        self.add(self.event_box)
        self.on_speaker_changed()
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

    def on_new_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self.on_speaker_changed)
            self.on_speaker_changed()

    def toggle_mute(self, _):
        current_stream = self.audio.speaker
        if current_stream:
            current_stream.muted = not current_stream.muted
            if current_stream.muted:
                self.on_speaker_changed()
                self.progress_bar.add_style_class("muted")
                self.vol_label.add_style_class("muted")
            else:
                self.on_speaker_changed()
                self.progress_bar.remove_style_class("muted")
                self.vol_label.remove_style_class("muted")

    def on_scroll(self, _, event):
        if self.audio.speaker and event.direction == Gdk.ScrollDirection.SMOOTH:
            v = self.audio.speaker.volume
            if abs(event.delta_y) > 0:
                v = pct_int(v - event.delta_y)
            if abs(event.delta_x) > 0:
                v = pct_int(v + event.delta_x)
            self.audio.speaker.volume = v

    def on_speaker_changed(self, *_):
        if not self.audio.speaker:
            return

        vol_high_icon = icons.vol_high
        vol_medium_icon = icons.vol_medium
        vol_mute_icon = icons.vol_off
        vol_off_icon = icons.vol_mute

        if "bluetooth" in self.audio.speaker.icon_name:
            vol_high_icon = icons.bluetooth_connected
            vol_medium_icon = icons.bluetooth
            vol_mute_icon = icons.bluetooth_off
            vol_off_icon = icons.bluetooth_disconnected

        self.progress_bar.value = self.audio.speaker.volume / 100

        if self.audio.speaker.muted:
            self.vol_button.get_child().set_markup(vol_mute_icon)
            self.progress_bar.add_style_class("muted")
            self.vol_label.add_style_class("muted")
            self.set_tooltip_text("Muted")
            return
        else:
            self.progress_bar.remove_style_class("muted")
            self.vol_label.remove_style_class("muted")
        self.set_tooltip_text(f"{round(self.audio.speaker.volume)}%")
        if self.audio.speaker.volume > 74:
            self.vol_button.get_child().set_markup(vol_high_icon)
        elif self.audio.speaker.volume > 0:
            self.vol_button.get_child().set_markup(vol_medium_icon)
        else:
            self.vol_button.get_child().set_markup(vol_off_icon)

class MicSmall(Box):
    def __init__(self, **kwargs):
        super().__init__(name="button-bar-mic", **kwargs)
        self.audio = Audio()
        self.progress_bar = CircularProgressBar(
            name="button-mic", size=28, line_width=2,
            start_angle=150, end_angle=390,
        )
        self.mic_label = Label(name="mic-label", markup=icons.mic)
        self.mic_button = Button(on_clicked=self.toggle_mute, child=self.mic_label)
        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=Overlay(child=self.progress_bar, overlays=self.mic_button),
        )
        self.audio.connect("notify::microphone", self.on_new_microphone)
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self.on_microphone_changed)
        self.event_box.connect("scroll-event", self.on_scroll)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)
        self.add(self.event_box)
        self.on_microphone_changed()

    def on_new_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self.on_microphone_changed)
            self.on_microphone_changed()

    def toggle_mute(self, _):
        current_stream = self.audio.microphone
        if current_stream:
            current_stream.muted = not current_stream.muted
            if current_stream.muted:
                self.mic_button.get_child().set_markup(icons.mic_mute)
                self.progress_bar.add_style_class("muted")
                self.mic_label.add_style_class("muted")
            else:
                self.on_microphone_changed()
                self.progress_bar.remove_style_class("muted")
                self.mic_label.remove_style_class("muted")

    def on_scroll(self, _, event):
        if self.audio.microphone and event.direction == Gdk.ScrollDirection.SMOOTH:
            v = self.audio.microphone.volume
            if abs(event.delta_y) > 0:
                v = pct_int(v - event.delta_y)
            if abs(event.delta_x) > 0:
                v = pct_int(v + event.delta_x)
            self.audio.microphone.volume = v

    def on_microphone_changed(self, *_):
        if not self.audio.microphone:
            return
        if self.audio.microphone.muted:
            self.mic_button.get_child().set_markup(icons.mic_mute)
            self.progress_bar.add_style_class("muted")
            self.mic_label.add_style_class("muted")
            self.set_tooltip_text("Muted")
            return
        else:
            self.progress_bar.remove_style_class("muted")
            self.mic_label.remove_style_class("muted")
        self.progress_bar.value = self.audio.microphone.volume / 100
        self.set_tooltip_text(f"{round(self.audio.microphone.volume)}%")
        if self.audio.microphone.volume >= 1:
            self.mic_button.get_child().set_markup(icons.mic)
        else:
            self.mic_button.get_child().set_markup(icons.mic_mute)

class VolumeIcon(Box):
    def __init__(self, **kwargs):
        super().__init__(name="vol-icon", **kwargs)
        self.audio = Audio()

        self.vol_label = Label(name="vol-label-dash", markup="", h_align="center", v_align="center", h_expand=True, v_expand=True)
        self.vol_button = Button(on_clicked=self.toggle_mute, child=self.vol_label, h_align="center", v_align="center", h_expand=True, v_expand=True)

        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=self.vol_button,
            h_align="center",
            v_align="center",
            h_expand=True,
            v_expand=True
        )
        self.event_box.connect("scroll-event", self.on_scroll)
        self.add(self.event_box)

        self._pending_value = None
        self._update_source_id = None
        self._periodic_update_source_id = None

        self.audio.connect("notify::speaker", self.on_new_speaker)
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self.on_speaker_changed)

        self._periodic_update_source_id = GLib.timeout_add_seconds(1, self.update_device_icon)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

    def on_scroll(self, _, event):
        if not self.audio.speaker:
            return

        step_size = 5
        current_volume = self.audio.speaker.volume

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0:
                new_volume = pct_int(current_volume + step_size)
            elif event.delta_y > 0:
                new_volume = pct_int(current_volume - step_size)
            else:
                return
        else:
            if event.direction == Gdk.ScrollDirection.UP:
                new_volume = pct_int(current_volume + step_size)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                new_volume = pct_int(current_volume - step_size)
            else:
                return

        self._pending_value = new_volume
        if self._update_source_id is None:
            self._update_source_id = GLib.timeout_add(50, self._update_volume_callback)

    def _update_volume_callback(self):
        if self._pending_value is not None and self._pending_value != self.audio.speaker.volume:
            self.audio.speaker.volume = self._pending_value
            self._pending_value = None
            return True
        else:
            self._update_source_id = None
            return False

    def on_new_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self.on_speaker_changed)
            self.on_speaker_changed()

    def toggle_mute(self, _):
        current_stream = self.audio.speaker
        if current_stream:
            current_stream.muted = not current_stream.muted

            self.on_speaker_changed()

    def on_speaker_changed(self, *_):
        if not self.audio.speaker:

            self.vol_label.set_markup("")
            self.remove_style_class("muted")
            self.vol_label.remove_style_class("muted")
            self.vol_button.remove_style_class("muted")
            self.set_tooltip_text("No audio device")
            return

        if self.audio.speaker.muted:
            self.vol_label.set_markup(icons.headphones)
            self.add_style_class("muted")
            self.vol_label.add_style_class("muted")
            self.vol_button.add_style_class("muted")
            self.set_tooltip_text("Muted")
        else:
            self.remove_style_class("muted")
            self.vol_label.remove_style_class("muted")
            self.vol_button.remove_style_class("muted")

            self.update_device_icon()
            self.set_tooltip_text(f"{round(self.audio.speaker.volume)}%")

    def update_device_icon(self):
        if not self.audio.speaker:
            self.vol_label.set_markup("")
            return True

        if self.audio.speaker.muted:
             return True

        try:
            device_type = self.audio.speaker.port.type
            if device_type == 'headphones':
                self.vol_label.set_markup(icons.headphones)
            elif device_type == 'speaker':
                self.vol_label.set_markup(icons.headphones)
            else:
                 self.vol_label.set_markup(icons.headphones)
        except AttributeError:
            self.vol_label.set_markup(icons.headphones)

        return True

    def destroy(self):
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)

        if hasattr(self, '_periodic_update_source_id') and self._periodic_update_source_id is not None:
            GLib.source_remove(self._periodic_update_source_id)
        super().destroy()

class MicIcon(Box):
    def __init__(self, **kwargs):
        super().__init__(name="mic-icon", **kwargs)
        self.audio = Audio()

        self.mic_label = Label(name="mic-label-dash", markup=icons.mic, h_align="center", v_align="center", h_expand=True, v_expand=True)
        self.mic_button = Button(on_clicked=self.toggle_mute, child=self.mic_label, h_align="center", v_align="center", h_expand=True, v_expand=True)

        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=self.mic_button,
            h_align="center",
            v_align="center",
            h_expand=True,
            v_expand=True
        )
        self.event_box.connect("scroll-event", self.on_scroll)
        self.add(self.event_box)

        self._pending_value = None
        self._update_source_id = None

        self.audio.connect("notify::microphone", self.on_new_microphone)
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self.on_microphone_changed)
        self.on_microphone_changed()
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

    def on_scroll(self, _, event):
        if not self.audio.microphone:
            return

        step_size = 5
        current_volume = self.audio.microphone.volume

        if event.direction == Gdk.ScrollDirection.SMOOTH:
            if event.delta_y < 0:
                new_volume = pct_int(current_volume + step_size)
            elif event.delta_y > 0:
                new_volume = pct_int(current_volume - step_size)
            else:
                return
        else:
            if event.direction == Gdk.ScrollDirection.UP:
                new_volume = pct_int(current_volume + step_size)
            elif event.direction == Gdk.ScrollDirection.DOWN:
                new_volume = pct_int(current_volume - step_size)
            else:
                return

        self._pending_value = new_volume
        if self._update_source_id is None:
            self._update_source_id = GLib.timeout_add(50, self._update_volume_callback)

    def _update_volume_callback(self):
        if self._pending_value is not None and self._pending_value != self.audio.microphone.volume:
            self.audio.microphone.volume = self._pending_value
            self._pending_value = None
            return True
        else:
            self._update_source_id = None
            return False

    def on_new_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self.on_microphone_changed)
            self.on_microphone_changed()

    def toggle_mute(self, _):
        current_stream = self.audio.microphone
        if current_stream:
            current_stream.muted = not current_stream.muted
            if current_stream.muted:
                self.mic_button.get_child().set_markup(icons.mic_mute)
                self.mic_label.add_style_class("muted")
                self.mic_button.add_style_class("muted")
            else:
                self.on_microphone_changed()
                self.mic_label.remove_style_class("muted")
                self.mic_button.remove_style_class("muted")

    def on_microphone_changed(self, *_):
        if not self.audio.microphone:
            return
        if self.audio.microphone.muted:
            self.mic_button.get_child().set_markup(icons.mic_mute)
            self.add_style_class("muted")
            self.mic_label.add_style_class("muted")
            self.set_tooltip_text("Muted")
            return
        else:
            self.remove_style_class("muted")
            self.mic_label.remove_style_class("muted")

        self.set_tooltip_text(f"{round(self.audio.microphone.volume)}%")
        if self.audio.microphone.volume >= 1:
            self.mic_button.get_child().set_markup(icons.mic)
        else:
            self.mic_button.get_child().set_markup(icons.mic_filled)

    def destroy(self):
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
        super().destroy()

class VolumeSlider(Scale):
    def __init__(self, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            h_align="fill",
            has_origin=True,
            increments=(0.01, 0.1),
            **kwargs,
        )
        self.audio = Audio()
        self.audio.connect("notify::speaker", self.on_new_speaker)
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self.on_speaker_changed)
        self.connect("value-changed", self.on_value_changed)
        self.add_style_class("vol")
        self.on_speaker_changed()

    def on_new_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect("changed", self.on_speaker_changed)
            self.on_speaker_changed()

    def on_value_changed(self, _):
        if self.audio.speaker:
            self.audio.speaker.volume = pct_int(self.value * 100)

    def on_speaker_changed(self, *_):
        if not self.audio.speaker:
            return
        self.value = self.audio.speaker.volume / 100
        if self.audio.speaker.muted:
            self.add_style_class("muted")
        else:
            self.remove_style_class("muted")


class MicSlider(Scale):
    def __init__(self, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            has_origin=True,
            increments=(0.01, 0.1),
            **kwargs,
        )
        self.audio = Audio()
        self.audio.connect("notify::microphone", self.on_new_microphone)
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self.on_microphone_changed)
        self.connect("value-changed", self.on_value_changed)
        self.add_style_class("mic")
        self.on_microphone_changed()

    def on_new_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect("changed", self.on_microphone_changed)
            self.on_microphone_changed()

    def on_value_changed(self, _):
        if self.audio.microphone:
            self.audio.microphone.volume = pct_int(self.value * 100)

    def on_microphone_changed(self, *_):
        if not self.audio.microphone:
            return
        self.value = self.audio.microphone.volume / 100
        if self.audio.microphone.muted:
            self.add_style_class("muted")
        else:
            self.remove_style_class("muted")


class BrightnessSlider(Scale):
    def __init__(self, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            has_origin=True,
            increments=(1, 5),
            **kwargs,
        )
        self.client = Brightness.get_initial() if Brightness else None
        if not self.client:
            self.set_sensitive(False)
            return

        self.set_range(0, 100)
        self.add_style_class("brightness")
        self.set_sensitive(False)

        self._syncing = False
        self._pending_value = None
        self._update_source_id = None

        def _apply(v: int):
            v = pct_int(v)
            bus = getattr(self.client, "primary_bus", None)
            if bus is not None and hasattr(self.client, "set_percent"):
                self.client.set_percent(bus, v)
            elif hasattr(self.client, "set_all_percent"):
                self.client.set_all_percent(v)
            else:
                try:
                    setattr(self.client, "all_external_brightness", v)
                except Exception:
                    pass
            self.set_tooltip_text(f"{v}%")

        self._debounced = DebouncedSetter(delay_ms=240, do_set=_apply)

        # listen to service
        self.client.connect("external", self.on_brightness_changed)
        try:
            self.client.connect("displays_changed", self._on_displays_changed)
        except Exception:
            pass

        # interactions
        self.connect("change-value", self._on_change_value)
        self.connect("scroll-event", self._on_scroll)
        self.connect("button-release-event", self._on_release)

        self._on_displays_changed(self.client)

    # --- helpers ---

    def _on_displays_changed(self, *_):
        if getattr(self.client, "external_count", 0) > 0:
            self.set_sensitive(True)
            self._set_value_from_client()
        else:
            self.set_sensitive(False)

    def _avg_percent(self) -> int:
        try:
            bus = getattr(self.client, "primary_bus", None)
            if bus is not None:
                arr = json.loads(self.client.external_brightness_json)
                for e in arr:
                    if int(e.get("display", -9999)) == int(bus):
                        return int(e.get("percent", -1))
            # Fallback if we couldn’t find it
            return int(getattr(self.client, "all_external_brightness"))
        except Exception:
            try:
                arr = json.loads(self.client.external_brightness_json)
                vals = [int(e.get("percent", 0)) for e in arr]
                return round(sum(vals) / len(vals)) if vals else -1
            except Exception:
                return -1

    def _set_value_from_client(self):
        pct = self._avg_percent()
        if pct >= 0:
            self._syncing = True
            try:
                self.set_value(pct)
            finally:
                self._syncing = False
            self.set_tooltip_text(f"{pct}%")
            logger.debug(f"[.SLIDER] Sync from service -> {pct}%")

    # --- events ---

    def _on_change_value(self, _w, _scroll, moved_pos):
        if not self._syncing:
            wanted = pct_int(moved_pos)
            self.set_value(wanted)
            self._debounced.push(wanted)
        return False

    def _apply_pending(self):
        self._apply_timer_id = None
        if self._pending_value is not None:
            v = max(0, min(100, int(self._pending_value)))
            self._pending_value = None
            bus = getattr(self.client, "primary_bus", None)
            if bus is not None and hasattr(self.client, "set_percent"):
                self.client.set_percent(bus, v)
            elif hasattr(self.client, "set_all_percent"):
                self.client.set_all_percent(v)
            else:
                try:
                    setattr(self.client, "all_external_brightness", v)
                except Exception:
                    pass
            self.set_tooltip_text(f"{v}%")
            return False  # one-shot
        return False

    def _clear_idle(self):
        if self._update_source_id is not None:
            logger.debug("[.SLIDER] Cleared idle handle")
            self._update_source_id = None

    def _on_scroll(self, _, event):
        cur = pct_int(self.get_value())
        step = 5
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            delta = (-step if event.delta_y > 0 else step if event.delta_y < 0 else 0)
        else:
            delta = (step if event.direction == Gdk.ScrollDirection.UP
                     else -step if event.direction == Gdk.ScrollDirection.DOWN else 0)
        new_v = pct_int(cur + delta)
        if new_v == cur:
            return True
        self.set_value(new_v)
        self._debounced.push(new_v)
        return True

    def _on_release(self, *_):
        self._debounced.flush_now()
        return False

    def on_brightness_changed(self, *_):
        self._set_value_from_client()

    def destroy(self):
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)

class BrightnessSmall(Box):
    def __init__(self, monitor_id: int, single_bar_mode: bool):
        super().__init__(name="button-bar-brightness")
        self.client = Brightness.get_initial()
        self.monitor_id = monitor_id
        self.mm = get_monitor_manager()

        self._drive_all = len(self.mm.get_monitors()) <= 1
        self.mm.monitor_changed.connect(self._on_monitors_changed)
        self.single_bar_mode = single_bar_mode

        try:
            self.client.connect("external", self.on_brightness_changed)
        except Exception: pass

        try:
            self.client.connect("notify::screen-brightness", self.on_brightness_changed)
        except Exception: pass

        self._visible_when_ready = True
        self.set_no_show_all(False)

        self._updating_from_brightness = False
        self._pending_value = None
        self._update_source_id = None

        self.progress_bar = CircularProgressBar(
            name="button-brightness", size=28, line_width=2,
            start_angle=150, end_angle=390,
        )
        self.brightness_label = Label(name="brightness-label", markup=icons.brightness_high)
        self.brightness_button = Button(child=self.brightness_label)
        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"],
            child=Overlay(child=self.progress_bar, overlays=self.brightness_button),
        )
        self.event_box.connect("scroll-event", self.on_scroll)
        self.add(self.event_box)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

        try:
            self.client.connect("displays_changed", self._maybe_show)
        except Exception:
            pass
        # Poll once a second as a fallback until internal props show up
        GLib.timeout_add_seconds(1, self._maybe_show)
        self._maybe_show()

        self.progress_bar.connect("notify::value", self.on_progress_value_changed)
        self.on_brightness_changed()

    def _on_monitors_changed(self, monitors):
        self._drive_all = len(monitors) <= 1

    def _has_internal(self):
        max_screen = getattr(self.client, "max_screen", -1)
        cur = getattr(self.client, "screen_brightness", -1)
        return (isinstance(max_screen, int) and max_screen > 0) and (isinstance(cur, int) and cur >= 0)

    def _has_any(self):
        has_internal = (getattr(self.client, "max_screen", -1) or -1) > 0
        has_external = (getattr(self.client, "external_count", 0) or 0) > 0
        return has_internal or has_external

    def _maybe_show(self, *_):
        if self._has_any() and not self.get_visible():
            self.show_all()
        else:
            self.hide()
        return not self._has_any()

    def _apply_pct(self, pct: int):
        pct = max(0, min(100, int(pct)))

        if self.single_bar_mode:
            buses = list(self.client.buses)
            if buses:
                self.client.set_percent_many(buses, pct, source="small-all")
        else:
            bus = self.mm.get_focused_monitor_id()
            if bus is not None:
                self.client.set_percent(bus=bus, pct=pct, source="small-one")

    def on_scroll(self, _, event):
        max_screen = getattr(self.client, "max_screen", -1)
        has_internal = isinstance(max_screen, int) and max_screen > 0
        step = 5

        if has_internal:
            current_norm = self.progress_bar.value
            if event.delta_y < 0:
                new_norm = min(current_norm + (step / max_screen), 1)
            elif event.delta_y > 0:
                new_norm = max(current_norm - (step / max_screen), 0)
            else:
                return
            self.progress_bar.value = new_norm
        else:
            cur_pct = int(round(self.progress_bar.value * 100))
            new_pct = cur_pct + (-step if event.delta_y > 0 else step if event.delta_y < 0 else 0)
            new_pct = max(0, min(100, new_pct))
            self.progress_bar.value = new_pct / 100.0

    def on_progress_value_changed(self, widget, _):
        if self._updating_from_brightness:
            return

        max_screen = getattr(self.client, "max_screen", -1)
        has_internal = isinstance(max_screen, int) and max_screen > 0
        norm = float(widget.value)  # 0..1
        if has_internal:
            # INTERNAL: _pending_value is an *absolute* backlight value
            new_brightness = int(round(norm * max_screen))
            self._pending_value = new_brightness
        else:
            # EXTERNAL: _pending_value is a *percent* 0..100
            new_pct = int(round(norm * 100))
            self._pending_value = max(0, min(100, new_pct))

        if self._update_source_id is None:
            self._update_source_id = GLib.timeout_add(50, self._update_brightness_callback)

    def _update_brightness_callback(self):
        self._update_source_id = None
        if self._pending_value is None:
            return False
        max_screen = getattr(self.client, "max_screen", -1)
        has_internal = isinstance(max_screen, int) and max_screen > 0

        try:
            if has_internal:
                # INTERNAL
                cur = getattr(self.client, "screen_brightness", None)
                if isinstance(cur, int) and self._pending_value != cur:
                    self.client.screen_brightness = int(self._pending_value)
            else:
                # EXTERNAL
                v = int(self._pending_value)
                bus = getattr(self.client, "primary_bus", None)
                if bus is not None and hasattr(self.client, "set_percent"):
                    self.client.set_percent(bus, v)
                else:
                    try:
                        setattr(self.client, "all_external_brightness", v)
                    except Exception:
                        pass
        finally:
            self._pending_value = None
        return False

    def _bus_for_monitor(self, monitor_id: int) -> int | None:
        return self.client.bus_map.get(monitor_id)

    def _set_brightness_pct(self, pct: int):
        if self._drive_all:
            # Drive all detected buses
            for bus in self.client.buses:
                self.client.set_percent(bus=bus, pct=pct, source="small")
        else:
            # Drive the bar’s monitor or focused monitor
            target_monitor_id = self.monitor_id or self.mm.get_focused_monitor_id()
            bus = self._bus_for_monitor(target_monitor_id)
            if bus is not None:
                self.client.set_percent(bus=bus, pct=pct, source="small")

    def on_brightness_changed(self, *_):
        max_screen = getattr(self.client, "max_screen", -1)
        cur = getattr(self.client, "screen_brightness", -1)
        has_internal = (isinstance(max_screen, int) and max_screen > 0 and isinstance(cur, int) and cur >= 0)

        if has_internal:
            normalized = cur / max_screen if max_screen > 0 else 0
            pct = int(round(normalized * 100))
        else:
            pct = int(getattr(self.client, "all_external_brightness", -1))
            if pct < 0:
                return
            normalized = pct / 100.0

        self._updating_from_brightness = True
        self.progress_bar.value = normalized
        self._updating_from_brightness = False

        # icon + tooltip
        if pct >= 75:
            self.brightness_label.set_markup(icons.brightness_high)
        elif pct >= 24:
            self.brightness_label.set_markup(icons.brightness_medium)
        else:
            self.brightness_label.set_markup(icons.brightness_low)
        self.set_tooltip_text(f"{pct}%")

    def destroy(self):
        if self._update_source_id is not None:
            GLib.source_remove(self._update_source_id)
        super().destroy()

class BrightnessIcon(Box):
    def __init__(self, **kwargs):
        super().__init__(name="brightness-icon", **kwargs)
        self.client = Brightness.get_initial() if Brightness else None
        if not self.client:
            self.set_sensitive(False)
            return

        self.label = Label(
            name="brightness-label-dash", markup=icons.brightness_high,
            h_align="center", v_align="center", h_expand=True, v_expand=True
        )
        self.button = Button(child=self.label, h_align="center", v_align="center",
                             h_expand=True, v_expand=True)
        self.event_box = EventBox(
            events=["scroll", "smooth-scroll"], child=self.button,
            h_align="center", v_align="center", h_expand=True, v_expand=True
        )
        self.event_box.connect("scroll-event", self.on_scroll)
        self.add(self.event_box)
        self.add_events(Gdk.EventMask.SCROLL_MASK | Gdk.EventMask.SMOOTH_SCROLL_MASK)

        self.client.connect("external", self._on_any_change)
        try:
            self.client.connect("displays_changed", self._on_any_change)
        except Exception:
            pass

        self._on_any_change(self.client)

    def _avg(self) -> int:
        try:
            return int(getattr(self.client, "all_external_brightness", -1))
        except Exception:
            return -1

    def _update_icon(self, pct: int):
        if pct >= 75:
            self.label.set_markup(icons.brightness_high)
        elif pct >= 24:
            self.label.set_markup(icons.brightness_medium)
        else:
            self.label.set_markup(icons.brightness_low)
        self.set_tooltip_text(f"{pct}%")

    def _on_any_change(self, *_):
        # Enable/disable based on whether we have any external displays.
        if getattr(self.client, "external_count", 0) <= 0:
            self.set_sensitive(False)
            return
        self.set_sensitive(True)
        # Pull current value and update icon/tooltip.
        pct = self._avg()
        if isinstance(pct, int) and pct >= 0:
            self._update_icon(pct)

    def on_scroll(self, _w, event):
        pct = self._avg()
        if pct < 0:
            return
        step = 5
        if event.direction == Gdk.ScrollDirection.SMOOTH:
            new_v = pct + (-step if event.delta_y > 0 else step if event.delta_y < 0 else 0)
        else:
            new_v = pct + (step if event.direction == Gdk.ScrollDirection.UP else -step if event.direction == Gdk.ScrollDirection.DOWN else 0)
        new_v = max(0, min(100, new_v))
        bus = getattr(self.client, "primary_bus", None)
        if bus is not None and hasattr(self.client, "set_percent"):
            self.client.set_percent(bus, new_v)
        else:
            try:
                setattr(self.client, "all_external_brightness", new_v)
            except Exception:
                pass

    def destroy(self):
        if getattr(self, "_update_source_id", None) is not None:
            GLib.source_remove(self._update_source_id)
        super().destroy()

class ControlSliders(Box):
    def __init__(self, **kwargs):
        super().__init__(name="control-sliders", orientation="h", spacing=8, **kwargs)

        if Brightness:
            ext_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
            ext_row.add(BrightnessIcon())
            ext_row.add(BrightnessSlider())
            self.add(ext_row)

        volume_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
        volume_row.add(VolumeIcon()); volume_row.add(VolumeSlider()); self.add(volume_row)

        mic_row = Box(orientation="h", spacing=0, h_expand=True, h_align="fill")
        mic_row.add(MicIcon()); mic_row.add(MicSlider()); self.add(mic_row)

        self.show_all()

class ControlSmall(Box):
    def __init__(self, monitor_id: int, single_bar_mode: bool, **kwargs):
        children = []
        bsvc = Brightness.get_initial() if Brightness else None
        if bsvc:
            children.append(BrightnessSmall(monitor_id=monitor_id,
                                            single_bar_mode=single_bar_mode))

        children.extend([VolumeSmall(), MicSmall()])
        super().__init__(
            name="control-small",
            orientation="h" if not data.VERTICAL else "v",
            spacing=4,
            children=children,
            **kwargs,
        )
        self.show_all()
        logger.debug(
            "brightness status: ext_count=%s screen=%s/%s",
            getattr(bsvc, "external_count", None),
            getattr(bsvc, "screen_brightness", None),
            getattr(bsvc, "max_screen", None),
        )