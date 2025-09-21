import contextlib

import gi
from gi.repository import GLib  # type: ignore

from fabric.core.service import Property, Service, Signal
from fabric.utils import bulk_connect

from config.loguru_config import logger
logger = logger.bind(name="MPris", type="Service")

class PlayerctlImportError(ImportError):
    def __init__(self, *args):
        super().__init__("Playerctl is not installed, please install it first", *args)

# Try to import Playerctl, raise custom error if not available
try:
    gi.require_version("Playerctl", "2.0")
    from gi.repository import Playerctl
except ValueError:
    raise PlayerctlImportError


class MprisPlayer(Service):
    """A service to manage a mpris player."""

    @Signal
    def exit(self, value: bool) -> bool: ...

    @Signal
    def changed(self) -> None: ...

    def _emit_changed_async(self):
        GLib.idle_add(lambda: (self.emit("changed"), False))

    def _notify_prop(self, kebab_name: str):
        self._emit_changed_async()

    def __init__(self, player: Playerctl.Player, **kwargs):
        self._signal_connectors = {}
        self._player = player
        super().__init__(**kwargs)

        self._signal_map = {
            "playback-status": "playback_status",
            "loop-status": "loop_status",
            "shuffle": "shuffle",
            "seeked": "position",
            "metadata": None,
        }

        self._signal_connectors["playback-status"] = self._player.connect(
            "playback-status", lambda *a: self._emit_changed_async()
        )
        self._signal_connectors["loop-status"] = self._player.connect(
            "loop-status", lambda *a: self._emit_changed_async()
        )
        self._signal_connectors["shuffle"] = self._player.connect(
            "shuffle", lambda *a: self._emit_changed_async()
        )
        self._signal_connectors["seeked"] = self._player.connect(
            "seeked", lambda *a: self._emit_changed_async()
        )
        self._signal_connectors["metadata"] = self._player.connect(
            "metadata", lambda *a: self._emit_changed_async()
        )

    def on_player_exit(self, player):
        for id in list(self._signal_connectors.values()):
            with contextlib.suppress(Exception):
                self._player.disconnect(id)
        del self._signal_connectors
        GLib.idle_add(lambda: (self.emit("exit", True), False))
        del self._player

    def toggle_shuffle(self):
        if self.can_shuffle:
            # schedule the shuffle toggle in the GLib idle loop
            GLib.idle_add(lambda: (setattr(self, 'shuffle', not self.shuffle), False))

    def play_pause(self):
        if self.can_pause:
            GLib.idle_add(lambda: (self._player.play_pause(), False))

    def next(self):
        if self.can_go_next:
            GLib.idle_add(lambda: (self._player.next(), False))

    def previous(self):
        if self.can_go_previous:
            GLib.idle_add(lambda: (self._player.previous(), False))

    # Properties
    @Property(str, "readable")
    def player_name(self) -> str:
        return self._player.get_property("player-name")

    @Property(int, "read-write")
    def position(self) -> int:
        return self._player.get_property("position")

    @position.setter
    def position(self, new_pos: int):
        self._player.set_position(new_pos)
        self._emit_changed_async()

    @Property(dict, "readable")
    def metadata(self) -> dict:
        return self._player.get_property("metadata") or {}

    @Property(str or None, "readable")
    def arturl(self) -> str | None:
        if "mpris:artUrl" in self.metadata.keys():  # type: ignore  # noqa: SIM118
            return self.metadata["mpris:artUrl"]  # type: ignore
        return None

    @Property(str or None, "readable")
    def length(self) -> str | None:
        if "mpris:length" in self.metadata.keys():  # type: ignore  # noqa: SIM118
            return self.metadata["mpris:length"]  # type: ignore
        return None

    @Property(str, "readable")
    def artist(self) -> str:
        a = self._player.get_artist()
        return ", ".join(a) if isinstance(a, (list, tuple)) else (a or "")

    @Property(str, "readable")
    def album(self) -> str:
        return self._player.get_album() or ""

    @Property(str, "readable")
    def title(self) -> str:
        t = self._player.get_title()
        return t if isinstance(t, str) else ""

    @Property(bool, "read-write", default_value=False)
    def shuffle(self) -> bool:
        return bool(self._player.get_property("shuffle"))

    @shuffle.setter
    def shuffle(self, do_shuffle: bool):
        self._player.set_shuffle(bool(do_shuffle))
        self._emit_changed_async()

    @Property(str, "readable")
    def playback_status(self) -> str:
        return {
            Playerctl.PlaybackStatus.PAUSED: "paused",
            Playerctl.PlaybackStatus.PLAYING: "playing",
            Playerctl.PlaybackStatus.STOPPED: "stopped",
        }.get(self._player.get_property("playback_status"), "unknown")

    @Property(str, "read-write")
    def loop_status(self) -> str:
        return {
            Playerctl.LoopStatus.NONE: "none",
            Playerctl.LoopStatus.TRACK: "track",
            Playerctl.LoopStatus.PLAYLIST: "playlist",
        }.get(self._player.get_property("loop_status"), "unknown")

    @loop_status.setter
    def loop_status(self, status: str):
        ls = {"none": Playerctl.LoopStatus.NONE,
              "track": Playerctl.LoopStatus.TRACK,
              "playlist": Playerctl.LoopStatus.PLAYLIST}.get(status)
        if ls is not None:
            self._player.set_loop_status(ls)
            self._emit_changed_async()

    @Property(bool, "readable", default_value=False)
    def can_go_next(self) -> bool:
        return self._player.get_property("can_go_next")

    @Property(bool, "readable", default_value=False)
    def can_go_previous(self) -> bool:
        return self._player.get_property("can_go_previous")

    @Property(bool, "readable", default_value=False)
    def can_seek(self) -> bool:
        return self._player.get_property("can_seek")

    @Property(bool, "readable", default_value=False)
    def can_pause(self) -> bool:
        return self._player.get_property("can_pause")

    @Property(bool, "readable", default_value=False)
    def can_shuffle(self) -> bool:
        try:
            self._player.set_shuffle(self._player.get_property("shuffle"))
            return True
        except Exception:
            return False

    @Property(bool, "readable", default_value=False)
    def can_loop(self) -> bool:
        try:
            self._player.set_shuffle(self._player.get_property("shuffle"))
            return True
        except Exception:
            return False


class MprisPlayerManager(Service):
    """A service to manage mpris players."""

    @Signal
    def player_appeared(self, player: Playerctl.Player) -> Playerctl.Player: ...

    @Signal
    def player_vanished(self, player_name: str) -> str: ...

    def __init__(self, **kwargs,):
        self._manager = Playerctl.PlayerManager.new()
        bulk_connect(
            self._manager,
            {
                "name-appeared": self.on_name_appeard,
                "name-vanished": self.on_name_vanished,
            },
        )
        self.add_players()
        super().__init__(**kwargs)

    def on_name_appeard(self, manager, player_name: Playerctl.PlayerName):
        logger.info(f"{player_name.name} appeared")
        new_player = Playerctl.Player.new_from_name(player_name)
        manager.manage_player(new_player)
        self.emit("player-appeared", new_player)  # type: ignore

    def on_name_vanished(self, manager, player_name: Playerctl.PlayerName):
        logger.info(f"{player_name.name} vanished")
        self.emit("player-vanished", player_name.name)  # type: ignore

    def add_players(self):
        for player in self._manager.get_property("player-names"):  # type: ignore
            self._manager.manage_player(Playerctl.Player.new_from_name(player))  # type: ignore

    @Property(object, "readable")
    def players(self):
        return self._manager.get_property("players")  # type: ignore
