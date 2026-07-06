import threading
import time

from .history import ClipboardHistory
from .inject import Injector
from .keygrab import KeyGrabber
from .tooltip import Tooltip


class ClipjumpDaemon:
    def __init__(self):
        self.history = ClipboardHistory()
        self.tooltip = Tooltip()
        self.injector = Injector()
        self.grabber = KeyGrabber(self._on_key)
        self.navigating = False
        self.index = 0

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
                self.index = min(self.index + 1, len(self.history) - 1)
                self._update_tooltip()
        elif name == "c":
            if self.navigating:
                self.index = max(self.index - 1, 0)
                self._update_tooltip()

    def _start_navigation(self):
        if len(self.history) == 0:
            return
        self.navigating = True
        self.index = 0
        self.grabber.enable_c()
        self._update_tooltip()

    def _update_tooltip(self):
        text = self.history.get(self.index)
        if text is not None:
            self.tooltip.show(text, self.index, len(self.history))

    def _watch_ctrl_release(self):
        while True:
            time.sleep(0.02)
            if self.navigating and not self.grabber.ctrl_is_down():
                self._commit()

    def _commit(self):
        text = self.history.get(self.index)
        self.navigating = False
        self.grabber.disable_c()
        self.tooltip.hide()
        if text is not None:
            # Our own synthetic paste keystroke would otherwise be caught by
            # our own permanent Ctrl+V grab, re-triggering navigation in a loop.
            self.grabber.disable_v()
            try:
                self.injector.commit_paste(text)
            finally:
                self.grabber.enable_v()


if __name__ == "__main__":
    print("clipjump running: Ctrl+C copies normally; hold Ctrl+V to navigate clipboard history (V=older, C=newer), release Ctrl to paste.", flush=True)
    ClipjumpDaemon().start()
