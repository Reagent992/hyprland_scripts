# Run or focus
## 📋 What It does

A utility script for **Hyprland** that ensures only one instance of a specific application is running.
- If the app is already running, it will focus the window.
- If not, it will launch the app, optionally on a specified workspace.

## 🧱 Requirements

- Linux system running Hyprland
- Python 3.10+
- `hyprctl` (should come with Hyprland)
- `notify-send` (typically provided by `libnotify`)

## 🚀 Installation
1. Clone the repository or download the script and make it executable:
```bash
git clone https://github.com/yourusername/hypr-single-launch.git
cd hypr-single-launch
chmod +x run_or_focus.py
```

## 🛠️ Usage
```bash
run_or_focus.py [workspace] application [application arguments]
```

```ini
# hypr.conf
$run_or_focus = /path/to/run_or_focus.py
bind = SUPER, O, exec, run_or_focus 4 obsidian
bind = SUPER, C, exec, run_or_focus 2 code --profile blank_profile
```
