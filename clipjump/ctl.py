"""One-shot sender used by Hyprland's key binds (see
~/.config/hypr/bindings.lua) to reach the running clipjump daemon:

    python3 -m clipjump.ctl v|c|z|x|commit

Fire-and-forget: a UNIX datagram send either lands or fails immediately
(e.g. ECONNREFUSED if the daemon isn't running) -- it never blocks, so a
dead daemon can't hang whatever's calling this (the Hyprland compositor).
"""
import socket
import sys

from .backends.wayland import socket_path


def main():
    if len(sys.argv) != 2:
        print("usage: python3 -m clipjump.ctl <v|c|z|x|commit>", file=sys.stderr)
        return 1
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        sock.sendto(sys.argv[1].encode(), socket_path())
    except OSError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
