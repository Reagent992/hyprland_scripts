# GitHub Notifications

> Show unread GitHub notification count in waybar.

<img width="59" height="43" alt="screenshot-2026-07-23_12-56-51" src="https://github.com/user-attachments/assets/4a4e59f5-72f0-4253-a875-d06f9490e1e2" />

## What It Does

- Fetches unread notification count from GitHub API via `pygithub`.
- Outputs JSON for waybar's `return-type: json`.

## Requirements

- Python 3.12+
- GitHub personal access token (classic, with `notifications` scope)
- uv

## Installation

```bash
git clone https://github.com/Reagent992/hyprland_scripts.git
cd hyprland_scripts
```

## Usage

1. Create a `.env` file next to the script:

```
GITHUB_TOKEN=ghp_...
```

2. Add to waybar config:

```json
"custom/gh-notifications": {
  "exec": "uv run ~/hyprland_scripts/waybar_gh_notifications.py",
  "hide-empty-text": true,
  "format": " {text}",
  "return-type": "json",
  "interval": 60,
  "on-click": "exec xdg-open https://github.com/notifications",
},
```

## Troubleshooting

- If waybar shows `"error"`, check your network connection.
- Ensure `GITHUB_TOKEN` is set in `.env` and has the correct scope.
