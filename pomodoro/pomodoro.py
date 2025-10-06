#!/usr/bin/env python3

import argparse
import json
import logging
import os
import pickle
import subprocess
import tempfile
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Constants
POMODORO = 25 * 60  # 25 minutes in seconds
SHORT_BREAK = 5 * 60  # 5 minutes in seconds
LONG_BREAK = 15 * 60  # 15 minutes in seconds
DATA_FILE = Path(tempfile.gettempdir()) / "pomodoro_state.pkl"
DEBUG = False

if os.environ.get("DEBUG") in ("TRUE", "True", "true", "1"):
    DEBUG = True
    logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


class TimerState(Enum):
    IDLE = "idle"
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    PAUSED = "paused"


@dataclass
class Pomodoro:
    time_left: int = 0
    pomodoros: int = 0
    last_update: int = int(time.time())
    previous_status: TimerState = TimerState.IDLE
    _status: TimerState = TimerState.IDLE

    @property
    def status(self) -> TimerState:
        return self._status

    @status.setter
    def status(self, value: TimerState) -> None:
        self.previous_status = self._status
        self._status = value

    def next_break(self) -> None:
        self.pomodoros += 1
        if self.pomodoros % 4 == 0:
            self.status = TimerState.LONG_BREAK
            self.time_left = LONG_BREAK
        else:
            self.status = TimerState.SHORT_BREAK
            self.time_left = SHORT_BREAK

    def update_status(self) -> None:
        if self.status in (
            TimerState.WORK,
            TimerState.SHORT_BREAK,
            TimerState.LONG_BREAK,
        ):
            elapsed = int(time.time()) - self.last_update
            original_time_left = self.time_left
            self.time_left = max(0, self.time_left - elapsed)
            if self.time_left <= 0 and original_time_left > 0:
                if self.status == TimerState.WORK:
                    send_notification("Pomodoro Complete!", "Time for a break")
                    self.next_break()
                else:
                    send_notification("Break Complete!", "Time to focus")
                    self.status = TimerState.WORK
                    self.time_left = POMODORO

    def toggle(self) -> None:
        if self.status is TimerState.IDLE:
            self.status = TimerState.WORK
            self.time_left = POMODORO
        elif self.status is TimerState.PAUSED:
            self.status = self.previous_status
        else:
            self.status = TimerState.PAUSED

    def reset(self) -> None:
        self.status = TimerState.IDLE
        self.time_left = 0
        self.pomodoros = 0

    def skip(self) -> None:
        if self.status in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK) or (
            self.status is TimerState.PAUSED
            and self.previous_status in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK)
        ):
            self.status = TimerState.WORK
            self.time_left = POMODORO
        else:
            self.next_break()

    def stop(self) -> None:
        self.status = TimerState.IDLE
        self.time_left = 0


def read_or_create() -> Pomodoro:
    try:
        if DATA_FILE.exists():
            with DATA_FILE.open("rb") as f:
                return pickle.load(f)
    except Exception:
        logging.debug("Corrupt pkl. Reinitializing state.")
    return Pomodoro()


def save(data: Pomodoro) -> None:
    data.last_update = int(time.time())
    with DATA_FILE.open("wb") as f:
        pickle.dump(data, f)


def format_time(seconds: int) -> str:
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"
    # return f"{minutes:02d} min"


def output_for_waybar(data: Pomodoro):
    text = ""
    tooltip = ""
    if data.status is TimerState.IDLE:
        text = "󰔟 Start"
        if data.pomodoros:
            tooltip = f"Pomodoros: {data.pomodoros}"
        else:
            tooltip = "Click to start a pomodoro"
    elif data.status is TimerState.WORK:
        text = f"󰔛 {format_time(data.time_left)}"
        tooltip = f"Pomodoros: {data.pomodoros}"
    elif data.status is TimerState.SHORT_BREAK:
        text = f"󰭹 {format_time(data.time_left)}"
        tooltip = f"Pomodoros: {data.pomodoros}"
    elif data.status is TimerState.LONG_BREAK:
        text = f"󰭹 {format_time(data.time_left)}"
        tooltip = f"Pomodoros: {data.pomodoros}"
    elif data.status is TimerState.PAUSED:
        text = f"󰏤 {format_time(data.time_left)}"
        tooltip = f"Pomodoros: {data.pomodoros}"

    tooltip += "\nRight-click: Toggle"

    return json.dumps({"text": text, "tooltip": tooltip, "class": data.status.value})


def send_notification(title, message):
    if not DEBUG:
        logging.debug("Notification sent!")
        subprocess.run(
            [
                "notify-send",
                title,
                message,
                "--transient",
                "--urgency=low",
                "--expire-time=4000",
            ]
        )


def main():
    parser = argparse.ArgumentParser(description="Pomodoro Timer for Waybar")
    parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "toggle", "skip", "reset", "stop"],
        help="Action to perform",
    )
    args = parser.parse_args()
    pomodoro = read_or_create()
    pomodoro.update_status()
    if args.action == "toggle":
        pomodoro.toggle()
    elif args.action == "skip":
        pomodoro.skip()
    elif args.action == "reset":
        pomodoro.reset()
    elif args.action == "stop":
        pomodoro.stop()
    logging.debug(pomodoro)
    save(pomodoro)
    return output_for_waybar(pomodoro)


if __name__ == "__main__":
    print(main())
