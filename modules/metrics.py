import json
import logging
import subprocess
import time

import psutil
from fabric.core.fabricator import Fabricator
from fabric.utils.helpers import invoke_repeater
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.circularprogressbar import CircularProgressBar
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.revealer import Revealer
from fabric.widgets.scale import Scale
from gi.repository import GLib

import config.data as data
import modules.icons as icons

logger = logging.getLogger(__name__)

class MetricsProvider:
    """
    Class responsible for obtaining centralized CPU, memory, and disk usage metrics.
    It updates periodically so that all widgets querying it display the same values.
    """
    def __init__(self):
        self.gpu = []
        self.cpu = 0.0
        self.mem = 0.0
        self.disk = []
        self._gpu_update_running = False

        GLib.timeout_add_seconds(1, self._update)

    def _update(self):
        self.cpu = psutil.cpu_percent(interval=0)
        self.mem = psutil.virtual_memory().percent
        self.disk = [psutil.disk_usage(path).percent for path in data.BAR_METRICS_DISKS]

        if not self._gpu_update_running:
            self._start_gpu_update_async()

        return True

    def _start_gpu_update_async(self):
        """Starts a new GLib thread to run nvtop in the background."""
        self._gpu_update_running = True

        GLib.Thread.new("nvtop-thread", lambda _: self._run_nvtop_in_thread(), None)

    def _run_nvtop_in_thread(self):
        """Runs nvtop via subprocess in a separate GLib thread."""
        output = None
        error_message = None
        try:
            result = subprocess.check_output(["nvtop", "-s"], text=True, timeout=10)
            output = result
        except FileNotFoundError:
            error_message = "nvtop command not found."
            logger.warning(error_message)
        except subprocess.CalledProcessError as e:
            error_message = f"nvtop failed with exit code {e.returncode}: {e.stderr.strip()}"
            logger.error(error_message)
        except subprocess.TimeoutExpired:
            error_message = "nvtop command timed out."
            logger.error(error_message)
        except Exception as e:
            error_message = f"Unexpected error running nvtop: {e}"
            logger.error(error_message)

        GLib.idle_add(self._process_gpu_output, output, error_message)
        self._gpu_update_running = False

    @staticmethod
    def _safe_load_nvtop(output: str):
        """Load nvtop JSON safely."""
        try:
            return json.loads(output)
        except json.JSONDecodeError:
            start = output.find('[')
            end = output.rfind(']')
            if start != -1 and end != -1 and end > start:
                return json.loads(output[start:end+1])
            raise

    def _process_gpu_output(self, output, error_message):
        try:
            if error_message:
                logger.error(f"GPU update failed: {error_message}")
                self.gpu = []
            elif output:
                info = self._safe_load_nvtop(output)
                if not isinstance(info, list):
                    logger.error(f"Unexpected nvtop payload type: {type(info).__name__}")
                    self.gpu = []
                    return False

                try:
                    idx = int(getattr(data, "GPU_DEVICE_INDEX", 0))
                except Exception:
                    idx = 0

                if 0 <= idx < len(info):
                    v = info[idx] or {}
                    util_raw = v.get("gpu_util")
                    try:
                        util = int(str(util_raw).strip("%")) if util_raw is not None else 0
                    except Exception:
                        util = 0
                    # keep a single-element list so widgets work unchanged
                    self.gpu = [util]
                else:
                    self.gpu = []
            else:
                logger.warning("nvtop returned no output.")
                self.gpu = []
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            self.gpu = []
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Failed parsing nvtop JSON: {e}")
            self.gpu = []
        except Exception as e:
            logger.error(f"Error processing nvtop output: {e}")
            self.gpu = []
        return False

    def get_metrics(self):
        return (self.cpu, self.mem, self.disk, self.gpu)

    def get_gpu_info(self):
        try:
            result = subprocess.check_output(["nvtop", "-s"], text=True, timeout=5)
            info = self._safe_load_nvtop(result)
            if not isinstance(info, list) or not info:
                return []
    
            try:
                idx = int(getattr(data, "GPU_DEVICE_INDEX", 0))
            except Exception:
                idx = 0
    
            if 0 <= idx < len(info):
                return [info[idx]]   # only the selected GPU
            return []
        except FileNotFoundError:
            logger.warning("nvtop not found; GPU info unavailable.")
            return []
        except subprocess.CalledProcessError as e:
            logger.error(f"nvtop init sync failed: {e}")
            return []
        except subprocess.TimeoutExpired:
            logger.error("nvtop init call timed out.")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Init JSON parse error: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error during GPU init: {e}")
            return []


shared_provider = MetricsProvider()

class SingularMetric:
    def __init__(self, id, name, icon):
        self.usage = Scale(
            name=f"{id}-usage",
            value=0.25,
            orientation='v',
            inverted=True,
            v_align='fill',
            v_expand=True,
        )

        self.label = Label(
            name=f"{id}-label",
            markup=icon,
        )

        self.box = Box(
            name=f"{id}-box",
            orientation='v',
            spacing=8,
            children=[
                self.usage,
                self.label,
            ]
        )

        self.box.set_tooltip_markup(f"{icon} {name}")

class Metrics(Box):
    def __init__(self, **kwargs):
        super().__init__(
            name="metrics",
            spacing=8,
            h_align="center",
            v_align="fill",
            visible=True,
            all_visible=True,
        )

        visible = getattr(data, "METRICS_VISIBLE", {'cpu': True, 'ram': True, 'disk': True, 'gpu': True})
        disks = [SingularMetric("disk", f"DISK ({path})" if len(data.BAR_METRICS_DISKS) != 1 else "DISK", icons.disk)
                 for path in data.BAR_METRICS_DISKS] if visible.get('disk', True) else []

        gpu_info = shared_provider.get_gpu_info()
        gpus = [SingularMetric(f"gpu", f"GPU ({v['device_name']})" if len(gpu_info) != 1 else "GPU", icons.gpu)
                for v in gpu_info] if visible.get('gpu', True) else []

        self.cpu = SingularMetric("cpu", "CPU", icons.cpu) if visible.get('cpu', True) else None
        self.ram = SingularMetric("ram", "RAM", icons.memory) if visible.get('ram', True) else None
        self.disk = disks
        self.gpu = gpus

        self.scales = []
        if self.disk: self.scales.extend([v.box for v in self.disk])
        if self.ram: self.scales.append(self.ram.box)
        if self.cpu: self.scales.append(self.cpu.box)
        if self.gpu: self.scales.extend([v.box for v in self.gpu])

        if self.cpu: self.cpu.usage.set_sensitive(False)
        if self.ram: self.ram.usage.set_sensitive(False)
        for disk in self.disk:
            disk.usage.set_sensitive(False)
        for gpu in self.gpu:
            gpu.usage.set_sensitive(False)

        for x in self.scales:
            self.add(x)

        GLib.timeout_add_seconds(1, self.update_status)

    def update_status(self):
        cpu, mem, disks, gpus = shared_provider.get_metrics()

        if self.cpu:
            self.cpu.usage.value = cpu / 100.0
        if self.ram:
            self.ram.usage.value = mem / 100.0
        for i, disk in enumerate(self.disk):

            if i < len(disks):
                disk.usage.value = disks[i] / 100.0
        for i, gpu in enumerate(self.gpu):

            if i < len(gpus):
                gpu.usage.value = gpus[i] / 100.0
        return True

class SingularMetricSmall:
    def __init__(self, id, name, icon):
        self.name_markup = name
        self.icon_markup = icon

        self.icon = Label(name="metrics-icon", markup=icon)
        self.circle = CircularProgressBar(
            name="metrics-circle",
            value=0,
            size=28,
            line_width=2,
            start_angle=150,
            end_angle=390,
            style_classes=id,
            child=self.icon,
        )

        self.level = Label(name="metrics-level", style_classes=id, label="0%")
        self.revealer = Revealer(
            name=f"metrics-{id}-revealer",
            transition_duration=250,
            transition_type="slide-left",
            child=self.level,
            child_revealed=False,
        )

        self.box = Box(
            name=f"metrics-{id}-box",
            orientation="h",
            spacing=0,
            children=[self.circle, self.revealer],
        )

    def markup(self):
        return f"{self.icon_markup} {self.name_markup}" if not data.VERTICAL else f"{self.icon_markup} {self.name_markup}: {self.level.get_label()}"

class MetricsSmall(Button):
    def __init__(self, **kwargs):
        super().__init__(name="metrics-small", **kwargs)

        main_box = Box(

            spacing=0,
            orientation="h" if not data.VERTICAL else "v",
            visible=True,
            all_visible=True,
        )

        visible = getattr(data, "METRICS_SMALL_VISIBLE", {'cpu': True, 'ram': True, 'disk': True, 'gpu': True})
        disks = [SingularMetricSmall("disk", f"DISK ({path})" if len(data.BAR_METRICS_DISKS) != 1 else "DISK", icons.disk)
                 for path in data.BAR_METRICS_DISKS] if visible.get('disk', True) else []

        gpu_info = shared_provider.get_gpu_info()
        gpus = [SingularMetricSmall(f"gpu", f"GPU ({v['device_name']})" if len(gpu_info) != 1 else "GPU", icons.gpu)
                for v in gpu_info] if visible.get('gpu', True) else []

        self.cpu = SingularMetricSmall("cpu", "CPU", icons.cpu) if visible.get('cpu', True) else None
        self.ram = SingularMetricSmall("ram", "RAM", icons.memory) if visible.get('ram', True) else None
        self.disk = disks
        self.gpu = gpus

        for disk in self.disk:
            main_box.add(disk.box)
            main_box.add(Box(name="metrics-sep"))
        if self.ram:
            main_box.add(self.ram.box)
            main_box.add(Box(name="metrics-sep"))
        if self.cpu:
            main_box.add(self.cpu.box)
        for gpu in self.gpu:
            main_box.add(Box(name="metrics-sep"))
            main_box.add(gpu.box)

        self.add(main_box)

        self.connect("enter-notify-event", self.on_mouse_enter)
        self.connect("leave-notify-event", self.on_mouse_leave)

        GLib.timeout_add_seconds(1, self.update_metrics)

        self.hide_timer = None
        self.hover_counter = 0

    def _format_percentage(self, value: int) -> str:
        """Natural percentage format without forcing fixed width."""
        return f"{value}%"

    def on_mouse_enter(self, widget, event):
        if not data.VERTICAL:
            self.hover_counter += 1
            if self.hide_timer is not None:
                GLib.source_remove(self.hide_timer)
                self.hide_timer = None

            if self.cpu: self.cpu.revealer.set_reveal_child(True)
            if self.ram: self.ram.revealer.set_reveal_child(True)
            for disk in self.disk:
                disk.revealer.set_reveal_child(True)
            for gpu in self.gpu:
                gpu.revealer.set_reveal_child(True)
            return False

    def on_mouse_leave(self, widget, event):
        if not data.VERTICAL:
            if self.hover_counter > 0:
                self.hover_counter -= 1
            if self.hover_counter == 0:
                if self.hide_timer is not None:
                    GLib.source_remove(self.hide_timer)
                self.hide_timer = GLib.timeout_add(500, self.hide_revealer)
            return False

    def hide_revealer(self):
        if not data.VERTICAL:
            if self.cpu: self.cpu.revealer.set_reveal_child(False)
            if self.ram: self.ram.revealer.set_reveal_child(False)
            for disk in self.disk:
                disk.revealer.set_reveal_child(False)
            for gpu in self.gpu:
                gpu.revealer.set_reveal_child(False)
            self.hide_timer = None
            return False

    def update_metrics(self):
        cpu, mem, disks, gpus = shared_provider.get_metrics()

        if self.cpu:
            self.cpu.circle.set_value(cpu / 100.0)
            self.cpu.level.set_label(self._format_percentage(int(cpu)))
        if self.ram:
            self.ram.circle.set_value(mem / 100.0)
            self.ram.level.set_label(self._format_percentage(int(mem)))
        for i, disk in enumerate(self.disk):

            if i < len(disks):
                disk.circle.set_value(disks[i] / 100.0)
                disk.level.set_label(self._format_percentage(int(disks[i])))
        for i, gpu in enumerate(self.gpu):

            if i < len(gpus):
                gpu.circle.set_value(gpus[i] / 100.0)
                gpu.level.set_label(self._format_percentage(int(gpus[i])))

        tooltip_metrics = []
        if self.disk: tooltip_metrics.extend(self.disk)
        if self.ram: tooltip_metrics.append(self.ram)
        if self.cpu: tooltip_metrics.append(self.cpu)
        if self.gpu: tooltip_metrics.extend(self.gpu)
        self.set_tooltip_markup((" - " if not data.VERTICAL else "\n").join([v.markup() for v in tooltip_metrics]))

        return True