#!/usr/bin/env python
# Author: Sadykov Miron <MironSadykov@yandex.ru>
# License: MIT
# 2025
"""
Python rewrite of some bash script i found.

This is a Python script for Waybar that displays information
about running Docker containers.
If any containers are running,
the script shows their count along with CPU
and memory usage stats for each container in a formatted table.
If Docker is not running, it outputs an appropriate status message.
"""

import json
import subprocess


def count_running_containers() -> int:
    try:
        containers = subprocess.run(
            ["docker", "ps", "-q"],
            capture_output=True,
            text=True,
            check=True,
        )
        return count_continers(containers)
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        # There is no docker in system.
        return False


def count_continers(containers: subprocess.CompletedProcess):
    return len(containers.stdout.splitlines())


def get_containers() -> list[dict]:
    """Get a list of container stats as dictionaries."""
    try:
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "json"],
            capture_output=True,
            check=True,
            text=True,
        )
        lines = result.stdout.strip().splitlines()
        return [json.loads(line) for line in lines if line.strip()]
    except subprocess.CalledProcessError:
        return []
    except json.JSONDecodeError:
        return []


def table_builder(containers: list[dict]) -> str:
    """Build a pretty table string with container stats."""
    lines = []
    for container in containers:
        name = container.get("Name", "unknown")
        cpu = container.get("CPUPerc", "0%")
        mem = container.get("MemUsage", "0B / 0B").split(" /")[0]
        lines.append(f"{name}|{cpu}|{mem}")
    result = subprocess.run(
        ["column", "-t", "--table-columns", "Name,CPU,MEM", "--separator", "|"],
        input="\n".join(lines),
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=True,
        text=True,
    )
    return result.stdout.strip()


def output_builder(status_class: str, text: str, tooltip: str = "") -> str:
    """Build JSON output for Waybar."""
    data = {
        "class": status_class,
        "text": f"Docker: {text}",
    }
    if tooltip:
        data["tooltip"] = tooltip
    return json.dumps(data)


def main():
    containers_counter = count_running_containers()
    if containers_counter > 0:
        tooltip = table_builder(get_containers())
        print(output_builder("on", f"{containers_counter}", tooltip))
    else:
        print(output_builder("off", ""))


if __name__ == "__main__":
    main()
