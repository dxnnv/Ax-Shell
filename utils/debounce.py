from gi.repository import GLib

class DebouncedSetter:
    def __init__(self, delay_ms: int, do_set):
        """
        delay_ms: idle time before we actually write
        do_set:   function(percent:int) that performs the write action (e.g., brightness.set_percent)
        """
        self.delay_ms = delay_ms
        self._src = None
        self._pending = None
        self._do_set = do_set

    def _cancel(self):
        if self._src is not None:
            GLib.source_remove(self._src)
            self._src = None

    def push(self, value: int):
        """Schedule a write action for the latest value, restarting the timer."""
        self._pending = int(max(0, min(100, value)))
        self._cancel()
        self._src = GLib.timeout_add(self.delay_ms, self._fire)

    def flush_now(self):
        """Immediately perform the latest pending write action (if any)."""
        self._cancel()
        return self._fire()

    def _fire(self):
        if self._pending is not None:
            v = self._pending
            self._pending = None
            self._src = None
            self._do_set(v)
        return False
