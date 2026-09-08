import json
import subprocess


def cursor_pos():
    result = subprocess.run(["hyprctl", "-j", "cursorpos"], capture_output=True, timeout=1)
    pos = json.loads(result.stdout)
    return pos["x"], pos["y"]
