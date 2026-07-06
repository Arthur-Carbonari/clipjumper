import threading
import time
from urllib.parse import unquote, urlparse

from .formats import FORMATS
from .history import ClipboardHistory
from .inject import Injector
from .keygrab import KeyGrabber
from .tooltip import Tooltip

# Once X is tapped at all, further X taps cycle these (never back to a plain
# paste for that session) -- matches the original AHK tool's action-mode key.
ACTIONS = ["Cancel", "Delete", "Clear History", "Terminate"]


def _friendly_file_list(uri_list_text):
    paths = []
    for line in uri_list_text.strip().split("\n"):
        line = line.strip("\r\n")
        if not line or line.startswith("#"):
            continue
        paths.append(unquote(urlparse(line).path) or line)
    return "\n".join(paths) if paths else uri_list_text


class ClipjumpDaemon:
    def __init__(self):
        self.history = ClipboardHistory()
        self.tooltip = Tooltip()
        self.injector = Injector()
        self.grabber = KeyGrabber(self._on_key)
        self.navigating = False
        self.index = 0
        self.format_index = 0
        self.action_index = -1  # -1 = no action selected (normal paste)

    def start(self):
        self.history.start()
        threading.Thread(target=self.grabber.run, daemon=True).start()
        threading.Thread(target=self._watch_ctrl_release, daemon=True).start()
        # Tk's mainloop must own the real main thread (see tooltip.Tooltip
        # docstring) -- this call blocks here for the daemon's lifetime.
        self.tooltip.run()

    def _on_key(self, name, pressed):
        if not pressed:
            return
        if name == "v":
            if not self.navigating:
                self._start_navigation()
            else:
                self.index = (self.index + 1) % len(self.history)
                self._update_tooltip()
        elif name == "c":
            if self.navigating:
                self.index = (self.index - 1) % len(self.history)
                self._update_tooltip()
        elif name == "z":
            if self.navigating:
                self.format_index = (self.format_index + 1) % len(FORMATS)
                self._update_tooltip()
        elif name == "x":
            if self.navigating:
                self.action_index = (self.action_index + 1) % len(ACTIONS)
                self._update_tooltip()

    def _start_navigation(self):
        if len(self.history) == 0:
            return
        self.navigating = True
        self.index = 0
        self.format_index = 0
        self.action_index = -1
        self.grabber.enable_nav()
        self._update_tooltip()

    def _update_tooltip(self):
        clip = self.history.get(self.index)
        if clip is None:
            return
        status_parts = []
        if self.action_index >= 0:
            status_parts.append(f"Action: {ACTIONS[self.action_index]}")
        if clip.kind == "text":
            fmt_name, _ = FORMATS[self.format_index]
            if fmt_name != "None":
                status_parts.append(f"Format: {fmt_name}")
        status = "  ".join(status_parts) if status_parts else None
        total = len(self.history)
        if clip.kind == "image":
            self.tooltip.show_image(clip.data, clip.mime, self.index, total, status=status)
        elif clip.kind == "files":
            self.tooltip.show_text(_friendly_file_list(clip.data), self.index, total, status=status)
        else:
            self.tooltip.show_text(clip.data, self.index, total, status=status)

    def _watch_ctrl_release(self):
        while True:
            time.sleep(0.02)
            if self.navigating and not self.grabber.ctrl_is_down():
                self._commit()

    def _commit(self):
        clip = self.history.get(self.index)
        index = self.index
        action = ACTIONS[self.action_index] if self.action_index >= 0 else None
        _, fmt_fn = FORMATS[self.format_index]

        self.navigating = False
        self.grabber.disable_nav()
        self.tooltip.hide()

        if action == "Cancel":
            return
        if action == "Delete":
            self.history.delete(index)
            return
        if action == "Clear History":
            self.history.clear()
            return
        if action == "Terminate":
            self.tooltip.quit()
            return

        if clip is None:
            return
        # Our own synthetic paste keystroke would otherwise be caught by our
        # own permanent Ctrl+V grab, re-triggering navigation in a loop.
        self.grabber.disable_v()
        try:
            if clip.kind == "image":
                self.injector.commit_paste_image(clip.data, clip.mime)
            elif clip.kind == "files":
                self.injector.commit_paste_files(clip.data)
            else:
                pasted = fmt_fn(clip.data)
                self.injector.commit_paste(pasted, restore_text=clip.data)
        finally:
            self.grabber.enable_v()


if __name__ == "__main__":
    print(
        "clipjump running: Ctrl+C copies normally; hold Ctrl+V to navigate clipboard "
        "history (V=older, C=newer), Z cycles paste format, X cycles action mode "
        "(Cancel/Delete/Clear History/Terminate), release Ctrl to commit.",
        flush=True,
    )
    ClipjumpDaemon().start()
