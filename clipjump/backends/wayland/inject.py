import json
import subprocess
import time

# Terminals are the exception to Ctrl+V (see send_paste): they use Ctrl+V as
# the "quote next character" control code and put paste on Ctrl+Shift+V.
# Matched against the focused window's class, lowercased.
TERMINAL_CLASSES = {
    "alacritty",
    "com.mitchellh.ghostty",
    "contour",
    "foot",
    "footclient",
    "konsole",
    "kitty",
    "org.wezfurlong.wezterm",
    "rio",
    "st",
    "urxvt",
    "wezterm",
    "xterm",
}


def _focused_is_terminal():
    """Best-effort: unknown classes are treated as non-terminals, since
    Ctrl+V is the near-universal paste and terminals are the exception. The
    substring check catches the long tail (gnome-terminal, xfce4-terminal,
    terminator, ...) that isn't worth enumerating."""
    try:
        result = subprocess.run(
            ["hyprctl", "-j", "activewindow"], capture_output=True, timeout=1
        )
        window_class = json.loads(result.stdout).get("class", "").lower()
    except Exception:
        return False
    return window_class in TERMINAL_CLASSES or "term" in window_class


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
        # Which combo actually pastes depends on the focused app, so pick per
        # paste. Measured here, in foot: Ctrl+Shift+V pastes, plain Ctrl+V
        # pastes nothing (terminals use Ctrl+V as "quote next character").
        # GUI apps are the reverse -- Ctrl+Shift+V means "paste special" /
        # "paste as plain text" there, which silently drops an image or file
        # clip since it has no plain-text form. Sending Ctrl+Shift+V
        # everywhere is why text pasted fine (it was only ever tested in a
        # terminal) while images did nothing at all.
        #
        # Injected through Hyprland rather than wtype. wtype drives
        # zwp_virtual_keyboard_v1 with its own generated keymap, which
        # XWayland clients don't honour -- they decode the keycodes against
        # the X keymap instead, so keystrokes arrive as unrelated characters
        # (typing "TYPED" into an XWayland Tk entry produced "1234"), and a
        # paste combo silently does nothing. send_shortcut goes through the
        # compositor and lands correctly on both native Wayland and XWayland
        # windows. Nothing else needs wtype, so this drops the dependency.
        #
        # Our own Hyprland bind owns Ctrl+V globally, but this doesn't
        # re-trigger it: verified by listening on the control socket while
        # dispatching exactly this -- nothing arrives.
        mods = "CTRL SHIFT" if _focused_is_terminal() else "CTRL"
        result = subprocess.run(
            [
                "hyprctl",
                "dispatch",
                f'hl.dsp.send_shortcut({{ mods = "{mods}", key = "V", '
                f'window = "activewindow" }})',
            ],
            capture_output=True,
            text=True,
        )
        # hyprctl reports a bad dispatch in stdout and still exits 0, so
        # check=True wouldn't catch it.
        if result.stdout.strip() != "ok":
            raise RuntimeError(f"paste dispatch failed: {result.stdout.strip()!r}")

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
