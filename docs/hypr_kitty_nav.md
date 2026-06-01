# Hyprland + Kitty + Neovim Navigation Script

> Switch focus between Neovim splits, Kitty splits, and Hyprland windows with a single hotkey.

![hypr_kitty_nav example gif](./hypr_kitty_nav.gif)

**What It Does**

- If the active Kitty pane runs Neovim, it first tries to move focus to a neighboring Neovim split through `pynvim`.
- If Neovim navigation is not available or does not move anywhere, it moves focus to the neighboring Kitty split.
- If Kitty is not active (or Kitty navigation fails), it falls back to Hyprland focus movement.

**Requirements**

- Python 3.12+
- `lsof`
- Hyprland
- Kitty with remote control enabled via a Unix socket
- `pynvim`

The script is an `uv` script and declares `pynvim` in its inline dependencies.

**Kitty Configuration**
Add this to your `kitty.conf`:

```conf
allow_remote_control socket-only
listen-on unix:/tmp/kitty
```

**Usage**
Run directly:

```bash
./hypr_kitty_nav.py left
./hypr_kitty_nav.py right
./hypr_kitty_nav.py up
./hypr_kitty_nav.py down
```

**Example Hyprland Keybinds**

For Hyprland 0.55+ Lua configs:

```lua
-- ~/.config/hypr/hyprland.lua
hl.bind("SUPER + H", hl.dsp.exec_cmd("/path/to/hypr_kitty_nav.py left"))
hl.bind("SUPER + L", hl.dsp.exec_cmd("/path/to/hypr_kitty_nav.py right"))
hl.bind("SUPER + K", hl.dsp.exec_cmd("/path/to/hypr_kitty_nav.py up"))
hl.bind("SUPER + J", hl.dsp.exec_cmd("/path/to/hypr_kitty_nav.py down"))
```

**Notes**

- The script uses `HYPRLAND_INSTANCE_SIGNATURE` and `XDG_RUNTIME_DIR` to locate the Hyprland socket.
- Hyprland focus fallback uses the Hyprland 0.55+ Lua IPC form: `eval hl.dispatch(hl.dsp.focus({ direction = "r" }))`.
- If Kitty has no sockets under `/tmp/kitty*`, the script immediately falls back to Hyprland.
- Neovim detection uses sockets under `$XDG_RUNTIME_DIR/nvim*` and matches them to the active Kitty pane.

**Troubleshooting**

- Ensure Kitty is running with the socket enabled and accessible at `/tmp/kitty*`.
- Ensure `lsof` is installed and available in `PATH`.
- If Neovim split navigation is skipped, ensure Neovim exposes a socket under `$XDG_RUNTIME_DIR/nvim*` and `pynvim` is available.
- To enable debug logs, set `DEBUG = True` in `hypr_kitty_nav.py` and read `/tmp/hypr_kitty_nav.log`.
