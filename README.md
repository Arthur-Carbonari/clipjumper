# ClipJumper

A Linux/X11 clipboard history navigator inspired by
[aviaryan/Clipjump](https://github.com/aviaryan/Clipjump), an AutoHotkey tool
for Windows. AHK isn't available on Linux, so ClipJumper reimplements the
same core gesture — hold Ctrl+V, step through your clipboard history, release
to paste — using X11 instead.

## How it works

- **Ctrl+C** copies normally, untouched — a background monitor just watches
  the clipboard and builds a history list from it.
- **Ctrl+V** is intercepted: holding Ctrl and tapping **V**/**C** shows a
  tooltip near your cursor and steps through your clipboard history (V =
  older, C = newer, wrapping around at both ends). Releasing Ctrl pastes
  whichever clip is showing.
- While navigating, **Z** cycles a paste-format transform (None, UPPERCASE,
  lowercase, Sentence case, Trim Whitespace, Numbered List) applied to the
  pasted text.
- While navigating, **X** cycles an action mode: **Cancel** (paste nothing),
  **Delete** (remove the selected clip from history), **Clear History**
  (wipe the whole list), **Terminate** (quit ClipJumper). Whichever mode is
  showing when you release Ctrl is what happens.

Clipboard history seeds from KDE's Klipper on startup (if present), and
re-copying or re-pasting an item always promotes it back to the top.

## Compatibility

- **Display server: X11 only.** This relies on X11-specific mechanisms
  (`XGrabKey` passive key grabs, XTest synthetic input, `XQueryPointer` for
  modifier state) that don't exist under Wayland's security model. Check
  your session with `echo $XDG_SESSION_TYPE` — it must print `x11`, not
  `wayland`. On Fedora/KDE Plasma you can pick "Plasma (X11)" at the login
  screen if your default session is Wayland.
- **Desktop environment**: developed and tested on **KDE Plasma (X11)** on
  Fedora 42. Should work on any X11 window manager/DE for the core
  navigation gesture; the clipboard-history seeding on startup is
  KDE-specific (talks to Klipper over D-Bus) and silently no-ops elsewhere,
  starting with just the current clipboard content instead.
- **Python**: 3.9+ (tested on 3.13).
- **System packages required**: `xclip`, and Tk/Tcl bindings for Python
  (`python3-tkinter` / `python3-tk`, depending on your distro).
- Autostart setup uses a **systemd user service** (`systemd --user`).

## Installation

```bash
git clone <this-repo-url> clipjump
cd clipjump
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

System dependencies (Fedora):

```bash
sudo dnf install xclip python3-tkinter
```

## Running

```bash
source .venv/bin/activate
python3 -m clipjump.main
```

## Autostart (systemd user service)

Create `~/.config/systemd/user/clipjump.service`:

```ini
[Unit]
Description=ClipJumper clipboard history navigator
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart=/path/to/clipjump/.venv/bin/python3 -m clipjump.main
WorkingDirectory=/path/to/clipjump
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now clipjump.service
```

Useful commands:

```bash
systemctl --user status clipjump      # check it's running
systemctl --user restart clipjump     # restart after code changes
systemctl --user stop clipjump        # stop it
systemctl --user disable clipjump     # turn off autostart
journalctl --user -u clipjump -f      # tail logs
```

Note: using the **Terminate** action (X key) exits the process cleanly
(exit code 0), so systemd won't auto-restart it in that case — start it
again manually with `systemctl --user start clipjump`.

## Known limitations

- X11 only, as above — no Wayland support.
- Terminal emulators and some other apps may behave inconsistently with
  synthetic paste injection depending on how they implement clipboard
  handling.
- Clipboard-history seeding from existing history is Klipper-specific
  (KDE); other desktop environments start from just the current clipboard
  value.

## Project layout

- `clipjump/history.py` — clipboard history monitor (polls `xclip`, seeds
  from Klipper via D-Bus if available)
- `clipjump/keygrab.py` — X11 global key grabbing for Ctrl+V navigation
- `clipjump/tooltip.py` — cursor-following preview tooltip
- `clipjump/inject.py` — sets the clipboard and synthesizes paste/copy
- `clipjump/formats.py` — paste-format transforms (Z key)
- `clipjump/main.py` — the daemon's state machine tying it all together
