import threading
from collections import deque

try:
    from jeepney import DBusAddress, new_method_call
    from jeepney.io.blocking import open_dbus_connection
except ImportError:
    DBusAddress = None

from .clip import Clip


class ClipboardHistory:
    def __init__(self, clipboard_backend, maxlen=50):
        self._backend = clipboard_backend
        self._items = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not self._seed_from_klipper():
            current = self._backend.read_clip()
            if current:
                self._items.appendleft(current)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _seed_from_klipper(self):
        """Import existing history from KDE's Klipper (already running by
        default on Plasma), so we don't start with an empty list every run.
        No-ops (returns False) on any other desktop, including Omarchy/
        Hyprland, since there's no Klipper to talk to there."""
        if DBusAddress is None:
            return False
        try:
            conn = open_dbus_connection(bus="SESSION")
            try:
                klipper = DBusAddress(
                    "/klipper", bus_name="org.kde.klipper", interface="org.kde.klipper.klipper"
                )
                msg = new_method_call(klipper, "getClipboardHistoryMenu")
                reply = conn.send_and_get_reply(msg, timeout=2)
                items = reply.body[0]
            finally:
                conn.close()
        except Exception:
            return False
        if not items:
            return False
        with self._lock:
            self._items.clear()
            for item in items[: self._items.maxlen]:  # already newest-first
                self._items.append(Clip("text", item, None))
        return True

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2)

    def _listen_loop(self):
        self._backend.listen(self._stop, self._check_clipboard)

    def _check_clipboard(self):
        current = self._backend.read_clip()
        if not current:
            return
        with self._lock:
            if self._items and self._items[0] == current:
                return
            try:
                self._items.remove(current)
            except ValueError:
                pass
            self._items.appendleft(current)

    def get(self, index):
        with self._lock:
            if 0 <= index < len(self._items):
                return self._items[index]
            return None

    def delete(self, index):
        with self._lock:
            if 0 <= index < len(self._items):
                del self._items[index]

    def clear(self):
        with self._lock:
            self._items.clear()

    def __len__(self):
        with self._lock:
            return len(self._items)


if __name__ == "__main__":
    import time

    from . import backends

    if backends.detect() == "wayland":
        from .backends.wayland import clipboard
    else:
        from .backends.x11 import clipboard

    h = ClipboardHistory(clipboard)
    h.start()
    print("Watching clipboard. Copy a few things (Ctrl+C) over the next 20s...")
    for _ in range(20):
        time.sleep(1)
        print(f"history len={len(h)} top={h.get(0)!r}")
    h.stop()
