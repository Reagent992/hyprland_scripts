#!/usr/bin/env python3
# Author: Sadykov Miron <MironSadykov@yandex.ru>
# License: MIT
# 2026
"""
# What is it?
This Python script lets you switch between Kitty and Hyprland windows with one hotkey.

For example:
You have two OS windows open. The first is Kitty with two windows split vertically.
Your cursor is in the left Kitty window. The first press of `SUPER+L` jumps to the right
Kitty window; the second press jumps to the OS window on the right.

- Based on top of https://github.com/joe-butler-23/hypr-kitty-nav

## Requirements
- python 3.12+
- lsof
- Hyprland
- Kitty with `allow_remote_control=socket-only` and `listen-on=unix:/tmp/kitty`

##
"""

import logging
import os
import re
import socket
import subprocess
import sys
from itertools import batched
from pathlib import Path
from tempfile import gettempdir
from typing import Final

# Constants
logger: Final = logging.getLogger(__name__)
KITTY_SOCKETS_PATH: Final = Path("/tmp").glob("kitty*")
LOG_PATH: Final = gettempdir() + "/hypr_kitty_nav.log"
XDG_RUNTIME_DIR: Final = os.environ.get("XDG_RUNTIME_DIR", "/tmp")
HYPRLAND_INSTANCE: Final = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
HYPRLAND_SOCKET: Final = (
    Path(XDG_RUNTIME_DIR) / "hypr" / HYPRLAND_INSTANCE / ".socket.sock"
)
SOCKET_TIMEOUT_SEC: Final = 2
DIRECTION_MAP: Final = {
    "left": ("l", "left"),
    "right": ("r", "right"),
    "up": ("u", "top"),
    "down": ("d", "bottom"),
}
DEBUG = False  # Write logs to file. `tail -f /tmp/hypr_kitty_nav.log` to read it
if DEBUG:
    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:line %(lineno)d:%(message)s",
        level=logging.DEBUG,
        filename=LOG_PATH,
    )


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
    logger.error("Cannot find proper Kitty socket.")


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
        logger.exception("Error while getting an active kitty pid.")


def hypr_dispatch(socket_path: Path, direction: str) -> None:
    """Focus through Hyprland dispatch."""
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(SOCKET_TIMEOUT_SEC)
            sock.connect(str(socket_path))
            cmd = f"dispatch movefocus {direction}"
            sock.sendall(cmd.encode())
    except (OSError, socket.error):
        logger.exception("Error while focusing window through Hyprland socket.")


def main():
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
            logger.info("Execute kitty focus-window through socket: %s", kitty_socket)
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
            logger.error("Sending to Kitty socket failed")

    hypr_dispatch(HYPRLAND_SOCKET, move_dir)


if __name__ == "__main__":
    main()
