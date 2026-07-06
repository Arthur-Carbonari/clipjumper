import subprocess
import time

from Xlib import X, XK, display
from Xlib.ext import xtest


class Injector:
    def __init__(self):
        self.display = display.Display()
        self.kc_ctrl_l = self.display.keysym_to_keycode(XK.string_to_keysym("Control_L"))
        self.kc_v = self.display.keysym_to_keycode(XK.string_to_keysym("v"))
        self.kc_c = self.display.keysym_to_keycode(XK.string_to_keysym("c"))

    def set_clipboard(self, text):
        subprocess.run(["xclip", "-selection", "clipboard"], input=text.encode(), check=True)

    def set_clipboard_image(self, data, mime):
        subprocess.run(["xclip", "-selection", "clipboard", "-t", mime], input=data, check=True)

    def _tap_combo(self, keycode):
        xtest.fake_input(self.display, X.KeyPress, self.kc_ctrl_l)
        xtest.fake_input(self.display, X.KeyPress, keycode)
        xtest.fake_input(self.display, X.KeyRelease, keycode)
        xtest.fake_input(self.display, X.KeyRelease, self.kc_ctrl_l)
        self.display.sync()

    def send_paste(self):
        self._tap_combo(self.kc_v)

    def send_copy(self):
        self._tap_combo(self.kc_c)

    def commit_paste(self, text, restore_text=None):
        self.set_clipboard(text)
        time.sleep(0.03)
        self.send_paste()
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
