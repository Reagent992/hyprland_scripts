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

`run_or_focus_hyprpy.py` is another version of the same script. It has **uv** as a dependency and uses the `hyprpy` lib. It was created just for fun.

## 🚀 Installation

1. Clone the repository or download the script and make it executable:

```bash
git clone https://github.com/Reagent992/hyprland_scripts.git
cd hyprland_scripts/run_or_focus
chmod u+x run_or_focus.py
```

## 🛠️ Usage

```bash
run_or_focus.py [workspace] application [application arguments]
```

```ini
# hypr.conf
$open = /path/to/run_or_focus.py
bind = SUPER, O, exec, $open 4 obsidian
bind = SUPER, C, exec, $open 2 code --profile blank_profile
```
