import sys
from Xlib import X, XK, display


class KeyGrabber:
    """Grabs Ctrl+V always, and Ctrl+C/Z/X only while dynamically enabled
    (navigation keys: C/V step through history, Z cycles paste format,
    X cycles the action mode).

    IMPORTANT: we never grab the bare Control_L/R keycode. Per the X11
    protocol, a passive XGrabKey activates a *full keyboard grab* for as
    long as the grabbed key is physically held -- grabbing bare Ctrl was
    tried and confirmed (empirically) to break every other Ctrl shortcut
    system-wide for the duration Ctrl was held, not just Ctrl+C/V. Only
    grabbing the letter keys (v always, c/z/x only during navigation)
    keeps the full-keyboard-grab side effect scoped to the literal instant
    that key is held -- which is exactly the gesture we mean to hijack.

    "Ctrl released" (to commit the paste) is detected separately, by
    polling query_pointer()'s modifier mask -- a normal, non-grabbing
    query any client can make -- rather than by grabbing Ctrl itself.
    """

    LOCK_VARIANTS = [0, X.LockMask, X.Mod2Mask, X.LockMask | X.Mod2Mask]
    NAV_KEY_NAMES = ["c", "z", "x"]

    def __init__(self, on_event):
        self.on_event = on_event
        self.display = display.Display()
        self.root = self.display.screen().root
        self._errors = []
        self.display.set_error_handler(lambda err, request=None: self._errors.append(err))

        self.kc_v = self.display.keysym_to_keycode(XK.string_to_keysym("v"))
        self._nav_keycodes = {
            name: self.display.keysym_to_keycode(XK.string_to_keysym(name))
            for name in self.NAV_KEY_NAMES
        }
        self._keycode_to_name = {code: name for name, code in self._nav_keycodes.items()}
        self._keycode_to_name[self.kc_v] = "v"

        self._nav_enabled = False
        self._grab_key(self.kc_v)

    def _grab_key(self, keycode):
        for lv in self.LOCK_VARIANTS:
            self.root.grab_key(keycode, X.ControlMask | lv, True, X.GrabModeAsync, X.GrabModeAsync)
        self.display.sync()
        if self._errors:
            print(f"X errors during grab: {self._errors}", file=sys.stderr, flush=True)
            self._errors.clear()

    def _ungrab_key(self, keycode):
        for lv in self.LOCK_VARIANTS:
            self.root.ungrab_key(keycode, X.ControlMask | lv)
        self.display.sync()

    def disable_v(self):
        self._ungrab_key(self.kc_v)

    def enable_v(self):
        self._grab_key(self.kc_v)

    def enable_nav(self):
        if not self._nav_enabled:
            for code in self._nav_keycodes.values():
                self._grab_key(code)
            self._nav_enabled = True

    def disable_nav(self):
        if self._nav_enabled:
            for code in self._nav_keycodes.values():
                self._ungrab_key(code)
            self._nav_enabled = False

    def ctrl_is_down(self):
        pointer = self.root.query_pointer()
        return bool(pointer.mask & X.ControlMask)

    def pending_event_count(self):
        return self.display.pending_events()

    def next_event(self):
        return self.display.next_event()

    def run(self):
        try:
            while True:
                event = self.display.next_event()
                if event.type not in (X.KeyPress, X.KeyRelease):
                    continue
                name = self._keycode_to_name.get(event.detail)
                if name is not None:
                    self.on_event(name, event.type == X.KeyPress)
        finally:
            self.disable_nav()
            self._ungrab_key(self.kc_v)


if __name__ == "__main__":
    import threading
    import time

    grabber = KeyGrabber(lambda name, pressed: None)
    navigating = False

    def log(name, pressed):
        global navigating
        print(f"{name} {'DOWN' if pressed else 'UP'}", flush=True)
        if name == "v" and pressed and not navigating:
            navigating = True
            grabber.enable_nav()
            print("-> navigation START (c/z/x enabled)", flush=True)

    grabber.on_event = log

    def watch_ctrl_release():
        global navigating
        while True:
            time.sleep(0.03)
            if navigating and not grabber.ctrl_is_down():
                navigating = False
                grabber.disable_nav()
                print("-> navigation END (ctrl released, c/z/x disabled)", flush=True)

    threading.Thread(target=watch_ctrl_release, daemon=True).start()
    print("Grabbing Ctrl+V always; Ctrl+C/Z/X only while navigating. Try Ctrl+V (hold, tap v/c/z/x), then release. Also try unrelated Ctrl shortcuts (Ctrl+A, Ctrl+S etc) to confirm they still work.", flush=True)
    grabber.run()
