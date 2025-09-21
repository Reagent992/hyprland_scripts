import argparse
import json
import pickle
import subprocess
import tempfile
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

# Constants
POMODORO = 25 * 60  # 25 minutes in seconds
SHORT_BREAK = 5 * 60  # 5 minutes in seconds
LONG_BREAK = 15 * 60  # 15 minutes in seconds
tmp_dir = Path(tempfile.gettempdir())
DATA_FILE = tmp_dir / "pomodoro_state.json"


class TimerState(Enum):
    inactive = "inactive"
    pomodoro = "pomodoro"
    short_break = "short_break"
    long_break = "long_break"
    paused = "paused"
    running = "running"


@dataclass
class PomodoroData:
    time_left: int = 0
    pomodoros: int = 0
    last_update: int = 0
    status: TimerState = TimerState.inactive


@dataclass
class Pomodoro:
    data: PomodoroData

    def toggle(self) -> None: ...
    def reset(self) -> None: ...
    def stop(self) -> None: ...
    def skip(self) -> None: ...


def read_or_create_data() -> PomodoroData:
    if DATA_FILE.exists():
        with DATA_FILE.open("rb") as f:
            data = pickle.load(f)
    else:
        data = PomodoroData()
    return data


def format_time(seconds: int) -> str:
    minutes = seconds // 60
    seconds = seconds % 60
    # return f"{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d} min"


def output_for_waybar(data: PomodoroData):
    text = ""
    tooltip = ""
    if data.status is TimerState.inactive:
        text = "󰔟 Start"
        tooltip = "Click to start a pomodoro"
    elif data.status is TimerState.pomodoro:
        text = f"󰔛 {format_time(data.time_left)}"
        tooltip = f"Focus time - Pomodoros: {data.pomodoros}"
    elif data.status is TimerState.short_break:
        text = f"󰭹 {format_time(data.time_left)}"
        tooltip = f"Short break - Pomodoros: {data.pomodoros}"
    elif data.status is TimerState.long_break:
        text = f"󰭹 {format_time(data.time_left)}"
        tooltip = f"Long break - Pomodoros: {data.pomodoros}"
    elif data.status is TimerState.paused:
        text = f"󰏤 {format_time(data.time_left)}"
        tooltip = f"Paused - Pomodoros: {data.pomodoros}"

    tooltip += "\nClick: Toggle | Right-click: Skip | Middle-click: Reset"

    return json.dumps({"text": text, "tooltip": tooltip, "class": data.status.value})


def send_notification(title, message):
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
        choices=["status", "toggle", "skip", "reset"],
        help="Action to perform",
    )
    args = parser.parse_args()
    data = read_or_create_data()
    pomodoro = Pomodoro(data)
    if not args.action:
        return output_for_waybar(data)
    elif args.action == "toggle":
        pomodoro.toggle()
    elif args.action == "skip":
        pomodoro.skip()
    elif args.action == "reset":
        pomodoro.reset()
    # return output_for_waybar(data)


if __name__ == "__main__":
    print(main())
