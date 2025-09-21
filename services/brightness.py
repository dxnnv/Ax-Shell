import json
import re
import time
from typing import Dict, List, Optional, Tuple, Callable

from fabric.core.service import Property, Service, Signal
from fabric.utils import exec_shell_command_async
from gi.repository import GLib

import utils.functions as helpers
from config.loguru_config import logger

logger = logger.bind(name="Brightness", type="Service")

ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
_VCP_BRIGHTNESS = 0x10

# Soft ceilings (used even if `timeout` is unavailable), in milliseconds
CEIL_MS = {
    "detect": 4000,
    "get":    2000,
    "set":    3200,
}
CONFIRM_MS = 1200

def _parse_detect_output(out: str) -> List[int]:
    buses: List[int] = []
    for line in out.splitlines():
        m = re.search(r"I2C\s+bus:\s*/dev/i2c-(\d+)", line, re.I)
        if m:
            b = int(m.group(1))
            if b not in buses:
                buses.append(b)
    return buses

def _parse_getvcp_output(out: str) -> Tuple[Optional[int], Optional[int]]:
    out = out.strip()
    m = re.search(r"^\s*(?:VCP\s+)?(?:16|10|0x10)\s+(?:[A-Za-z]\s+)?(\d+)\s+(\d+)\s*$", out, re.M)
    if m:
        return int(m.group(1)), int(m.group(2))
    m2 = re.search(r"current\s*value\s*=\s*(\d+).*max\s*value\s*=\s*(\d+)", out, re.I | re.S)
    if m2:
        return int(m2.group(1)), int(m2.group(2))
    return None, None

class Brightness(Service):
    instance = None

    @staticmethod
    def get_initial():
        if Brightness.instance is None:
            Brightness.instance = Brightness()
        return Brightness.instance

    @Signal
    def external(self, display: int, value: int) -> None: ...

    @Signal
    def displays_changed(self) -> None: ...

    @property
    def primary_bus(self) -> Optional[int]:
        return self._available[0] if self._available else None

    def __init__(self, poll_seconds: int = 10, **kwargs):
        super().__init__(**kwargs)

        self._pending_confirm: Dict[int, Tuple[int, int]] = {}

        self._available: List[int] = []
        self._current: Dict[int, int] = {}
        self._max_cache: Dict[int, int] = {}

        self._busy = False
        self._queue: List[Tuple[str, Callable, Tuple[str, int]]] = []  # (cmd, cb, kind)
        self._current_cmd_started_ms: Optional[int] = None
        self._current_timeout_src: Optional[int] = None  # GLib source id for our soft timeout
        self._set_backoff_until_ms: Dict[int, int] = {}
        self._set_retry_budget: Dict[int, int] = {}

        self._target_pct: Dict[int, Optional[int]] = {}
        self._inflight_set: Dict[int, bool] = {}
        self._inflight_since_ms: Dict[int, int] = {}
        self._suspend_poll_until_ms = 0

        self._have_timeout = helpers.executable_exists("timeout")
        if not helpers.executable_exists("ddcutil"):
            logger.error("ddcutil not found. Install it and ensure /dev/i2c-* access.")
            return
        if not self._have_timeout:
            logger.warning("coreutils 'timeout' not found; using internal queue-unstick timer instead.")

        self._detect_displays()
        self._redetect_timer = GLib.timeout_add_seconds(8, self._redetect_if_empty)

        if poll_seconds > 0:
            GLib.timeout_add_seconds(poll_seconds, self._poll_all)
        GLib.timeout_add(500, self._watchdog_tick)

    # ---------- Detect / Poll ----------

    def _detect_displays(self):
        def _on_detect_done(proc):
            text = _strip_ansi(_coerce_text_from_proc_result(proc))
            buses = set(_parse_detect_output(text))
            if not buses:
                logger.info(f"[.DETECT] DDC buses: None found")
                return
            merged = sorted(set(self._available) | buses)
            if merged != self._available:
                self._available = merged
                self.emit("displays_changed")
                logger.info(f"[.DETECT] DDC buses: {self._available}")
            for b in self._available:
                self._fetch_one(b)

        base = "env LC_ALL=C /usr/bin/ddcutil --noverify --brief detect 2>&1"
        cmd = self._wrap_timeout("detect", base)
        self._run_cmd(cmd, _on_detect_done, kind=("detect", -1))

    def _poll_all(self):
        now = _now_ms()
        if now < getattr(self, "_suspend_poll_until_ms", 0):
            logger.debug("[.POLL] Suspended to avoid contention")
            return True
        if any(v is not None for v in self._target_pct.values()):
            logger.debug("[.POLL] Skipped; target pending")
            return True

        primaries = [b for b in self._available if b == self.primary_bus]
        for b in primaries:
            self._fetch_one(b)
        return True

    # ---------- Watchdog ----------

    def _watchdog_tick(self):
        now = _now_ms()
        for bus, inflight in list(self._inflight_set.items()):
            if not inflight:
                continue
            age = now - self._inflight_since_ms.get(bus, now)
            if age > 2500:
                logger.warning(f"[.WATCHDOG] Inflight stuck, clearing & backoff (bus={bus} age={age}ms)")
                self._inflight_set[bus] = False
                self._inflight_since_ms.pop(bus, None)
                backoff = max(1400, min(3000, age + 400))
                self._set_backoff_until_ms[bus] = now + backoff
                tgt = self._target_pct.get(bus)
                if tgt is not None:
                    self._pending_confirm[bus] = (tgt, now + backoff + 1500)
                GLib.timeout_add(backoff, lambda b=bus: (self._confirm_after_ceiling(b), False)[1])

        if self._busy and self._current_cmd_started_ms:
            cage = now - self._current_cmd_started_ms
            if cage > 5000:
                if self._current_timeout_src is None:
                    logger.warning("[.WATCHDOG] busy with no ceiling; forcing unstick")
                    self._force_unstick(("get", -1))
                else:
                    logger.warning(f"[.WATCHDOG] Busy for {cage}ms (waiting on current shell). "
                                   f"{'Timeout wrapper should free it.' if self._have_timeout else 'Internal ceiling will unstick it.'}")
        return True

    # ---------- Reads ----------

    def _fetch_one(self, bus: int, *, force: bool = False):
        if not force:
            # If a writing is inflight, or we’re backing off this bus, don’t contend
            if self._inflight_set.get(bus, False) or _now_ms() < self._set_backoff_until_ms.get(bus, 0):
                logger.debug(f"[.GETVCP] skipped; write inflight/backoff (bus={bus})")
                return
        def _done(proc):
            out = _strip_ansi(_coerce_text_from_proc_result(proc))
            if "flock()" in out or "Flock diagnostics" in out or "Max wait time" in out:
                logger.warning(f"[.GETVCP] flock: bus={bus}, {out.strip()!r}")
                return

            cur, mx = _parse_getvcp_output(out)
            if cur is None or mx is None or mx == 0:
                if "Timed out" in out or "timeout" in out:
                    logger.warning(f"[.GETVCP] timeout on bus {bus}: {out.strip()!r}")
                else:
                    logger.warning(f"[.GETVCP] Failed to parse getvcp: bus={bus}, {out!r}")
                return

            self._max_cache[bus] = mx
            pct = int(round((cur / mx) * 100))
            now = _now_ms()
            tgt = self._target_pct.get(bus)

            if tgt is not None and pct != tgt:
                # still schedule a retry / kick below via idle, but don't emit
                logger.debug(f"[.READ_SUPPRESS] bus={bus} have={pct}% want={tgt}% (suppress UI)")
                GLib.idle_add(lambda: (self._kick_set_loop(bus), False)[1])
                return

            # Anti-jitter gate: while a set is being confirmed, ignore stale reads
            hold = self._pending_confirm.get(bus)
            if hold is not None:
                tgt, exp = hold
                if now < exp and pct != tgt:
                    return
                # Clear the confirmation window if it expired, or we matched the target
                if now >= exp or pct == tgt:
                    self._pending_confirm.pop(bus, None)

            if tgt is not None and pct == tgt:
                # We reached the requested value; clear all per-bus state
                self._target_pct[bus] = None
                self._set_retry_budget[bus] = 0
                self._set_backoff_until_ms[bus] = 0
                # let normal polling resume
                self._suspend_poll_until_ms = 0
                logger.debug(f"[.SETTLED] bus={bus} reached {pct}%")

            prev = self._current.get(bus)
            self._current[bus] = pct
            if prev != pct:
                logger.debug(f"[.FETCH] emit external bus={bus}, pct={pct}, raw {cur}/{mx}")
                self.emit("external", bus, pct)

            if self._target_pct.get(bus) == pct:
                logger.debug(f"[.SETTLED] bus={bus} reached {pct}%")
                self._target_pct.pop(bus, None)
                self._pending_confirm.pop(bus, None)

            if tgt is not None and tgt != pct:
                logger.debug(f"post-read mismatch bus={bus}: have={pct}% want={tgt}% -> kick set")
                GLib.idle_add(lambda: (self._kick_set_loop(bus), False)[1])

        base = (
            "env LC_ALL=C /usr/bin/ddcutil "
            "--enable-cross-instance-locks --sleep-multiplier=1.0 "
            f"getvcp 0x10 --bus {bus} --terse --noverify 2>&1"
        )
        cmd = self._wrap_timeout("get", base)
        kind = ("get_force", bus) if force else ("get", bus)
        self._run_cmd(cmd, _done, kind=kind)

    # ---------- Properties ----------

    @Property(str, "readable")
    def external_brightness_json(self) -> str:
        data = [{"display": d, "percent": self._current.get(d, -1)} for d in self._available]
        return json.dumps(data)

    @Property(int, "readable")
    def external_count(self) -> int:
        return len(self._available)

    # ---------- Writes ----------

    def _set_one_raw(self, bus: int, raw: int, mx: Optional[int]):
        if mx is None or mx <= 0:
            mx = self._max_cache.get(bus, 100)
        raw = max(0, min(raw, mx))
        logger.debug(f"[.SETVCP] enqueue: bus={bus}, raw={raw}/{mx}")

        def _done(proc):
            out = _strip_ansi(_coerce_text_from_proc_result(proc))
            try:
                if "flock()" in out or "Flock diagnostics" in out or "Max wait time" in out:
                    logger.warning(f"[.SETVCP] flock: bus={bus}, {out.strip()!r}")
                    return

                if "Timed out" in out or "timeout" in out:
                    logger.warning(f"[.SETVCP] timeout: bus={bus}, {out.strip()!r}")
                else:
                    logger.info(f"[.SETVCP] Set bus={bus} brightness to raw={raw}/{mx}")

                tgt = self._target_pct.get(bus)
                if tgt is not None:
                    self._pending_confirm[bus] = (tgt, _now_ms() + 1000)
                    self._set_retry_budget[bus] = 0

                GLib.timeout_add(360, lambda: (self._fetch_one(bus), False)[1])
            finally:
                self._inflight_set[bus] = False
                self._inflight_since_ms.pop(bus, None)
                GLib.idle_add(lambda: (self._kick_set_loop(bus), False)[1])

        base = (
            "env LC_ALL=C /usr/bin/ddcutil "
            "--enable-cross-instance-locks --sleep-multiplier=1.0 "
            f"setvcp 0x10 {raw} --bus {bus} --noverify 2>&1"
        )
        cmd = self._wrap_timeout("set", base)
        self._run_cmd(cmd, _done, kind=("set", bus))

    def set_percent(self, bus: int, percent: int):
        if bus not in self._available:
            logger.debug(f"[.SET_PERCENT] ignored due to unavailability (bus={bus})")
            return

        p = max(0, min(100, int(percent)))
        self._target_pct[bus] = p
        self._pending_confirm[bus] = (p, _now_ms() + CONFIRM_MS)

        prev = self._current.get(bus)
        self._current[bus] = p
        if prev != p:
            self.emit("external", bus, p)

        # inflight = self._inflight_set.get(bus, False)
        # age = _now_ms() - self._inflight_since_ms.get(bus, _now_ms())
        # logger.debug(f"[.SET_PERCENT] bus={bus}, target={p}%, inflight={inflight}, age={age}ms")
        #
        # if inflight and age > 2500:
        #     logger.warning(f"[.SET_PERCENT] inflight aged out (bus={bus}, age={age}ms) -> clearing & re-kick")
        #     self._inflight_set[bus] = False
        #     self._inflight_since_ms.pop(bus, None)

        if bus not in self._max_cache:
            self._fetch_one(bus)
        else:
            self._kick_set_loop(bus)

    def set_all_percent(self, percent: int, buses: list[int] = None):
        for bus in (buses or self._available):
            self.set_percent(bus, percent)

    def _kick_set_loop(self, bus: int):
        if self._busy:
            logger.debug(f"[.KSL] Busy, deferring set (bus={bus})")
            return
        # honor backoff
        if _now_ms() < self._set_backoff_until_ms.get(bus, 0):
            logger.debug(f"[.KSL] Delaying set (bus={bus})")
            return

        tgt = self._target_pct.get(bus)
        if tgt is None or self._inflight_set.get(bus, False):
            return
        self._pending_confirm[bus] = (tgt, _now_ms() + CONFIRM_MS)

        mx = self._max_cache.get(bus)
        if not mx:
            logger.debug(f"[.KSL] Skipping set due to no mx, will be kicked after read (bus={bus})")
            return

        # if we’ve already retried a couple times on this target, wait for a confirm read
        if self._set_retry_budget.get(bus, 0) > 2:
            logger.debug(f"[.KSL] Retry budget exceeded, waiting for confirm read (bus={bus})")
            GLib.timeout_add(120, lambda b=bus: (self._fetch_one(b, force=True), False)[1])
            return

        raw = int(round((tgt / 100) * mx))
        self._inflight_set[bus] = True
        self._inflight_since_ms[bus] = _now_ms()
        logger.debug(f"[.KSL] bus={bus} tgt={tgt}% -> raw={raw}/{mx}")
        self._set_one_raw(bus, raw, mx)

    # ---------- Queue plumbing ----------

    def _redetect_if_empty(self):
        # Keep trying until we have at least one bus
        if not self._available:
            logger.debug("[.REDETECT] No displays yet, re-running detect")
            self._detect_displays()
            return True  # keep timer
        return False  # stop timer once we have displays

    def _wrap_timeout(self, kind: str, base_cmd: str) -> str:
        """Prefix with coreutils timeout when available, otherwise leave as-is."""
        if self._have_timeout:
            t = f"{CEIL_MS[kind]//1000}.{(CEIL_MS[kind]%1000)//100}s" if isinstance(CEIL_MS[kind], int) else "2s"
            # use -k 1s to SIGKILL if SIGTERM ignored
            return f"/usr/bin/timeout -k 1s {t} {base_cmd}"
        return base_cmd

    def _run_cmd(self, cmd: str, cb: Callable, kind: Tuple[str, int]):
        k, bus = kind
        kept = []
        dropped = 0
        write_inflight = any(self._inflight_set.values())

        for s, _cb, kd in self._queue:
            kk, bb = kd
            if k == "get_force" or kk == "get_force":
                kept.append((s, _cb, kd))
                continue

            # drop only stale same-kind same-bus
            if kk == k and bb == bus:
                dropped += 1
                continue
            # if adding SET for this bus, drop queued GETs for this bus
            if k == "set" and kk == "get" and bb == bus:
                dropped += 1
                continue
            # while any write inflight, drop queued GETs (reduce contention)
            if write_inflight and kk == "get":
                dropped += 1
                continue
            kept.append((s, _cb, kd))

        if dropped:
            logger.debug(f"[.QUEUE] dropped {dropped} stale/redundant before {k} bus={bus}")
        self._queue = kept
        self._queue.append((cmd, cb, kind))
        if not self._busy:
            self._dequeue()

    def _dequeue(self):
        if not self._queue:
            self._busy = False
            self._current_cmd_started_ms = None
            if self._current_timeout_src is not None:
                GLib.source_remove(self._current_timeout_src)
                self._current_timeout_src = None
            return

        self._busy = True
        cmd, cb, kind = self._queue.pop(0)
        k, bus = kind
        self._current_cmd_started_ms = _now_ms()

        # --- INTERNAL PARACHUTE: shell timeout + 800ms ---
        ceiling = CEIL_MS.get(k, 2000)
        if self._current_timeout_src is not None:
            GLib.source_remove(self._current_timeout_src)
            self._current_timeout_src = None
        self._current_timeout_src = GLib.timeout_add(ceiling + 800, lambda: self._force_unstick(kind))
        # --------------------------------------------------

        #logger.debug(f"[.EXEC] {cmd}")

        def _wrapped(proc):
            if self._current_timeout_src is not None:
                GLib.source_remove(self._current_timeout_src)
                self._current_timeout_src = None
            GLib.timeout_add(40, lambda: (self._continue(cb, proc), False)[1])

        exec_shell_command_async(["/bin/sh", "-lc", cmd], _wrapped)

    def _force_unstick(self, kind: Tuple[str, int]):
        k, bus = kind
        logger.error(f"[.EXEC] Ceiling hit for {k} bus={bus}; advancing queue")

        if k == "set":
            self._inflight_set[bus] = False
            self._inflight_since_ms.pop(bus, None)
            # backoff 1200–3000ms depending on how long we waited
            waited = (_now_ms() - (self._current_cmd_started_ms or _now_ms()))
            backoff = max(900, min(2200, waited + 500))
            self._set_backoff_until_ms[bus] = _now_ms() + backoff
            # keep a small retry budget so we don't loop forever
            self._set_retry_budget[bus] = max(1, min(2, self._set_retry_budget.get(bus, 0) + 1))
            # schedule a single confirm read after backoff; re-try only if needed
            tgt = self._target_pct.get(bus)
            if tgt is not None:
                # extend confirm across the backoff we’re about to schedule
                self._pending_confirm[bus] = (tgt, _now_ms() + backoff + 1500)
            GLib.timeout_add(max(500, backoff // 2), lambda b=bus: (self._confirm_after_ceiling(b), False)[1])

        # clear internal ceiling and advance queue (unchanged)
        if self._current_timeout_src is not None:
            GLib.source_remove(self._current_timeout_src)
            self._current_timeout_src = None
        self._busy = False
        self._current_cmd_started_ms = None
        self._dequeue()
        return False

    def _confirm_after_ceiling(self, bus: int):
        # Don’t spam if another write started in the meantime
        if self._inflight_set.get(bus):
            return False
        # Single targeted read; _done() already handles mismatch and kicks set-loop
        self._fetch_one(bus, force=True)
        return False

    def _continue(self, cb: Callable, proc):
        try:
            cb(proc)
        finally:
            self._busy = False
            self._current_cmd_started_ms = None
            self._dequeue()

# ------------------------------

def _coerce_text_from_proc_result(self) -> str:
    if isinstance(self, str):
        return self
    if isinstance(self, (bytes, bytearray)):
        return self.decode(errors="ignore")
    if isinstance(self, tuple) and len(self) == 3:
        _, out, err = self
        out = out.decode(errors="ignore") if isinstance(out, (bytes, bytearray)) else (out or "")
        err = err.decode(errors="ignore") if isinstance(err, (bytes, bytearray)) else (err or "")
        return f"{out}\n{err}"
    out = ""
    err = ""
    try:
        if hasattr(self, "get_stdout"):
            tmp = self.get_stdout()
            out = tmp.decode(errors="ignore") if isinstance(tmp, (bytes, bytearray)) else (tmp or "")
        if hasattr(self, "get_stderr"):
            tmp = self.get_stderr()
            err = tmp.decode(errors="ignore") if isinstance(tmp, (bytes, bytearray)) else (tmp or "")
    except Exception:
        pass
    return f"{out}\n{err}"

def _strip_ansi(self: str) -> str:
    return ANSI_RE.sub("", self)

def _now_ms() -> int:
    return int(time.time() * 1000)
