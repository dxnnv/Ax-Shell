import math

import gi
import contextlib
from fabric.audio.service import Audio
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.scale import Scale
from fabric.widgets.scrolledwindow import ScrolledWindow

gi.require_version("Gtk", "3.0")
from gi.repository import GLib, GObject, Gtk

import config.data as data

vertical_mode = (
    True
    if data.PANEL_THEME == "Panel"
    and (
        data.BAR_POSITION in ["Left", "Right"]
        or data.PANEL_POSITION in ["Start", "End"]
    )
    else False
)

def _supports_writable_volume(obj) -> bool:
    if not isinstance(obj, GObject.Object):
        return False
    pspec = obj.find_property("volume")
    if pspec is None:
        return False
    flags = pspec.flags
    return bool(flags & GObject.ParamFlags.READABLE) and bool(flags & GObject.ParamFlags.WRITABLE)

class MixerSlider(Scale):
    def __init__(self, stream, **kwargs):
        super().__init__(
            name="control-slider",
            orientation="h",
            h_expand=True,
            h_align="fill",
            has_origin=True,
            increments=(0.01, 0.1),
            style_classes=["no-icon"],
            **kwargs,
        )

        self.stream = stream
        self._updating_from_stream = False
        self._hid_value = self.connect("value-changed", self.on_value_changed)

        self._stream_changed_id = stream.connect("changed", self.on_stream_changed)

        self._ensure_adjustment()
        self._set_slider_silently(stream.volume / 100.0)

        self.connect("map", self._on_mapped_first_set)

        # disconnect everything when this widget dies
        self.connect("destroy", self._on_destroy)

        # Apply appropriate style class based on stream type
        if hasattr(stream, "type"):
            if "microphone" in stream.type.lower() or "input" in stream.type.lower():
                self.add_style_class("mic")
            else:
                self.add_style_class("vol")
        else:
            # Default to volume style
            self.add_style_class("vol")

        try:
            self.set_tooltip_text(f"{getattr(stream, 'volume', 0):.0f}%")
        except Exception:
            self.set_tooltip_text("--%")
        self.update_muted_state()

    # ---------- lifecycle / guards ----------

    def _set_slider_silently(self, value: float) -> None:
        """Set the slider value without emitting value-changed."""
        val = float(max(0.0, min(1.0, value)))
        self._updating_from_stream = True
        try:
            if self._hid_value:
                self.handler_block(self._hid_value)
            # use set_value (preferred) or property
            setter = getattr(self, "set_value", None)
            if callable(setter):
                setter(val)
            else:
                self.value = val
        finally:
            if self._hid_value:
                self.handler_unblock(self._hid_value)
            self._updating_from_stream = False

    def _on_mapped_first_set(self, *_):
        self._set_slider_silently(self.stream.volume / 100.0)

    def _on_destroy(self, *_):
        if self._hid_value:
            try: self.disconnect(self._hid_value)
            except Exception: pass
            self._hid_value = 0
        if self._stream_changed_id and self.stream:
            try: self.stream.disconnect(self._stream_changed_id)
            except Exception: pass
            self._stream_changed_id = 0
        self.stream = None

    def _widget_is_ready(self) -> bool:
        try:
            return bool(self.get_mapped()) and self.get_adjustment() is not None
        except Exception:
            return False

    def _ensure_adjustment(self):
        adj = getattr(self, "get_adjustment", lambda: None)()
        if adj is not None:
            return
        try:
            self.set_range(0.0, 1.0)
            return
        except Exception:
            pass
        adj = Gtk.Adjustment(0.0, 0.0, 1.0, 0.01, 0.1, 0.0)
        if callable(getattr(self, "set_adjustment", None)):
            self.set_adjustment(adj)
        elif callable(getattr(self, "configure", None)):
            self.configure(adj, 0.0, 1.0)

    def _remove_idle(self):
        """Remove idle if it still exists, without spamming GLib warnings."""
        if not self._progress_idle_id:
            return
        # Only remove if GLib still knows this source id
        ctx = GLib.MainContext.default()
        src = ctx.find_source_by_id(self._progress_idle_id)
        if src is not None:
            try:
                src.destroy()
            except Exception:
                # Fallback if destroy() isn’t available
                try:
                    GLib.source_remove(self._progress_idle_id)
                except Exception:
                    pass
        self._progress_idle_id = 0

    # ---------- value flow ----------

    def _set_value_safe(self, value: float):
        if not self._widget_is_ready():
            return
        self._ensure_adjustment()
        val = float(max(0.0, min(1.0, value)))
        try:
            self.set_value(val)
        except Exception:
            # If the adj got swapped between checks, try once more
            self._ensure_adjustment()
            with contextlib.suppress(Exception):
                self.set_value(val)

    def on_value_changed(self, _):
        # user-driven update -> write back to service
        if self._updating_from_stream:
            return
        if not self.stream:
            return
        new_vol = self.value * 100.0
        # avoid noisy churn: only write if it actually changed meaningfully
        try:
            if abs(new_vol - float(getattr(self.stream, "volume", new_vol))) < 0.5:
                return
        except Exception:
            pass
        self.stream.volume = new_vol
        self.set_tooltip_text(f"{new_vol:.0f}%")

    def on_stream_changed(self, stream):
        # programmatic update from the service -> silent
        self._set_slider_silently(stream.volume / 100.0)
        self.set_tooltip_text(f"{stream.volume:.0f}%")
        self.update_muted_state()

    def update_muted_state(self):
        if getattr(self.stream, "muted", False):
            self.add_style_class("muted")
        else:
            self.remove_style_class("muted")


class MixerSection(Box):
    def __init__(self, title, **kwargs):
        super().__init__(
            name="mixer-section",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
        )

        self.title_label = Label(
            name="mixer-section-title",
            label=title,
            h_expand=True,
            h_align="fill",
        )

        self.content_box = Box(
            name="mixer-content",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
        )

        self.add(self.title_label)
        self.add(self.content_box)

    def update_streams(self, streams):
        for child in self.content_box.get_children():
            child.destroy()

        for stream in streams:
            stream_container = Box(
                orientation="v", spacing=4, h_expand=True, v_align="center"
            )

            try:
                vol_text = f"{math.ceil(getattr(stream, 'volume', 0))}%"
            except Exception:
                vol_text = "--%"

            label = Label(
                name="mixer-stream-label",
                label=f"[{vol_text}] {getattr(stream, 'description', 'Unknown')}",
                h_expand=True, h_align="start", v_align="center",
                ellipsization="end", max_chars_width=45,
            )
            stream_container.add(label)

            if _supports_writable_volume(stream):
                slider = MixerSlider(stream)
                stream_container.add(slider)
            else:
                # Optional: gray the label or add a tiny note
                # label.add_style_class("muted")  # or another style to indicate read-only
                pass

            self.content_box.add(stream_container)

        self.content_box.show_all()

class Mixer(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="mixer",
            orientation="v",
            spacing=8,
            h_expand=True,
            v_expand=True,
        )

        try:
            self.audio = Audio()
        except Exception as e:
            error_label = Label(
                label=f"Audio service unavailable: {str(e)}",
                h_align="center",
                v_align="center",
                h_expand=True,
                v_expand=True,
            )
            self.add(error_label)
            return

        self.main_container = Box(
            orientation="h" if not vertical_mode else "v",
            spacing=8,
            h_expand=True,
            v_expand=True,
        )

        self.main_container.set_homogeneous(True)

        self.outputs_section = MixerSection("Outputs")
        self.inputs_section = MixerSection("Inputs")

        self.main_container.add(self.outputs_section)
        self.main_container.add(self.inputs_section)

        self.scrolled = ScrolledWindow(
            h_expand=True,
            v_expand=True,
            child=self.main_container,
        )

        self.add(self.scrolled)

        self.audio.connect("changed", self.on_audio_changed)
        self.audio.connect("stream-added", self.on_audio_changed)
        self.audio.connect("stream-removed", self.on_audio_changed)

        self.update_mixer()

    def on_audio_changed(self, *args):
        self.update_mixer()

    def update_mixer(self):
        outputs, inputs = [], []

        if self.audio.speaker:
            outputs.append(self.audio.speaker)
        outputs.extend(self.audio.applications)

        if self.audio.microphone:
            inputs.append(self.audio.microphone)
        inputs.extend(self.audio.recorders)

        # Filter out things that don't have a writable 'volume'
        outputs = [s for s in outputs if _supports_writable_volume(s)]
        inputs  = [s for s in inputs  if _supports_writable_volume(s)]

        self.outputs_section.update_streams(outputs)
        self.inputs_section.update_streams(inputs)