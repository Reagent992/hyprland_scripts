#!/usr/bin/env python3
"""Kitty launch.

Author: Sadykov Miron <MironSadykov@yandex.ru>
License: MIT
2026

# What is this?

This script for Hyprland and Kitty lets you keep one main Kitty instance and
bind (in Hyprland) shortcuts that run terminal applications as new tabs in the
main Kitty instance.

- It communicates with Hyprland and Kitty through sockets.
- The `-d` argument is substituted with `--cwd` because `kitty` uses `-d`,
  but `kitten @ launch` uses `--cwd`.
- Launches kitty as a UWSM service.

## Requirements:

- UWSM managed Hyprland.

## Usage example:

```hyprlang
# hyprland.conf
$reuse_terminal = # here is path to this script
bind = $Mod, T, exec, [workspace 2] $reuse_terminal                    # Open new kitty tab or os-window
bind = $Mod, Y, exec, [workspace 2] $reuse_terminal yazi               # Open yazi in kitty tab or os-window
bind = $Mod, N, exec, [workspace 2] $reuse_terminal -d ~/dev/foo nvim  # Open nvim in selected directory
```

- First instance of kitty should be launched through this script.
- Don't forget to make this script executable.

--------------------------------------------------------------------------------
## Dev notes:

- `--instance-group` seems to be needed only to separate two kitty instances running with the --single-instance flag.
- Executing `hyprctl clients` through a socket returns a response without JSON formatting.
- Can't get pid of kitty out of `kitty @ ls`.
--------------------------------------------------------------------------------
"""

import json
import logging
import os
import socket
import subprocess
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from typing import Final, NotRequired, TypedDict, cast

# Constants
logger: Final = logging.getLogger(__name__)
MAIN_KITTY_CLASS: Final = "kitty_main1"
KITTY_SOCKET_DIR: Final = Path("/tmp")
KITTY_SOCKET_NAME: Final = "kitty_main"
KITTY_SOCKET_PATH: Final = KITTY_SOCKET_DIR / KITTY_SOCKET_NAME
XDG_RUNTIME_DIR: Final = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
HYPRLAND_INSTANCE: Final = os.environ.get("HYPRLAND_INSTANCE_SIGNATURE", "")
HYPRLAND_SOCKET: Final = Path(XDG_RUNTIME_DIR) / "hypr" / HYPRLAND_INSTANCE / ".socket.sock"
LOG_PATH: Final = gettempdir() + "/kitty_launch.log"
SOCKET_TIMEOUT_SEC: Final = 2
DEBUG: Final = False  # Write logs to file. `tail -f /tmp/kitty_launch.log` to read it
if DEBUG:
    logging.basicConfig(
        format="%(asctime)s:%(levelname)s:line %(lineno)d:%(message)s",
        level=logging.DEBUG,
        filename=LOG_PATH,
    )


@dataclass(frozen=True, slots=True)
class HyprClient:
    """Hyprland window."""

    class_: str
    title: str
    pid: str


class KittyWindow(TypedDict):
    """Single kitty window (pane) inside a tab."""

    id: int


class KittyTab(TypedDict):
    """Kitty tab inside an OS window."""

    id: int
    windows: list[KittyWindow]
    is_active: NotRequired[bool]


class KittyOsWindow(TypedDict):
    """Top-level OS window in kitty @ ls output."""

    id: int
    tabs: list[KittyTab]


def _get_hyprland_clients(hyprland_socket: Path) -> str | None:
    """Query the Hyprland socket for clients (open windows).

    - The "clients" command does not return JSON.
    """
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.settimeout(SOCKET_TIMEOUT_SEC)
            sock.connect(str(hyprland_socket))
            logger.debug("Connected to Hyprland socket")
            sock.sendall(b"clients")
            data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            return data.decode()
    except OSError:
        logger.exception("Error occurred while trying to connect to Hyprland socket.")


def _parse_clients(raw_text: str) -> list[HyprClient]:
    """Parse a raw Hyprland socket response into `HyprClient` objects."""
    clients = list[HyprClient]()
    window_blocks = raw_text.split("\n\n")

    for block in window_blocks:
        lines = block.splitlines()
        if not lines:
            continue
        data = dict[str, str]()
        for line in lines[1:]:
            line_stripped = line.strip()
            if not line_stripped:
                continue
            key, _, value = line_stripped.partition(":")
            if key and value:
                key, value = key.strip(), value.strip()
                if key in ("pid", "class", "title"):
                    data[key] = value
        missing = {"class", "title", "pid"} - data.keys()
        if missing:
            logger.debug("Skipping malformed client block, missing: %s", missing)
            continue
        clients.append(HyprClient(class_=data["class"], title=data["title"], pid=data["pid"]))
    logger.debug("Found these hyprland windows: %s", "\n".join(str(client) for client in clients))
    return clients


def _get_main_kitty_window_pid_by_class(windows: list[HyprClient]) -> str | None:
    """Return the PID of the first window matching the configured Kitty OS window class."""
    for window in windows:
        if window.class_ == MAIN_KITTY_CLASS:
            logger.info("Main kitty window PID found: %s", window.pid)
            return window.pid
    return None


def get_pid_of_main_kitty_window() -> str | None:
    """Query Hyprland for open windows and return the main Kitty window PID."""
    clients = _get_hyprland_clients(HYPRLAND_SOCKET)
    if clients:
        clients = _parse_clients(clients)
        return _get_main_kitty_window_pid_by_class(clients)
    return None


def select_socket_for_main_kitty(sockets: list[Path]) -> Path | None:
    """Choose the correct socket from candidates.

    - If you have more than one Kitty instance, Kitty may add PID to the socket
      name, e.g. "kitty-1389".
    """
    pid = get_pid_of_main_kitty_window()
    if not pid:
        logger.info("Can't find main kitty window among opened kitty windows.")
        return None

    logger.info("Got pid of active kitty")
    for socket_ in sockets:
        match = (pid in socket_.name or socket_.name == KITTY_SOCKET_NAME) and socket_.is_socket()
        logger.info("socket: %s, pid: %s, match: %s", socket, pid, match)
        if match:
            logger.info("Found socket matching pid: %s", socket)
            return socket_
    logger.info("No suitable socket found among sockets.")
    return None


def select_kitty_socket() -> Path | None:
    """Select the Kitty socket to target.

    - Even if there is only one socket, it might not be from the main window.
    - Expects sockets named like "kitty*".
    """
    sockets = list(Path(KITTY_SOCKET_DIR).glob(f"{KITTY_SOCKET_NAME}*"))
    logger.info("Found sockets: %s", sockets)
    if not sockets:
        return None
    return select_socket_for_main_kitty(sockets)


def _run_kitty_command(
    socket_path: Path, args: list[str], *, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    command = [
        "kitty",
        "@",
        "--to",
        f"unix:{socket_path.resolve()!s}",
        *args,
    ]
    if capture:
        return subprocess.run(command, capture_output=True, text=True)
    return subprocess.run(command, text=True)


def focus_kitty_tab(socket_path: Path, window_id: str) -> bool:
    """Focus a tab containing the specified kitty window id."""
    result = _run_kitty_command(
        socket_path,
        ["focus-tab", "--match", f"window_id:{window_id}"],
        capture=True,
    )
    if result.returncode == 0:
        return True
    logger.error("Kitty focus-tab failed with code: %s", result.returncode)
    if result.stdout:
        logger.error("Kitty focus-tab stdout: %s", result.stdout.strip())
    if result.stderr:
        logger.error("Kitty focus-tab stderr: %s", result.stderr.strip())
    return False


def _get_kitty_remote_tree(socket_path: Path) -> list[KittyOsWindow] | None:
    """Get information about open Kitty windows from `kitty @ ls`."""
    result = _run_kitty_command(socket_path, ["ls"], capture=True)
    if result.returncode != 0:
        logger.error("Kitty remote ls failed with code: %s", result.returncode)
        return None
    try:
        return cast("list[KittyOsWindow]", json.loads(result.stdout))
    except ValueError:
        logger.exception("Failed to parse kitty @ ls output")
    return None


def _parse_kitty_ls(kitty_ls: list[KittyOsWindow]) -> str:
    """Select a kitty window id from the oldest OS window in `kitty @ ls` output.

    - We take the OS window with the smallest id. We expect this to be the first running window.
    - Inside it, we take the kitty window id from the active tab, or the first available one.
    """
    oldest_os_window = min(kitty_ls, key=lambda window: int(window["id"]))
    tab = next(
        (tab for tab in oldest_os_window["tabs"] if tab.get("is_active")),
        oldest_os_window["tabs"][0],
    )
    return str(tab["windows"][0]["id"])


def kitty_launch_through_socket(socket_path: Path, args: Iterable[str], launch_type: str = "tab") -> str | None:
    """Launch Kitty through a remote-control socket.

    - Can't use `os.execvp` here because we need to focus on the window.
        [workspace 2] from hyprland won't work here, so we need to explicitly execute
        focuswindow after.
    - `--match` is used because one kitty instance can have two windows, but we need
        to always open in the main one. Selects the oldest window.
    """
    logger.info("Launch Kitty through socket: %s", socket_path)
    command = ["launch", f"--type={launch_type}"]
    window_id: str | None = None
    if launch_type == "tab":
        result = _get_kitty_remote_tree(socket_path)
        if result:
            window_id = _parse_kitty_ls(result)
            logger.info("Found kitty window_id: %s, in kitty @ ls", window_id)
            command.extend([f"--match=window_id:{window_id}"])
    logger.debug(
        "Exec args: %s",
        " ".join(("kitty", "@", "--to", str(socket_path), *command, *args)),
    )
    result = _run_kitty_command(socket_path, [*command, *args], capture=True)
    if result.returncode != 0:
        logger.error("Kitty remote launch failed with code: %s", result.returncode)
        if result.stdout:
            logger.error("Kitty launch stdout: %s", result.stdout.strip())
        if result.stderr:
            logger.error("Kitty launch stderr: %s", result.stderr.strip())
        return window_id

    new_window_id = result.stdout.strip()
    if new_window_id:
        logger.info("Kitty launch returned window_id: %s", new_window_id)
        return new_window_id
    return window_id


def kitty_launch(args: Iterable[str]) -> None:
    """Launch the first Kitty instance.

    - `--single-instance` allows opening a new OS window in the same instance via `kitty --single-instance`.
        Without it, `kitty --single-instance` will open a new instance.
    - Launched as `uwsm app -t service --`, which creates a new PID, so we can't set the PID in the socket name here.
    """
    uwsm_run_as_service = ["app", "-t", "service", "--"]
    kitty = [
        "kitty",
        "--single-instance",
        "--class",
        MAIN_KITTY_CLASS,
        "--listen-on",
        "unix:" + str(KITTY_SOCKET_PATH.resolve()),
        "--override",
        "allow_remote_control=socket-only",
        *args,
    ]
    logger.info("Launching first Kitty instance: %s", kitty)
    os.execvp("/usr/bin/uwsm", ["uwsm", *uwsm_run_as_service, *kitty])


def substitute_args(args: list[str]) -> list[str]:
    """For `kitten @ launch`, replace the first `-d` argument with `--cwd`."""
    if "-d" in args:
        d_index = args.index("-d")
        if d_index + 1 < len(args):
            args[d_index] = "--cwd"
            logger.info("Replaced -d with --cwd in arguments")
    return args


def _main() -> None:
    args = sys.argv[1:]
    logger.info("Passed arguments: %s", args)
    if not HYPRLAND_INSTANCE:
        logger.error("HYPRLAND_INSTANCE_SIGNATURE is not set; cannot resolve Hyprland socket.")
        sys.exit(1)
    logger.info("HYPRLAND_SOCKET: %s", HYPRLAND_SOCKET)
    kitty_socket = select_kitty_socket()
    if kitty_socket:
        args = substitute_args(args)
        window_id = kitty_launch_through_socket(kitty_socket, args)
        if window_id:
            _ = focus_kitty_tab(kitty_socket, window_id)
    else:
        kitty_launch(args)


def main() -> None:
    """Launch."""
    try:
        _main()
    except Exception:
        logger.exception("Error: ")
    logger.debug("#" * 60)


if __name__ == "__main__":
    main()
