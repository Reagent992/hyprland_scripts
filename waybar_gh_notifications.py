#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pygithub",
#   "python-dotenv",
# ]
# ///
"""Waybar script to display GitHub notifications.

Based on: <https://github.com/mcgillij/waybar_github_notifications>

Dependencies:
- uv  <https://docs.astral.sh/uv/>

Usage:
1. Place GITHUB_TOKEN in .env file near script.
2. `uv run waybar_github_notifications.py <github_token>`


Waybar config:
```json
  "custom/gh-notifications": {
    "exec": "uv run ~/your_path/waybar_gh_notifications.py",
    "hide-empty-text": true,
    "format": " {text}",
    "return-type": "json",
    "interval": 60,
    "on-click": "exec xdg-open https://github.com/notifications",
  },
```

"""

import json
import os
import sys
from typing import TYPE_CHECKING, cast

import requests.exceptions
from dotenv import load_dotenv
from github import Auth, Github, GithubException

if TYPE_CHECKING:
    from github.AuthenticatedUser import AuthenticatedUser

_ = load_dotenv()
GITHUB_TOKEN: str | None = os.getenv("GITHUB_TOKEN")


def get_notifications(token: str) -> int:
    """Fetch unread GitHub notification count for the given token.

    Args:
        token: GitHub personal access token.

    Returns:
        Number of unread notifications.
    """
    try:
        g = Github(auth=Auth.Token(token))
        user = cast("AuthenticatedUser", g.get_user())
        notifications = user.get_notifications(all=False, participating=False)
        return notifications.totalCount if hasattr(notifications, "totalCount") else len(list(notifications))
    except (GithubException, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
        print(json.dumps({"text": "error", "tooltip": str(e)}))
        sys.exit(1)


def main() -> None:
    """Entry point. Prints JSON with notification count for waybar."""
    if GITHUB_TOKEN is None:
        print(json.dumps({"text": "error", "tooltip": "GITHUB_TOKEN not set"}))
        sys.exit(1)

    count = get_notifications(GITHUB_TOKEN)
    print(
        json.dumps(
            {
                "text": count or "",
                "tooltip": f"{count} GitHub notifications",
            }
        )
    )


if __name__ == "__main__":
    main()
