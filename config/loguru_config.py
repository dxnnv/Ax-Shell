from __future__ import annotations
import sys
import time
import logging
import re
from collections import deque
from typing import TYPE_CHECKING, Deque, Tuple, Dict, Any
from loguru import logger

try:
    from gi.repository import GLib  # type: ignore
except Exception:
    GLib = None  # type: ignore

if TYPE_CHECKING:
    from loguru._logger import Record  # type: ignore
else:
    Record = Any

# ---------------- Formatting ----------------
FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<magenta>({extra[display_group]})</magenta> "
    "<cyan>{extra[display_name]}</cyan> | "
    "<level>{message}</level>"
)

GROUP_MAP = {
    "widgets": "Widget",
    "services": "Service",
    "fabric": "Fabric",
    "config": "Config",
    "logging": "Logging",
    "__main__": "Main",
}

# ---------------- Helpers ----------------
_TAGS_RE = re.compile(r"^(?:\[(?!\.)(?P<tag>[^]]+)])+\s*")
# Captures one or more [Tag] prefixes at the start of message

def _extract_tags_and_clean_message(record: Dict[str, Any]) -> None:
    """
    Pull leading [Tag][Sub]... from the start of message into extra['tag'].
    Mutates record['message'] to drop those prefixes.
    """
    msg = record["message"]
    tags: Deque[str] = deque()
    while True:
        m = _TAGS_RE.match(msg)
        if not m:
            break
        # Collect ALL tags in the matched prefix
        # (e.g. "[Audio][Microphone]" -> "Audio/Microphone")
        prefix = m.group(0)
        for piece in re.findall(r"\[([^]]+)]", prefix):
            tags.append(piece)
        msg = msg[len(prefix):]
    if tags:
        record["extra"]["tag"] = "/".join(tags)
        record["message"] = msg

# Simple de-dup limiter (same name/function/line/message within N ms)
_LAST_SEEN: Dict[Tuple[str, str, int, str], float] = {}
def _should_emit(record: Dict[str, Any], window_ms: int = 250) -> bool:
    key = (record["name"], record["function"], record["line"], record["message"])
    now = time.monotonic() * 1000
    last = _LAST_SEEN.get(key)
    _LAST_SEEN[key] = now
    return last is None or (now - last) > window_ms

def _patch(record: "Record") -> None:
    _maybe_demote_info_to_debug(record)

    extra = record["extra"]

    bound_name = extra.get("name")
    extra.setdefault("tag", "-")

    # Hoist [Tag]s like [Audio][Microphone] into extra['tag']
    _extract_tags_and_clean_message(record)

    # Derive defaults from module path
    parts = record["name"].split(".")
    root = parts[0] if parts else record["name"]
    group = GROUP_MAP.get(root, root.capitalize())
    component = (parts[1] if len(parts) > 1 else parts[-1]).replace("_", " ").title()

    # If this is the top-level script and you bound a tag (e.g., "Main"), use it as the group label
    if root == "__main__" and extra["tag"] != "-":
        group = extra["tag"]

    # Prefer bound name (Ax-Shell) → tag (Audio/Microphone) → component (Wayland/Brightness/Core)
    if bound_name and bound_name != record["name"]:
        display_name = bound_name
    elif extra["tag"] != "-":
        display_name = extra["tag"]
    else:
        display_name = component

    extra["display_group"] = group
    extra["display_name"]  = display_name

# A sink wrapper that drops near-duplicate spam
def _rate_limited_sink(msg):
    rec = msg.record
    if _should_emit(rec, window_ms=250):
        sys.stdout.write(str(msg))
        sys.stdout.flush()

# ---------------- Filter ----------------
_FABRIC_DOWNGRADE_RULES = [
    (re.compile(r"^fabric\.audio\."), re.compile(r"^Adding stream \d+ with name ")),
    (re.compile(r"^fabric\.hyprland\.widgets"), re.compile(r"^Activated window ")),
]

def _is_noisy_fabric(record) -> bool:
    msg = record["message"]
    low = msg.lower()

    if (
        "adding stream " in low
        or "changing default speaker to" in low
        or "changing default microphone to" in low
        or "Activated window " in msg
    ):
        return True

    return False

def _info_sink_filter(record) -> bool:
    return not _is_noisy_fabric(record)

def _debug_only_fabric_filter(record) -> bool:
    return _is_noisy_fabric(record)

def _maybe_demote_info_to_debug(record) -> None:
    try:
        if record["level"].no == logger.level("INFO").no and _is_noisy_fabric(record):
            dbg = logger.level("DEBUG").no
            record["level"].name = "DEBUG"
            record["level"].no = dbg
            # Optional: mark for a quick sanity check in your format while testing
            record["extra"]["demoted"] = True
    except Exception:
        pass

# ---------------- Public API ----------------

class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        level_name = record.levelname or logging.getLevelName(record.levelno)
        try:
            _ = logger.level(level_name)
            loguru_level = level_name
        except Exception:
            try:
                alias = {
                    5: "TRACE", 10: "DEBUG", 20: "INFO", 25: "SUCCESS",
                    30: "WARNING", 40: "ERROR", 50: "CRITICAL"
                }.get(record.levelno, f"LVL{record.levelno}")
                if alias.startswith("LVL"):
                    logger.level(alias, no=record.levelno)
                loguru_level = alias
            except Exception:
                loguru_level = record.levelno

        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.bind(src_logger=record.name).opt(depth=depth, exception=record.exc_info).log(
            loguru_level, record.getMessage()
        )

def setup_logging(level: str = "INFO", capture_stdlib: bool = True) -> None:
    logger.configure(patcher=_patch)
    logger.remove()

    level_name = level.upper()

    logger.add(
        _rate_limited_sink,
        level=level_name,
        filter=_info_sink_filter,
        format=FMT,
        colorize=True,
        backtrace=True,
        diagnose=False,
        enqueue=False,
    )

    if level_name == "TRACE":
        logger.add(
            _rate_limited_sink,
            level="TRACE",
            filter=_debug_only_fabric_filter,
            format=FMT,
            colorize=True,
            backtrace=True,
            diagnose=False,
            enqueue=False,
        )
    else:
        for noisy in ("urllib3", "httpx", "requests"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    if capture_stdlib:
        logging.root.handlers = [InterceptHandler()]
        logging.root.setLevel(logging.NOTSET)

    _capture_glib()

def _glib_level_to_loguru(level: int) -> str:
    if GLib is None:
        return "UNKNOWN"

    if level & GLib.LogLevelFlags.LEVEL_ERROR: name = "ERROR"
    elif level & GLib.LogLevelFlags.LEVEL_CRITICAL: name = "CRITICAL"
    elif level & GLib.LogLevelFlags.LEVEL_WARNING: name = "WARNING"
    elif level & GLib.LogLevelFlags.LEVEL_MESSAGE: name = "INFO"
    elif level & GLib.LogLevelFlags.LEVEL_INFO: name = "INFO"
    elif level & GLib.LogLevelFlags.LEVEL_DEBUG: name = "DEBUG"
    elif level & GLib.LogLevelFlags.LEVEL_MASK: name = "TRACE"
    else: name = "WARNING"

    return name

def _capture_glib() -> None:
    if GLib is None:
        return

    def glib_handler(domain: str, level: int, message: str) -> None:
        dom = domain or "GLib"
        name = _glib_level_to_loguru(level)
        logger.bind(tag="Logging", module=dom).log(name, f"[{dom}] {message.strip()}")

    try:
        GLib.log_set_handler(None, GLib.LogLevelFlags.LEVEL_MASK, glib_handler)
        GLib.log_set_handler("Gtk", GLib.LogLevelFlags.LEVEL_MASK, glib_handler)
        GLib.log_set_handler("Gdk", GLib.LogLevelFlags.LEVEL_MASK, glib_handler)
    except Exception:
        pass