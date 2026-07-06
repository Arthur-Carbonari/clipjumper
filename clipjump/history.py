import subprocess
import threading
import time
from collections import deque, namedtuple

from Xlib import display
from Xlib.ext import xfixes

try:
    from jeepney import DBusAddress, new_method_call
    from jeepney.io.blocking import open_dbus_connection
except ImportError:
    DBusAddress = None

# kind is "text" or "image". For text, data is a str and mime is None.
# For image, data is raw bytes and mime is the target used to fetch it
# (e.g. "image/png").
Clip = namedtuple("Clip", ["kind", "data", "mime"])

_TEXT_TARGETS = {"UTF8_STRING", "STRING", "TEXT", "text/plain", "text/plain;charset=utf-8"}


class ClipboardHistory:
    def __init__(self, maxlen=50):
        self._items = deque(maxlen=maxlen)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if not self._seed_from_klipper():
            current = self._read_clipboard()
            if current:
                self._items.appendleft(current)
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()

    def _seed_from_klipper(self):
        """Import existing history from KDE's Klipper (already running by
        default on Plasma), so we don't start with an empty list every run."""
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

    def _list_targets(self):
        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
                capture_output=True,
                timeout=1,
            )
            return result.stdout.decode("utf-8", errors="replace").split("\n")
        except Exception:
            return []

    def _read_clipboard(self):
        targets = self._list_targets()

        # Check file references first: file managers (Dolphin) advertise
        # text/uri-list for a copied file/dir, but also typically offer a
        # text/plain fallback containing the same literal URI string --
        # without checking this first, that fallback wins and the file
        # copy gets silently flattened into plain URI text.
        if "text/uri-list" in targets:
            try:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", "text/uri-list", "-o"],
                    capture_output=True,
                    timeout=1,
                )
                text = result.stdout.decode("utf-8", errors="replace")
                if not text:
                    return None
                return Clip("files", text, "text/uri-list")
            except Exception:
                return None

        has_text = any(t in _TEXT_TARGETS for t in targets)
        image_mime = next((t for t in targets if t.startswith("image/")), None)

        if image_mime and not has_text:
            try:
                result = subprocess.run(
                    ["xclip", "-selection", "clipboard", "-t", image_mime, "-o"],
                    capture_output=True,
                    timeout=1,
                )
                if not result.stdout:
                    return None
                return Clip("image", result.stdout, image_mime)
            except Exception:
                return None

        try:
            result = subprocess.run(
                ["xclip", "-selection", "clipboard", "-o"],
                capture_output=True,
                timeout=1,
            )
            text = result.stdout.decode("utf-8", errors="replace")
            if not text:
                return None
            return Clip("text", text, None)
        except Exception:
            return None

    def _listen_loop(self):
        """Event-driven instead of polling: XFixes pushes a notification
        only when the CLIPBOARD selection's owner actually changes, so we
        only ever fetch clipboard content in response to a real change --
        no fixed-interval re-fetching (which would be wasteful for large
        clips like images) and no polling delay.

        Blocks directly on next_event() rather than select()-ing on the
        raw socket fd -- python-xlib does its own internal socket
        buffering, which can desync from the OS-level fd readability that
        select() observes (confirmed empirically: select() missed events
        that a direct blocking next_event() picks up immediately)."""
        d = display.Display()
        d.xfixes_query_version()
        root = d.screen().root
        clipboard_atom = d.intern_atom("CLIPBOARD")
        d.xfixes_select_selection_input(root, clipboard_atom, xfixes.XFixesSetSelectionOwnerNotifyMask)

        while not self._stop.is_set():
            d.next_event()
            self._check_clipboard()

    def _check_clipboard(self):
        current = self._read_clipboard()
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
    h = ClipboardHistory()
    h.start()
    print("Watching clipboard. Copy a few things (Ctrl+C) over the next 20s...")
    for _ in range(20):
        time.sleep(1)
        print(f"history len={len(h)} top={h.get(0)!r}")
    h.stop()
