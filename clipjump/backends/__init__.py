import os


def detect():
    """Pick the display-server backend at runtime.

    WAYLAND_DISPLAY is the standard signal a Wayland compositor sets for
    its clients; its presence is what we key off of rather than
    XDG_SESSION_TYPE, since XWayland keeps DISPLAY set even in a pure
    Wayland session (Hyprland included) and would otherwise look X11-ish.
    """
    return "wayland" if os.environ.get("WAYLAND_DISPLAY") else "x11"
