#!/usr/bin/env python
# Author: Sadykov Miron <MironSadykov@yandex.ru>
# License: MIT
# 2025

import argparse
import json
import subprocess
from typing import Any


DESCRIPTION = """Run a single instance of an application in Hyperland:
focus it if it's already running,
or launch it otherwise (optionally on a specific workspace)."""


def get_running_apps() -> list[dict[str, Any]]:
    p = subprocess.run(
        ("hyprctl", "clients", "-j"),
        capture_output=True,
        check=True,
    )
    return json.loads(p.stdout)


def find_running_app(
    looking_app: str, running_apps: list[dict[str, Any]]
) -> str | None:
    for app in running_apps:
        if app["class"] == looking_app:
            return app["workspace"]["id"]


def focus_window(app_name: str) -> None:
    subprocess.run(
        ("hyprctl", "dispatch", "focuswindow", f"class:{app_name}"),
        stdout=subprocess.DEVNULL,
        check=True,
    )


def open_app(app_name: str, workspace: int | None, rest_args: list[str]) -> None:
    subprocess.run(
        (
            "hyprctl",
            "dispatch",
            "exec",
            f"[workspace {workspace}]" if workspace is not None else "",
            app_name,
            " ".join(rest_args),
        ),
        stdout=subprocess.DEVNULL,
        check=True,
    )


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
        runnung_apps = get_running_apps()
        app_id = find_running_app(args.app_name, runnung_apps)
        if app_id:
            focus_window(args.app_name)
        else:
            open_app(
                args.app_name,
                args.workspace if args.workspace is not None else None,
                args.rest_args,
            )
    except Exception as e:
        send_notification(str(e), args.app_name)


if __name__ == "__main__":
    main()
