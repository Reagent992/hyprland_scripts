# Pomodoro

This pomodoro timer is an improved version of the timer from the repository: https://github.com/Tejas242/pomodoro-for-waybar .

![Menu](./pomodoro_menu.png)

## Setup

```jsonc
// waybar's config.jsonc
  "custom/pomodoro": {
    "exec": "~/path/to/pomodoro.py",
    "on-click-right": "~/path/to/pomodoro.py toggle",
    "return-type": "json",
    "interval": 1,
    "format": "{}",
    "menu": "on-click",
    "menu-file": "~/path/to/pomodoro-menu.xml",
    "menu-actions": {
      "toggle": "~/path/to/pomodoro.py toggle",
      "skip": "~/path/to/pomodoro.py skip",
      "stop": "~/path/to/pomodoro.py stop",
      "reset": "~/path/to/pomodoro.py reset",
    },
  },
```

```css
/* style.css */
menu {
  border-radius: 15px;
  background: #2d353b;
  color: #d3c6aa;
}
menuitem {
  border-radius: 15px;
}
```
