# ClipJumper

A Linux clipboard history navigator inspired by
[aviaryan/Clipjump](https://github.com/aviaryan/Clipjump), an AutoHotkey tool
for Windows. AHK isn't available on Linux, so ClipJumper reimplements the
same core gesture — hold Ctrl+V, step through your clipboard history, release
to paste — on Linux, with a native backend for both X11 and Hyprland/Wayland.

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

ClipJumper picks a backend **at runtime** based on `WAYLAND_DISPLAY`
(`clipjump/backends/__init__.py`), so the same codebase and install steps
work on both setups below — nothing to configure by hand beyond the
Hyprland keybindings noted for Wayland.

- **X11** (e.g. KDE Plasma (X11) on Fedora — the original development
  target): uses `XGrabKey` passive key grabs, XTest synthetic input, and
  `XFixes` selection notifications, all via `python-xlib`. Check your
  session with `echo $XDG_SESSION_TYPE` — it must print `x11`. Requires
  `xclip`.
- **Hyprland/Wayland** (e.g. Omarchy): Wayland's security model doesn't let
  a client grab global hotkeys or synthesize input on its own, so this
  backend splits the work with the compositor:
  - The actual Ctrl+V/C/Z/X binds live in Hyprland's own config
    (`~/.config/hypr/bindings.lua`, see below), which forwards key events
    to the running daemon over a local Unix socket.
  - Clipboard read/write/watch uses `wl-clipboard` (`wl-copy`/`wl-paste`)
    instead of `xclip`.
  - Synthetic paste is dispatched through Hyprland itself
    (`hl.dsp.send_shortcut`), and the combo depends on the focused window:
    **Ctrl+Shift+V** into a terminal, **Ctrl+V** into anything else.
    Terminals use Ctrl+V as the "quote next character" control code and put
    paste on Ctrl+Shift+V; GUI apps are the reverse, treating Ctrl+Shift+V
    as "paste special"/"paste as plain text", which silently drops an image
    or file clip. `clipjump/backends/wayland/inject.py` decides from the
    focused window's class.
  - The tooltip (Tk, via XWayland) positions itself using `hyprctl -j
    cursorpos` instead of an X11 pointer query, and needs a `no_focus`
    window rule — Hyprland reports the override-redirect Tk window as
    `acceptsInput: true` and will otherwise hand it the keyboard focus,
    stealing it from whatever you're pasting into. It sets its own WM_CLASS
    (`Clipjump`) so that rule doesn't catch every Tk app on the system.

  Other Wayland compositors aren't supported — the Hyprland config below
  and the `hyprctl` cursor query are Hyprland-specific.
- **Desktop environment**: history seeding on startup talks to KDE's
  Klipper over D-Bus and silently no-ops everywhere else (including
  Hyprland/Omarchy), starting with just the current clipboard content
  instead. This isn't backend-specific — it'd no-op the same way on GNOME/
  X11 too.
- **Python**: 3.9+ (tested on 3.13 and 3.14).
- **System packages required**:
  - Both backends: Tk/Tcl bindings for Python (`python3-tkinter` on
    Fedora, `tk` on Arch/Omarchy — `tkinter` needs the system Tcl/Tk
    shared libs, which pip can't provide).
  - X11 only: `xclip`.
  - Wayland/Hyprland only: `wl-clipboard` (ships by default on Omarchy).
    Paste injection goes through `hyprctl`, so no `wtype` is needed.
  - KDE tray icon only (optional, see below): `python3-gobject` and
    `libappindicator-gtk3` — PyGObject needs its system Tcl/Tk-style shared
    libs the same way `tkinter` does, so it can't come from pip either.
- Autostart setup uses a **systemd user service** (`systemd --user`); on
  Omarchy this is activated via UWSM the same way it is on a typical
  systemd-based X11 desktop.

## Installation

```bash
git clone <this-repo-url> clipjump
cd clipjump
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` is shared across both backends — `python-xlib` and
`jeepney` are pure-Python and harmless to have installed even when unused
(the X11 backend module simply never gets imported on Wayland).

For the optional KDE tray icon (`clipjump/tray.py`, see below), the venv
needs to see the system's PyGObject install (`gi`), which pip can't provide
on its own — create the venv with `--system-site-packages`, or if it
already exists, flip `include-system-site-packages = true` in
`.venv/pyvenv.cfg`. `pystray` itself (in `requirements.txt`) installs
normally via pip either way.

System dependencies (Fedora, X11):

```bash
sudo dnf install xclip python3-tkinter
```

System dependencies (Omarchy/Arch, Hyprland):

```bash
sudo pacman -S tk wl-clipboard
```

(`wl-clipboard` is already installed by default on Omarchy — this is just
for a plain Arch/Hyprland setup that doesn't have it yet.)

### Hyprland keybindings (Wayland only)

Add to `~/.config/hypr/bindings.lua` (adjust `venv_py` to your actual clone
path):

```lua
local navigating = false
local clipjump_dir = "/path/to/clipjump"
local venv_py = clipjump_dir .. "/.venv/bin/python3"

-- Never let the tooltip (a Tk/XWayland override-redirect window) steal
-- keyboard focus from whatever you're actually pasting into. Matches
-- ^Clipjump$, not ^Tk$: the tooltip sets its own WM_CLASS, so this rule
-- doesn't make every other Tk app on the system unfocusable too.
o.window({ class = "^Clipjump$" }, { no_focus = true })

local function notify(key)
  -- `python3 -m clipjump.ctl` resolves the clipjump package via the current
  -- working directory (there's no script path to anchor it in -m mode), and
  -- exec_cmd doesn't run from clipjump_dir on its own -- without the cd the
  -- module silently fails to import and nothing reaches the daemon.
  hl.exec_cmd("cd " .. clipjump_dir .. " && " .. venv_py .. " -m clipjump.ctl " .. key)
end

hl.bind("CTRL + V", function()
  navigating = true
  notify("v")
end)

-- Re-synthesize CTRL+key as a fresh down-then-delayed-up. hl.dsp.pass() was
-- tried first and left the key stuck/repeating in foot -- the same bug
-- Omarchy's own default/hypr/bindings/clipboard.lua works around this way.
-- See https://github.com/hyprwm/Hyprland/discussions/14099.
local function forward_ctrl(key)
  hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = key, state = "down" }))
  hl.timer(function()
    hl.dispatch(hl.dsp.send_key_state({ mods = "CTRL", key = key, state = "up" }))
  end, { timeout = 50, type = "oneshot" })
end

for _, key in ipairs({ "C", "Z", "X" }) do
  hl.bind("CTRL + " .. key, function()
    if navigating then
      notify(key:lower())
    else
      forward_ctrl(key) -- let Ctrl+C/Z/X (copy/undo/cut) through untouched
    end
  end)
end

-- Fires once when either physical Ctrl key is released.
--
-- `transparent` is what makes this work at all, and it is NOT optional.
-- Hyprland's CKeybindManager::shadowKeybinds() marks every bind whose key is
-- currently held as `shadowed` whenever some *other* bind fires, and
-- handleKeybinds() then skips shadowed binds outright. So pressing V (which
-- fires the Ctrl+V bind above while Ctrl is held) shadows this bind, and the
-- shadow isn't lifted until *after* the Ctrl release has been processed --
-- the release silently does nothing and only a second, separate Ctrl tap
-- commits. `shadowed` is its own term in that condition, which is why
-- ignore_mods and non_consuming have no effect on it; `transparent` is the
-- documented opt-out ("cannot be shadowed by other binds").
--
-- non_consuming matters too, for a different reason: without it, matching
-- this bind on the Ctrl *press* would suppress that press, so the focused
-- app would never see Ctrl go down at all.
for _, ctrl_key in ipairs({ "Control_L", "Control_R" }) do
  hl.bind("CONTROL + " .. ctrl_key, function()
    navigating = false
    notify("commit")
  end, { release = true, ignore_mods = true, non_consuming = true, transparent = true })
end
```

Then validate: `hyprctl reload` followed by `hyprctl configerrors`.

Note that a clean `configerrors` does **not** mean your bind options were
understood — Omarchy's Lua wrapper silently ignores unknown option names. To
actually confirm a flag took effect, read it back off the bind object:

```lua
local kb = hl.bind("SUPER + F13", function() end, { transparent = true })
print(tostring(kb.transparent)) -- expect: true
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
Type=simple
# WorkingDirectory is required, not cosmetic: `python3 -m clipjump.main`
# resolves the clipjump package via the current working directory (there's
# no script path to anchor sys.path in -m mode), so without this the module
# fails to import.
WorkingDirectory=/path/to/clipjump
ExecStart=/path/to/clipjump/.venv/bin/python3 -m clipjump.main
Restart=on-failure
RestartSec=2
Environment=XDG_RUNTIME_DIR=%t

[Install]
WantedBy=graphical-session.target
```

On Hyprland this relies on `WAYLAND_DISPLAY`, `HYPRLAND_INSTANCE_SIGNATURE`
and `DISPLAY` being present in the systemd **user manager's** environment —
without `WAYLAND_DISPLAY` the daemon would pick the X11 backend and fail. On
Omarchy, UWSM exports all of them, so a `graphical-session.target` unit gets
them for free. Confirm with:

```bash
systemctl --user show-environment | grep -E 'WAYLAND_DISPLAY|HYPRLAND_INSTANCE'
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

### KDE tray icon (optional)

`clipjump/tray.py` is a small, separate program: a KDE system-tray icon
(via `pystray`'s AppIndicator backend, which Plasma's tray understands
natively) whose right-click menu can Restart/Start/Stop the daemon by
shelling out to `systemctl --user <action> clipjump.service`.

It deliberately runs as its **own** process/service rather than a thread
inside the daemon. If the daemon hangs (the historical failure mode here —
it stays `active (running)` in systemd, never crashes, so nothing
auto-restarts it), a thread sharing its process would very likely hang too:
Python's GIL means the tray's click handler can't run unless whatever's
stuck in the daemon releases the GIL, and this app makes blocking C-level
calls (Xlib, D-Bus) that don't always do so. A separate OS process has no
such dependency on the daemon's state, so the Restart button stays
clickable no matter how badly the daemon is stuck.

Create `~/.config/systemd/user/clipjump-tray.service`:

```ini
[Unit]
Description=ClipJumper KDE tray icon
After=graphical-session.target
PartOf=graphical-session.target

[Service]
ExecStart=/path/to/clipjump/.venv/bin/python3 -m clipjump.tray
WorkingDirectory=/path/to/clipjump
Restart=on-failure
RestartSec=2

[Install]
WantedBy=graphical-session.target
```

Then:

```bash
systemctl --user daemon-reload
systemctl --user enable --now clipjump-tray.service
```

Useful commands:

```bash
systemctl --user status clipjump-tray      # check it's running
systemctl --user restart clipjump-tray     # restart the tray icon itself
journalctl --user -u clipjump-tray -f      # tail logs
```

This is KDE/AppIndicator-specific (it registers with
`org.kde.StatusNotifierWatcher`); it hasn't been adapted for other desktop
environments or for Hyprland/Omarchy.

## Known limitations

- Wayland compositors other than Hyprland aren't supported — the global
  hotkey mechanism depends on Hyprland's Lua config/bind API.
- Picking the paste combo depends on recognising terminals by window class
  (`TERMINAL_CLASSES` in `clipjump/backends/wayland/inject.py`). A terminal
  that isn't in that list — and whose class doesn't contain "term" — gets
  Ctrl+V and so won't paste; add its class to the set.
- Terminal emulators and some other apps may behave inconsistently with
  synthetic paste injection depending on how they implement clipboard
  handling.
- Clipboard-history seeding from existing history is Klipper-specific
  (KDE); other desktop environments start from just the current clipboard
  value. Klipper's history API only returns a text placeholder for images
  (e.g. `▨ 919x303`), not the image bytes, so image clips from past
  sessions aren't recovered on restart — only ones copied since the daemon
  started.

## Project layout

- `clipjump/backends/__init__.py` — picks the X11 or Wayland backend at
  runtime based on `WAYLAND_DISPLAY`
- `clipjump/backends/x11/` — `python-xlib`/XTest/XFixes/`xclip`
  implementation (key grabbing, paste injection, clipboard read/watch,
  cursor position)
- `clipjump/backends/wayland/` — Hyprland/`wl-clipboard`
  implementation of the same pieces, plus the Unix-socket listener that
  Hyprland's keybinds talk to
- `clipjump/ctl.py` — one-shot sender Hyprland's keybinds shell out to
  (`python3 -m clipjump.ctl v|c|z|x|commit`)
- `clipjump/clip.py` — the shared `Clip` type both backends produce
- `clipjump/history.py` — clipboard history bookkeeping (Klipper seeding,
  the MRU deque), delegating actual reads/change-notifications to whichever
  backend is active
- `clipjump/tooltip.py` — cursor-following preview tooltip, delegating the
  cursor-position query to whichever backend is active
- `clipjump/formats.py` — paste-format transforms (Z key)
- `clipjump/main.py` — the daemon's state machine tying it all together
- `clipjump/tray.py` — standalone KDE tray icon (Restart/Start/Stop via
  `systemctl`), run as its own service separate from the daemon
- `clipjump/assets/icon.png` — the tray icon image
