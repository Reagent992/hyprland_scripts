#!/usr/bin/env python3

import argparse
import json
import logging
import os
import pickle
import subprocess
import tempfile
from datetime import datetime, time, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Final, cast, final

# logging
Debug = False
if os.environ.get("DEBUG") in ("TRUE", "True", "true", "1"):
    Debug = True
    logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Constants
POMODORO: Final = 25 * 60  # 25 minutes in seconds
SHORT_BREAK: Final = 5 * 60  # 5 minutes in seconds
LONG_BREAK: Final = 15 * 60  # 15 minutes in seconds
DATA_FILE: Final = Path(tempfile.gettempdir()) / "pomodoro_state.pkl"
DAILY_RESET_HOUR: Final = 4

# Toggle settings
ENABLE_LONG_BREAK: Final = True
ENABLE_NOTIFICATIONS: Final = True
ENABLE_DAILY_RESET: Final = False


class Action(StrEnum):
    """Command line actions for the pomodoro timer."""

    STATUS = "status"
    TOGGLE = "toggle"
    SKIP = "skip"
    RESET = "reset"
    STOP = "stop"


class Args(argparse.Namespace):
    """Command line argument namespace for pomodoro timer."""

    action: Action = Action.STATUS


class TimerState(StrEnum):
    """Possible states for the pomodoro timer."""

    IDLE = "idle"
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"
    PAUSED = "paused"


@final
class Pomodoro:
    """Pomodoro timer state manager.

    Tracks the current timer state, remaining time, and completed pomodoros.
    Handles state transitions and timer logic for work sessions and breaks.
    """

    def __init__(self) -> None:  # noqa: D107
        self.time_left = 0
        self.pomodoros = 0
        self.previous_status = TimerState.IDLE
        self._status = TimerState.IDLE
        self.last_update_date = datetime.now()  # noqa: DTZ005
        self._next_4_am = self._get_next_4_am(self.last_update_date)

    @staticmethod
    def _get_next_4_am(last_update_date: datetime) -> datetime:
        four_am_today = datetime.combine(last_update_date, time(4, 0))

        if last_update_date < four_am_today:
            return four_am_today
        return four_am_today + timedelta(days=1)

    @property
    def status(self) -> TimerState:
        """Get current status."""
        return self._status

    @status.setter
    def status(self, value: TimerState) -> None:
        self.previous_status = self._status
        self._status = value

    def next_break(self) -> None:
        """Transition to break state after completing a work session.

        Increments pomodoro count and starts appropriate break type:
        - Long break (15 min) after every 4th pomodoro
        - Short break (5 min) otherwise
        """
        self.pomodoros += 1
        if self.pomodoros % 4 == 0 and ENABLE_LONG_BREAK:
            self.status = TimerState.LONG_BREAK
            self.time_left = LONG_BREAK
        else:
            self.status = TimerState.SHORT_BREAK
            self.time_left = SHORT_BREAK

    def update_status(self) -> None:
        """Update timer state and handle automatic transitions.

        Calculates elapsed time since last update and decrements remaining time.
        Automatically transitions between work and break states when timer expires.
        Sends notifications for completed sessions.
        """
        if self.status in (
            TimerState.WORK,
            TimerState.SHORT_BREAK,
            TimerState.LONG_BREAK,
        ):
            elapsed = datetime.now() - self.last_update_date  # noqa: DTZ005
            original_time_left = self.time_left
            self.time_left = max(0, self.time_left - abs(int(elapsed.total_seconds())))
            if self.time_left <= 0 and original_time_left > 0:
                if self.status == TimerState.WORK:
                    send_notification("Pomodoro Complete!", "Time for a break")
                    self.next_break()
                else:
                    send_notification("Break Complete!", "Time to focus")
                    self.status = TimerState.WORK
                    self.time_left = POMODORO
        if ENABLE_DAILY_RESET and datetime.now() > self._next_4_am:  # noqa: DTZ005
            self.pomodoros = 0
            self._next_4_am = self._get_next_4_am(self.last_update_date)

    def toggle(self) -> None:
        """Toggle between active and paused states.

        Handles state transitions:
        - IDLE -> WORK (start new pomodoro)
        - PAUSED -> previous state (resume)
        - ACTIVE -> PAUSED (pause current session)
        """
        if self.status is TimerState.IDLE:
            self.status = TimerState.WORK
            self.time_left = POMODORO
        elif self.status is TimerState.PAUSED:
            self.status = self.previous_status
        else:
            self.status = TimerState.PAUSED

    def reset(self) -> None:
        """Reset the pomodoro timer to initial state.

        Clears all progress and returns to idle state.
        """
        self.status = TimerState.IDLE
        self.time_left = 0
        self.pomodoros = 0

    def skip(self) -> None:
        """Skip current session or break.

        During break: skip to next work session
        During work: skip to next break
        Paused states are handled based on previous active state.
        """
        if self.status in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK) or (
            self.status is TimerState.PAUSED
            and self.previous_status in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK)
        ):
            self.status = TimerState.WORK
            self.time_left = POMODORO
        else:
            self.next_break()

    def stop(self) -> None:
        """Stop the current timer and return to idle state."""
        self.status = TimerState.IDLE
        self.time_left = 0


def get_pomodoro() -> Pomodoro:
    """Read pomodoro state from file or create new instance."""
    try:
        if DATA_FILE.exists():
            with DATA_FILE.open("rb") as f:
                return cast("Pomodoro", pickle.load(f))  # noqa: S301
    except (FileNotFoundError, PermissionError, EOFError, pickle.UnpicklingError):
        logger.exception("Corrupt pkl. Reinitializing state.")
    return Pomodoro()


def save_pomodoro(data: Pomodoro) -> None:
    """Save pomodoro state to temporary file."""
    data.last_update_date = datetime.now()  # noqa: DTZ005
    with DATA_FILE.open("wb") as f:
        pickle.dump(data, f)


def format_time(seconds: int) -> str:
    """Format seconds as MM:SS string."""
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


def output_for_waybar(data: Pomodoro) -> str:
    """Format pomodoro state for Waybar display(JSON)."""
    text = ""
    tooltip = ""
    if data.status is TimerState.IDLE:
        text = "󰔟 Start"
    elif data.status is TimerState.WORK:
        text = f"󰔛 {format_time(data.time_left)}"
    elif data.status in (TimerState.SHORT_BREAK, TimerState.LONG_BREAK):
        text = f"󰭹 {format_time(data.time_left)}"
    elif data.status is TimerState.PAUSED:
        text = f"󰏤 {format_time(data.time_left)}"
    tooltip = f"Pomodoros: {data.pomodoros}"

    return json.dumps({"text": text, "tooltip": tooltip, "class": data.status.value})


def send_notification(title: str, message: str) -> None:
    """Send desktop notification using notify-send."""
    if not Debug and ENABLE_NOTIFICATIONS:
        logger.debug("Notification sent!")
        _ = subprocess.run(  # noqa: S603
            [  # noqa: S607
                "notify-send",
                title,
                message,
                "--transient",
                "--urgency=low",
                "--expire-time=4000",
            ],
            check=False,
        )


def main() -> str:
    """Entry point for pomodoro timer CLI."""
    parser = argparse.ArgumentParser(description="Pomodoro Timer for Waybar")
    values = ["status", "toggle", "skip", "reset", "stop"]
    _ = parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=values,
        help="Action to perform",
    )
    args = parser.parse_args(namespace=Args())
    pomodoro = get_pomodoro()
    pomodoro.update_status()
    match args.action:
        case Action.TOGGLE:
            pomodoro.toggle()
        case Action.SKIP:
            pomodoro.skip()
        case Action.RESET:
            pomodoro.reset()
        case Action.STOP:
            pomodoro.stop()
        case _:
            ...
    logger.debug(pomodoro)
    save_pomodoro(pomodoro)
    return output_for_waybar(pomodoro)


if __name__ == "__main__":
    print(main())  # noqa: T201
