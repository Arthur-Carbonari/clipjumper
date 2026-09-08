import subprocess

from Xlib import display
from Xlib.ext import xfixes

from ...clip import Clip, TEXT_TARGETS


def _list_targets():
    try:
        result = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
            capture_output=True,
            timeout=1,
        )
        return result.stdout.decode("utf-8", errors="replace").split("\n")
    except Exception:
        return []


def read_clip():
    targets = _list_targets()

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

    has_text = any(t in TEXT_TARGETS for t in targets)
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


def listen(stop_event, on_change):
    """Event-driven instead of polling: XFixes pushes a notification only
    when the CLIPBOARD selection's owner actually changes, so we only ever
    fetch clipboard content in response to a real change -- no fixed-
    interval re-fetching (which would be wasteful for large clips like
    images) and no polling delay.

    Blocks directly on next_event() rather than select()-ing on the raw
    socket fd -- python-xlib does its own internal socket buffering, which
    can desync from the OS-level fd readability that select() observes
    (confirmed empirically: select() missed events that a direct blocking
    next_event() picks up immediately)."""
    d = display.Display()
    d.xfixes_query_version()
    root = d.screen().root
    clipboard_atom = d.intern_atom("CLIPBOARD")
    d.xfixes_select_selection_input(root, clipboard_atom, xfixes.XFixesSetSelectionOwnerNotifyMask)

    while not stop_event.is_set():
        d.next_event()
        on_change()
