#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["hyprpy"]
# ///

# Author: Sadykov Miron <MironSadykov@yandex.ru>
# License: MIT
# 2025

import argparse
import subprocess

from hyprpy import Hyprland
from hyprpy.components.windows import Window

DESCRIPTION = """Run a single instance of an application in Hyperland:
focus it if it's already running,
or launch it otherwise (optionally on a specific workspace)."""


def find_window(looking_window: str, windows: list[Window]) -> Window:
    return next(filter(lambda x: looking_window in x.wm_class, windows))


def focus_window(window: Window, hyprland_instance: Hyprland) -> None:
    cmd = ["focuswindow", f"class:{window.wm_class}"]
    hyprland_instance.dispatch(cmd)


def open_app(args: argparse.Namespace, hyprland_instance: Hyprland) -> None:
    cmd = [
        "exec",
        f"[workspace {args.workspace}]" if args.workspace is not None else "",
        args.app_name,
        *args.rest_args,
    ]
    hyprland_instance.dispatch(cmd)


def get_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
    )
    parser.add_argument(
        "workspace",
        type=int,
        nargs="?",
    )
    parser.add_argument("app_name", type=str, metavar="application")
    parser.add_argument(
        "rest_args",
        metavar="APP ARGS",
        nargs=argparse.REMAINDER,
        help="Additional arguments passed to the application",
    )
    return parser.parse_args()


def send_notification(notificatin_msg: str, app_name: str) -> None:
    subprocess.run(
        (
            "notify-send",
            f"-a {app_name}",
            f"[{app_name}] Failed to launch or focus",
            notificatin_msg,
        ),
        stdout=subprocess.DEVNULL,
    )


def main() -> None:
    args = get_args()
    try:
        hyprland_instance = Hyprland()
        windows = hyprland_instance.get_windows()
        try:
            window = find_window(args.app_name, windows)
            focus_window(window, hyprland_instance)
        except StopIteration:
            open_app(args, hyprland_instance)
    except Exception as e:
        send_notification(str(e), args.app_name)


if __name__ == "__main__":
    main()
