import subprocess
import time

from Xlib import X, Xatom, XK, display, error
from Xlib.ext import xtest


class Injector:
    def __init__(self):
        self.display = display.Display()
        self.root = self.display.screen().root
        self.active_window_atom = self.display.intern_atom("_NET_ACTIVE_WINDOW")
        self.kc_ctrl_l = self.display.keysym_to_keycode(XK.string_to_keysym("Control_L"))
        self.kc_shift_l = self.display.keysym_to_keycode(XK.string_to_keysym("Shift_L"))
        self.kc_v = self.display.keysym_to_keycode(XK.string_to_keysym("v"))

    def _focused_is_ghostty(self):
        try:
            active = self.root.get_full_property(self.active_window_atom, Xatom.WINDOW)
            if active is None or not len(active.value) or not active.value[0]:
                return False
            window = self.display.create_resource_object("window", int(active.value[0]))
            return any(
                name.lower() in {"ghostty", "com.mitchellh.ghostty"}
                for name in window.get_wm_class() or ()
            )
        except error.BadWindow:
            # The active window can close between the two X11 requests.
            return False

    def set_clipboard(self, text):
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)

    def set_clipboard_image(self, data, mime):
        subprocess.run(["xclip", "-selection", "clipboard", "-t", mime], input=data, check=True)

    def set_clipboard_files(self, uri_list_text):
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "text/uri-list"],
            input=uri_list_text.encode(),
            check=True,
        )

    def send_paste(self, *, text=False):
        modifiers = [self.kc_ctrl_l]
        if text and self._focused_is_ghostty():
            # Ghostty's paste action sends clipboard text to its PTY.
            modifiers.append(self.kc_shift_l)
        for keycode in modifiers:
            xtest.fake_input(self.display, X.KeyPress, keycode)
        xtest.fake_input(self.display, X.KeyPress, self.kc_v)
        xtest.fake_input(self.display, X.KeyRelease, self.kc_v)
        for keycode in reversed(modifiers):
            xtest.fake_input(self.display, X.KeyRelease, keycode)
        self.display.sync()

    def commit_paste(self, text, restore_text=None):
        self.set_clipboard(text)
        time.sleep(0.03)
        self.send_paste(text=True)
        if restore_text is not None and restore_text != text:
            # Give the target app time to finish its SelectionRequest for
            # `text` before we swap the clipboard back, so a Z-formatted
            # paste doesn't leave the formatted variant as the new MRU item.
            time.sleep(0.05)
            self.set_clipboard(restore_text)

    def commit_paste_image(self, data, mime):
        self.set_clipboard_image(data, mime)
        time.sleep(0.03)
        self.send_paste()

    def commit_paste_files(self, uri_list_text):
        self.set_clipboard_files(uri_list_text)
        time.sleep(0.03)
        self.send_paste()


if __name__ == "__main__":
    import threading
    import tkinter as tk

    result = {}

    def gui():
        root = tk.Tk()
        root.title("clipjump inject test")
        root.geometry("300x80+100+100")
        entry = tk.Entry(root, font=("monospace", 12))
        entry.pack(fill="x", padx=10, pady=20)

        def after_focus():
            root.focus_force()
            entry.focus_set()
            root.update_idletasks()
            root.update()

            inj = Injector()
            inj.commit_paste("clipjump-inject-test-ok")
            root.after(300, check)

        def check():
            result["value"] = entry.get()
            root.destroy()

        root.after(400, after_focus)
        root.mainloop()

    t = threading.Thread(target=gui)
    t.start()
    t.join(timeout=5)
    print("Entry contained:", repr(result.get("value")))
    assert result.get("value") == "clipjump-inject-test-ok", "PASTE INJECTION FAILED"
    print("PASTE INJECTION OK")
