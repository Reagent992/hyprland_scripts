#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["pynvim"]
# ///
# Author: Sadykov Miron <MironSadykov@yandex.ru>
# License: MIT
# 2026
"""
# What is it?
This Python script lets you switch between Kitty and Hyprland windows with a single hotkey.

For example:
You have two OS-level windows open. The first is Kitty with two windows split vertically.
Your cursor is in the left Kitty window. The first press of `SUPER+L` jumps to the right
Kitty window; the second press jumps to the OS-level window on the right.

- Inspired by https://github.com/joe-butler-23/hypr-kitty-nav

## Requirements
- Python 3.12+
- lsof
- Hyprland
- Kitty with `allow_remote_control=socket-only` and `listen-on=unix:/tmp/kitty`

#FIXME:
- After `:restart` win+hjkl don't work within nvim
"""

import json
import logging
import os
import re
import socket
import subprocess
import sys
from itertools import batched
from pathlib import Path
from tempfile import gettempdir
from typing import Final, NotRequired, TypedDict, cast

import pynvim

# Constants
logger: Final = logging.getLogger(__name__)
KITTY_SOCKETS_PATH: Final = Path("/tmp").glob("kitty*")
LOG_PATH: Final = gettempdir() + "/hypr_kitty_nav.log"
XDG_RUNTIME_DIR: Final = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
HYPRLAND_INSTANCE: Final = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
HYPRLAND_SOCKET: Final = (
    Path(XDG_RUNTIME_DIR) / "hypr" / HYPRLAND_INSTANCE / ".socket.sock"
)
NVIM_SOCKETS: Final = list(Path(XDG_RUNTIME_DIR).glob("nvim*"))
SOCKET_TIMEOUT_SEC: Final = 2
DIRECTION_MAP: Final = {
    "left": ("l", "left"),
    "right": ("r", "right"),
    "up": ("u", "top"),
    "down": ("d", "bottom"),
}
NVIM_DIRECTION_MAP: Final = {
    "left": "h",
    "right": "l",
    "up": "k",
    "down": "j",
}
DEBUG = False  # Write logs to a file. `tail -f /tmp/hypr_kitty_nav.log` to read it
if DEBUG:
    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:line %(lineno)d:%(message)s",
        level=logging.DEBUG,
        filename=LOG_PATH,
    )


class KittyWindow(TypedDict):
    """Single kitty window (pane) inside a tab."""

    id: int
    is_active: NotRequired[bool]
    foreground_processes: NotRequired[list["KittyForegroundProcess"]]


class KittyTab(TypedDict):
    """Kitty tab inside an OS window."""

    id: int
    windows: list[KittyWindow]
    is_active: NotRequired[bool]


class KittyOsWindow(TypedDict):
    """Top-level OS window in kitty @ ls output."""

    id: int
    tabs: list[KittyTab]
    is_active: NotRequired[bool]
    is_focused: NotRequired[bool]


class KittyForegroundProcess(TypedDict):
    """Foreground process in a kitty window."""

    cmdline: list[str]
    cwd: str
    pid: int


def get_kitty_socket(active_kitty_pid: str) -> Path | None:
    """Get the socket of the active Kitty instance by its PID."""
    sockets = list(KITTY_SOCKETS_PATH)
    if not sockets:
        logger.error("No Kitty sockets found in /tmp (pattern: kitty*)")
        return None

    cmd = ["lsof", "-Fpn", "--", *sockets]
    result = subprocess.run(cmd, capture_output=True, text=True)

    for raw_pid, raw_socket_path in batched(result.stdout.splitlines(), 2):
        pid = raw_pid.strip().removeprefix("p")
        socket_path = raw_socket_path.removeprefix("n").removesuffix(" type=STREAM")
        if active_kitty_pid == pid:
            logger.info("Found socket path: %s", socket_path)
            return Path(socket_path)
    logger.error("Cannot find a matching Kitty socket.")


def get_active_kitty_pid(hyprland_socket_path: Path) -> str | None:
    """Check whether Kitty is the active window and return its PID."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(SOCKET_TIMEOUT_SEC)
            sock.connect(str(hyprland_socket_path.absolute()))
            sock.sendall(b"activewindow")
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            data = data.decode()
            if "class: kitty" in data:
                logger.debug("Kitty is the active window")
                group_name = "pid"
                regex = rf"pid: (?P<{group_name}>\d+)"
                match = re.search(regex, data)
                logger.debug("Match: %s", match)
                if match:
                    return match.group(group_name)
    except (OSError, socket.error):
        logger.exception("Error while getting the active Kitty PID.")


def _run_kitty_command(
    socket_path: Path, args: list[str], *, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    """Run a kitty remote-control command via the given socket."""
    command = [
        "kitty",
        "@",
        "--to",
        f"unix:{str(socket_path.resolve())}",
        *args,
    ]
    if capture:
        return subprocess.run(command, capture_output=True, text=True)
    return subprocess.run(command, text=True)


def _get_kitty_remote_tree(socket_path: Path) -> list[KittyOsWindow] | None:
    """Get information about open Kitty windows from `kitty @ ls`."""
    result = _run_kitty_command(socket_path, ["ls"], capture=True)
    if result.returncode != 0:
        logger.error("Kitty remote ls failed with code: %s", result.returncode)
        return None
    try:
        tree = cast(list[KittyOsWindow], json.loads(result.stdout))
        return tree
    except ValueError:
        logger.exception("Failed to parse kitty @ ls output")
    return None


def _select_active_os_window(kitty_ls: list[KittyOsWindow]) -> KittyOsWindow:
    """Pick the focused/active OS window from kitty @ ls output."""
    for window in kitty_ls:
        if window.get("is_focused"):
            return window
    for window in kitty_ls:
        if window.get("is_active"):
            return window
    return kitty_ls[0]


def _select_active_tab(os_window: KittyOsWindow) -> KittyTab:
    """Pick the active tab inside the selected OS window."""
    for tab in os_window["tabs"]:
        if tab.get("is_active"):
            return tab
    return os_window["tabs"][0]


def _select_active_window(tab: KittyTab) -> KittyWindow:
    """Pick the active window (pane) inside the selected tab."""
    for window in tab["windows"]:
        if window.get("is_active"):
            return window
    return tab["windows"][0]


def _find_nvim_pid_in_window(window: KittyWindow) -> int | None:
    """Find nvim pid in foreground_processes for the given kitty window."""
    for proc in window.get("foreground_processes", []):
        cmdline = proc.get("cmdline", [])
        if not cmdline:
            continue
        cmd = cmdline[0]
        if "nvim" in cmd:
            return int(proc["pid"])
    return None


def _get_child_pids(pid: int) -> list[int]:
    """Return direct child pids for a pid via /proc/<pid>/task/<pid>/children."""
    children_path = Path("/proc") / str(pid) / "task" / str(pid) / "children"
    try:
        raw = children_path.read_text(encoding="utf-8").strip()
    except OSError:
        return []
    if not raw:
        return []
    try:
        return [int(p) for p in raw.split()]
    except ValueError:
        return []


def select_active_nvim_socket(
    kitty_ls: list[KittyOsWindow], nvim_sockets: list[Path]
) -> Path | None:
    """Select active nvim socket in the focused kitty window.

    Strategy:
    - Identify active kitty OS window -> tab -> pane.
    - Extract foreground nvim pid from that pane.
    - Read child pids for foreground pid via /proc.
    - For each nvim socket, attach and match by child pid.
    """
    os_window = _select_active_os_window(kitty_ls)
    tab = _select_active_tab(os_window)
    window = _select_active_window(tab)
    nvim_pid = _find_nvim_pid_in_window(window)
    if not nvim_pid:
        logger.info("No nvim found in active kitty window.")
        return None
    logger.debug("Active kitty pane id: %s", window.get("id"))
    logger.debug("Foreground processes: %s", window.get("foreground_processes"))
    logger.debug("Foreground nvim pid: %s", nvim_pid)
    logger.debug("Candidate nvim sockets: %s", [str(p) for p in nvim_sockets])
    child_pids = _get_child_pids(nvim_pid)
    logger.debug("Child pids for foreground nvim pid: %s", child_pids)
    if not child_pids:
        logger.info("No child pids found for foreground nvim pid: %s", nvim_pid)
        return None

    for sock_path in nvim_sockets:
        if not sock_path.is_socket():
            logger.debug("Skip non-socket path: %s", sock_path)
            continue
        try:
            nvim = pynvim.attach("socket", path=str(sock_path))
            logger.debug(nvim)
        except Exception:
            logger.exception("Failed to attach to nvim socket: %s", sock_path)
            continue
        try:
            remote_pid = int(nvim.eval("getpid()"))
            logger.debug(
                "Socket %s -> remote pid %s, child_pids %s",
                sock_path,
                remote_pid,
                child_pids,
            )
            if remote_pid in child_pids:
                logger.info(
                    "Matched nvim socket by child pid (fg pid %s, remote pid %s)",
                    nvim_pid,
                    remote_pid,
                )
                return sock_path
        except Exception:
            logger.exception("Failed to query nvim pid for socket: %s", sock_path)
        finally:
            try:
                nvim.close()
            except Exception:
                logger.exception("Failed to close nvim socket: %s", sock_path)
    logger.info("No matching nvim socket found for pid: %s", nvim_pid)
    return None


def try_nvim_move(nvim_socket: Path, direction: str) -> bool:
    """Try to move within nvim splits in the given direction.

    Returns True if the window id changes after the move.
    """
    nvim_dir = NVIM_DIRECTION_MAP[direction]
    try:
        nvim = pynvim.attach("socket", path=str(nvim_socket))
    except Exception:
        logger.exception("Failed to attach to nvim socket: %s", nvim_socket)
        return False

    try:
        win_before = int(nvim.eval("win_getid()"))
        nvim.command(f"wincmd {nvim_dir}")
        win_after = int(nvim.eval("win_getid()"))
        if win_after != win_before:
            logger.info("Nvim move succeeded: %s", direction)
            return True
        logger.info("Nvim move had no effect: %s", direction)
        return False
    except Exception:
        logger.exception("Failed to execute nvim move: %s", direction)
        return False
    finally:
        try:
            nvim.close()
        except Exception:
            logger.exception("Failed to close nvim socket: %s", nvim_socket)


def hypr_dispatch(socket_path: Path, direction: str) -> None:
    """Focus through Hyprland dispatch."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(SOCKET_TIMEOUT_SEC)
            sock.connect(str(socket_path))
            cmd = f'eval hl.dispatch(hl.dsp.focus({{ direction = "{direction}" }}))'
            logging.debug("Send focus cmd to hyprland socket: %s", cmd)
            sock.sendall(cmd.encode())
            response = sock.recv(4096).decode(errors="replace")
            logging.debug("Hyprland socket response: %s", response)
    except (OSError, socket.error):
        logger.exception("Error while focusing a window through the Hyprland socket.")


def main():
    """Entry point for directional navigation across nvim/kitty/hyprland."""
    if len(sys.argv) < 2:
        print("Usage: hypr_kitty_nav <left|right|up|down>", file=sys.stderr)
        sys.exit(1)
    arg = sys.argv[1]
    logger.info("hypr_kitty_nav launched with arg: %s", arg)
    if arg not in DIRECTION_MAP:
        sys.exit(2)

    move_dir, kitty_dir = DIRECTION_MAP[arg]

    assert HYPRLAND_SOCKET.exists()
    logger.debug("Hyprland socket found: %s", HYPRLAND_SOCKET)

    if active_kitty_pid := get_active_kitty_pid(HYPRLAND_SOCKET):
        kitty_socket = get_kitty_socket(active_kitty_pid)
        if kitty_socket:
            kitty_ls = _get_kitty_remote_tree(kitty_socket)
            if kitty_ls:
                nvim_socket = select_active_nvim_socket(kitty_ls, NVIM_SOCKETS)
                if nvim_socket and try_nvim_move(nvim_socket, arg):
                    return
            logger.info("Execute kitty focus-window via socket: %s", kitty_socket)
            result = subprocess.run(
                [
                    "kitty",
                    "@",
                    "--to",
                    f"unix:{str(kitty_socket.absolute())}",
                    "focus-window",
                    "--match",
                    f"neighbor:{kitty_dir}",
                ],
            )
            if result.returncode == 0:
                return
            logger.error("Sending to the Kitty socket failed")

    hypr_dispatch(HYPRLAND_SOCKET, move_dir)


if __name__ == "__main__":
    main()
