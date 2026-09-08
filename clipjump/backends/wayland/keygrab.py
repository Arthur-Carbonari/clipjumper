import os
import socket

from . import socket_path


class HyprlandKeyGrabber:
    """Global hotkey capture on Hyprland: a Wayland client can't grab keys
    itself, so the actual Ctrl+V/C/Z/X binds live in the compositor's own
    config (~/.config/hypr/bindings.lua). Those binds shell out to
    `clipjump.ctl`, which forwards each key over this UNIX datagram
    socket -- datagram sends never block the Hyprland Lua thread even if
    nothing is listening here (unlike a FIFO), so a dead/not-yet-started
    daemon can't hang the compositor.

    Ctrl+C/Z/X pass through to the focused app untouched while not
    navigating -- that gating happens on the Hyprland/Lua side, so
    enable_v/disable_v/enable_nav/disable_nav are no-ops here, kept only
    for interface parity with the X11 KeyGrabber that main.py drives.
    """

    def __init__(self, on_event):
        self.on_event = on_event
        self._ctrl_down = False
        self._path = socket_path()
        try:
            os.unlink(self._path)
        except FileNotFoundError:
            pass
        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._sock.bind(self._path)

    def disable_v(self):
        pass

    def enable_v(self):
        pass

    def enable_nav(self):
        pass

    def disable_nav(self):
        pass

    def ctrl_is_down(self):
        return self._ctrl_down

    def run(self):
        try:
            while True:
                data = self._sock.recv(64)
                word = data.decode("utf-8", errors="replace").strip()
                if word in ("v", "c", "z", "x"):
                    self._ctrl_down = True
                    self.on_event(word, True)
                elif word == "commit":
                    self._ctrl_down = False
        finally:
            try:
                os.unlink(self._path)
            except FileNotFoundError:
                pass
