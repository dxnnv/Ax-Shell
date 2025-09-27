import configparser
import ctypes
import errno
import os
import re
import signal
import struct
import subprocess
from math import pi

from fabric.utils.helpers import get_relative_path
from fabric.widgets.overlay import Overlay
from gi.repository import Gdk, GLib, Gtk
from config.loguru_config import logger

logger = logger.bind(name="Cava", type="Module")

def get_bars(file_path):
    config = configparser.ConfigParser()
    config.read(file_path)
    return int(config['general']['bars'])

CAVA_CONFIG = get_relative_path("../config/cavalcade/cava.ini")
bars = get_bars(CAVA_CONFIG)

def set_death_signal():
    """
    Set the death signal of the child process to SIGTERM so that if the parent
    process is killed, the child (cava) is automatically terminated.
    """
    libc = ctypes.CDLL("libc.so.6")
    pr_set_pdeathsig = 1
    libc.prctl(pr_set_pdeathsig, signal.SIGTERM)

class Cava:
    """
    CAVA wrapper.
    Launch the cava process with certain settings and read output.
    """
    NONE = 0
    RUNNING = 1
    RESTARTING = 2
    CLOSING = 3

    def __init__(self, mainapp):
        self.bars = bars
        self.path = "/tmp/cava.fifo"

        self.cava_config_file = CAVA_CONFIG
        self.data_handler = mainapp.draw.update
        self.command = ["cava", "-p", self.cava_config_file]
        self.state = self.NONE
        self.process = None

        self.env = dict(os.environ)
        self.env["LC_ALL"] = "en_US.UTF-8"  # not sure if it's necessary

        is_16bit = True
        self.byte_type, self.byte_size, self.byte_norm = ("H", 2, 65535) if is_16bit else ("B", 1, 255)

        if not os.path.exists(self.path):
            os.mkfifo(self.path)

        self.fifo_fd = None
        self.fifo_dummy_fd = None
        self.io_watch_id = None

    def _run_process(self):
        try:
            self.process = subprocess.Popen(
                self.command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self.env,
                preexec_fn=set_death_signal  # Ensure cava gets killed when the parent dies.
            )
            self.state = self.RUNNING
        except Exception:
            logger.exception("Failed to launch cava")

    def _start_io_reader(self):
        # Open FIFO in non-blocking mode for reading
        self.fifo_fd = os.open(self.path, os.O_RDONLY | os.O_NONBLOCK)
        # Open dummy write end to prevent getting an EOF on our FIFO
        self.fifo_dummy_fd = os.open(self.path, os.O_WRONLY | os.O_NONBLOCK)
        self.io_watch_id = GLib.unix_fd_add_full(
            GLib.PRIORITY_DEFAULT,
            self.fifo_fd,
            GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR,
            self._io_callback,
            None
        )

    def _io_callback(self, _fd, _condition, _user_data=None):
        if _condition & (GLib.IO_HUP | GLib.IO_ERR):
            try:
                if self.io_watch_id:
                    GLib.source_remove(self.io_watch_id)
            finally:
                self.io_watch_id = None

            for attr in ("fifo_fd", "fifo_dummy_fd"):
                fd = getattr(self, attr, None)
                if fd is not None:
                    try:
                        os.close(fd)
                    except OSError:
                        pass
                    setattr(self, attr, None)

            GLib.idle_add(self.restart)
            return False

        frame_size = self.byte_size * self.bars
        latest = None

        while True:
            try:
                data = os.read(self.fifo_fd, frame_size)
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    break
                return False

            if not data:
                break
            if len(data) != frame_size:
                break
            latest = data

        if latest:
            try:
                fmt = self.byte_type * self.bars
                sample = [v / self.byte_norm for v in struct.unpack(fmt, latest)]
                GLib.idle_add(self.data_handler, sample)
            except (struct.error, Exception):
                pass
        return True

    def _on_stop(self):
        if self.state == self.RESTARTING:
            self.start()
        elif self.state == self.RUNNING:
            self.state = self.NONE

    def start(self):
        """Launch cava"""
        self._start_io_reader()
        self._run_process()

    def restart(self):
        """Restart cava process"""
        if self.state == self.RUNNING:
            self.state = self.RESTARTING
            if self.process and self.process.poll() is None:
                self.process.kill()
        elif self.state == self.NONE:
            self.start()

    def close(self):
        """Stop the cava process"""
        self.state = self.CLOSING
        
        # Stop to IO watch first
        if self.io_watch_id:
            GLib.source_remove(self.io_watch_id)
            self.io_watch_id = None
            
        # Close file descriptors safely
        if self.fifo_fd is not None:
            try:
                os.close(self.fifo_fd)
            except OSError:
                pass
            finally:
                self.fifo_fd = None
                
        if self.fifo_dummy_fd is not None:
            try:
                os.close(self.fifo_dummy_fd)
            except OSError:
                pass
            finally:
                self.fifo_dummy_fd = None
        
        # Kill the process if still running
        if self.process and self.process.poll() is None:
            try:
                self.process.kill()
                self.process.wait(timeout=2.0)  # Wait up to 2 seconds
            except subprocess.TimeoutExpired:
                self.process.kill()
            except Exception:
                pass
        
        # Remove the FIFO file
        if os.path.exists(self.path):
            try:
                os.remove(self.path)
            except OSError:
                pass

class AttributeDict(dict):
    """Dictionary with keys as attributes. Does nothing but easy reading"""
    def __getattr__(self, attr):
        return self.get(attr, 3)

    def __setattr__(self, attr, value):
        self[attr] = value

class Spectrum:
    """Spectrum drawing"""
    def __init__(self):
        self.silence_value = 0
        self.audio_sample = []
        self.color = None
        self._cached_color = None
        self._color_file_mtime = 0
        self._next_color_check_ms = 0
        GLib.timeout_add_seconds(1, self._periodic_color_check)

        self.area = Gtk.DrawingArea()
        self.area.connect("draw", self.redraw)
        self.area.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)

        self.sizes = AttributeDict()
        self.sizes.area = AttributeDict()
        self.sizes.bar = AttributeDict()

        self.silence = 10
        self.max_height = 12

        self.area.connect("configure-event", self.size_update)
        self.color_update()
        self._latest_sample = None
        self._sample_seq = 0
        self._last_painted_seq = -1
        self.area.add_tick_callback(self._on_tick)

    def is_silence(self, value):
        """Check if volume level critically low during last iterations"""
        self.silence_value = 0 if value > 0 else self.silence_value + 1
        return self.silence_value > self.silence

    def update(self, data):
        """Audio data processing"""
        self.color_update_cached()
        self._latest_sample = data
        self._sample_seq += 1
        if self.is_silence(data[0]) and self.silence_value == (self.silence + 1):
            self._latest_sample = [0] * self.sizes.number
            self._sample_seq += 1
            self.area.queue_draw()

    def redraw(self, _widget, cr):
        """Draw spectrum graph"""
        cr.set_source_rgba(*self.color)
        dx = 3

        center_y = self.sizes.area.height / 2  # center vertical of the drawing area
        for i, value in enumerate(self.audio_sample):
            width = self.sizes.bar.width
            radius = width / 2.0
            height = (self.sizes.bar.height * min(float(value), 1.0)) / 2.0
            height = min(height, self.max_height)
            if height == (self.sizes.zero / 2 + 1):
                height *= 0.5

            # Draw rectangle and arcs for rounded ends
            cr.rectangle(dx, center_y - height, width, height * 2)
            cr.arc(dx + radius, center_y - height, radius, 0, 2 * pi)
            cr.arc(dx + radius, center_y + height, radius, 0, 2 * pi)

            cr.close_path()
            dx += width + self.sizes.padding
        cr.fill()

    def _on_tick(self, _widget, frame_clock):
        """Called every vsync; paint the newest sample if it changed."""
        # If we have a new sample since last paint, adopt it and draw.
        if self._sample_seq != self._last_painted_seq and self._latest_sample:
            self.audio_sample = self._latest_sample
            self._last_painted_seq = self._sample_seq
            self.area.queue_draw()
        return True

    def size_update(self, *_):
        """Update drawing geometry"""
        self.sizes.number = bars
        self.sizes.padding = int(100 / bars)
        self.sizes.zero = 0

        self.sizes.area.width = max(1, self.area.get_allocated_width())
        self.sizes.area.height = self.area.get_allocated_height() - 2

        tw = self.sizes.area.width - self.sizes.padding * (self.sizes.number - 1)
        self.sizes.bar.width = max(int(tw / self.sizes.number), 1)
        self.sizes.bar.height = self.sizes.area.height

    def color_update_cached(self):
        """Set drawing color with caching to avoid file reads on every frame"""
        if self._cached_color is not None:
            self.color = self._cached_color
            return
        color_file = get_relative_path("../styles/colors.css")
        try:
            # Check if the file has been modified
            current_mtime = os.path.getmtime(color_file)
            if current_mtime != self._color_file_mtime or self._cached_color is None:
                self._color_file_mtime = current_mtime
                
                color = "#a5c8ff"  # default value
                with open(color_file, "r") as f:
                    content = f.read()
                    m = re.search(r"--primary:\s*(#[0-9a-fA-F]{6})", content)
                    if m:
                        color = m.group(1)
                
                red = int(color[1:3], 16) / 255
                green = int(color[3:5], 16) / 255
                blue = int(color[5:7], 16) / 255
                self._cached_color = Gdk.RGBA(red=red, green=green, blue=blue, alpha=1.0)
                
            self.color = self._cached_color
        except Exception:
            if self._cached_color is None:
                # Fallback to the default color
                self._cached_color = Gdk.RGBA(red=0.647, green=0.784, blue=1.0, alpha=1.0)
                self.color = self._cached_color

    def color_update(self):
        """Set drawing color according to current settings by reading primary color from CSS"""
        color = "#a5c8ff"  # default value
        try:
            with open(get_relative_path("../styles/colors.css"), "r") as f:
                content = f.read()
                m = re.search(r"--primary:\s*(#[0-9a-fA-F]{6})", content)
                if m:
                    color = m.group(1)
        except Exception:
            pass
        red = int(color[1:3], 16) / 255
        green = int(color[3:5], 16) / 255
        blue = int(color[5:7], 16) / 255
        self.color = Gdk.RGBA(red=red, green=green, blue=blue, alpha=1.0)


    def _periodic_color_check(self):
        color_file = get_relative_path("../styles/colors.css")
        try:
            current_mtime = os.path.getmtime(color_file)
            if current_mtime != self._color_file_mtime or self._cached_color is None:
                self._color_file_mtime = current_mtime
                color = "#a5c8ff"
                with open(color_file, "r") as f:
                    content = f.read()
                    m = re.search(r"--primary:\s*(#[0-9a-fA-F]{6})", content)
                    if m:
                        color = m.group(1)
                    red = int(color[1:3], 16) / 255
                    green = int(color[3:5], 16) / 255
                    blue = int(color[5:7], 16) / 255
                    self._cached_color = Gdk.RGBA(red=red, green=green, blue=blue, alpha=1.0)
                    self.color = self._cached_color
        except Exception:
            pass
        return True

class SpectrumRender:
    def __init__(self, mode=None, **kwargs):
        super().__init__(**kwargs)
        self.mode = mode

        self.draw = Spectrum()
        self.cava = Cava(self)
        self.cava.start()

    def get_spectrum_box(self):
        # Get the spectrum box
        box = Overlay(name="cavalcade", h_align='center', v_align='center')
        box.set_size_request(180, 40)
        box.add_overlay(self.draw.area)
        return box
