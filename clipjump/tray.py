"""KDE system-tray applet for clipjump.

Runs as its own process (its own systemd user service, see
clipjump-tray.service) so it keeps working -- and can offer a Restart --
even when the clipjump daemon itself has hung. All it does is shell out to
systemctl; it has no connection to the daemon process itself.
"""
import subprocess
import sys
from pathlib import Path

import pystray
from PIL import Image

ICON_PATH = Path(__file__).parent / "assets" / "icon.png"
SERVICE = "clipjump.service"


def _systemctl(*args):
    subprocess.run(["systemctl", "--user", *args, SERVICE], check=False)


def _restart(icon, item):
    _systemctl("restart")


def _stop(icon, item):
    _systemctl("stop")


def _start(icon, item):
    _systemctl("start")


def _quit(icon, item):
    icon.stop()


def main():
    image = Image.open(ICON_PATH)
    menu = pystray.Menu(
        pystray.MenuItem("Restart ClipJump", _restart, default=True),
        pystray.MenuItem("Start ClipJump", _start),
        pystray.MenuItem("Stop ClipJump", _stop),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit Tray Icon", _quit),
    )
    icon = pystray.Icon("clipjump", icon=image, title="ClipJump", menu=menu)
    icon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
