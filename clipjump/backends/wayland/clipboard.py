import subprocess

from ...clip import Clip, TEXT_TARGETS


def _list_targets():
    try:
        result = subprocess.run(["wl-paste", "--list-types"], capture_output=True, timeout=1)
        return result.stdout.decode("utf-8", errors="replace").split("\n")
    except Exception:
        return []


def read_clip():
    targets = _list_targets()

    # Check file references first: file managers advertise text/uri-list
    # for a copied file/dir, but also typically offer a text/plain
    # fallback containing the same literal URI string -- without checking
    # this first, that fallback wins and the file copy gets silently
    # flattened into plain URI text.
    if "text/uri-list" in targets:
        try:
            result = subprocess.run(
                ["wl-paste", "--no-newline", "--type", "text/uri-list"],
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
                ["wl-paste", "--type", image_mime], capture_output=True, timeout=1
            )
            if not result.stdout:
                return None
            return Clip("image", result.stdout, image_mime)
        except Exception:
            return None

    try:
        result = subprocess.run(["wl-paste", "--no-newline"], capture_output=True, timeout=1)
        text = result.stdout.decode("utf-8", errors="replace")
        if not text:
            return None
        return Clip("text", text, None)
    except Exception:
        return None


def listen(stop_event, on_change):
    """`wl-paste --watch <cmd>` spawns <cmd> each time the CLIPBOARD
    selection changes; the child inherits wl-paste's own stdout, so piping
    it and treating each line as a notification (confirmed empirically)
    gives an event-driven signal equivalent to the X11 backend's XFixes
    selection-owner subscription -- no polling needed here either."""
    proc = subprocess.Popen(
        ["wl-paste", "--watch", "echo", "changed"],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        while not stop_event.is_set():
            line = proc.stdout.readline()
            if not line:
                break
            on_change()
    finally:
        proc.terminate()
