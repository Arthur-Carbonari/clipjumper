import subprocess
import time


class Injector:
    def set_clipboard(self, text):
        subprocess.run(["wl-copy"], input=text.encode(), check=True)

    def set_clipboard_image(self, data, mime):
        subprocess.run(["wl-copy", "--type", mime], input=data, check=True)

    def set_clipboard_files(self, uri_list_text):
        subprocess.run(
            ["wl-copy", "--type", "text/uri-list"], input=uri_list_text.encode(), check=True
        )

    def send_paste(self):
        # Ctrl+Shift+V, not Ctrl+V: our own Hyprland bind owns Ctrl+V
        # globally (see ~/.config/hypr/bindings.lua), so synthesizing that
        # combo would re-trigger navigation instead of reaching the
        # focused app. Ctrl+Shift+V is the standard "paste from CLIPBOARD"
        # shortcut in Wayland terminals (confirmed: foot binds Shift+Insert
        # to the PRIMARY selection instead, not CLIPBOARD, which is why
        # that was tried first and silently pasted nothing) and is widely
        # supported by GTK/Qt apps too.
        subprocess.run(
            ["wtype", "-M", "ctrl", "-M", "shift", "-k", "v", "-m", "shift", "-m", "ctrl"],
            check=True,
        )

    def commit_paste(self, text, restore_text=None):
        self.set_clipboard(text)
        time.sleep(0.03)
        self.send_paste()
        if restore_text is not None and restore_text != text:
            # Give the target app time to finish reading `text` before we
            # swap the clipboard back, so a Z-formatted paste doesn't leave
            # the formatted variant as the new MRU item.
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
