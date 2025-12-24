# KSnow

A highly customizable snow overlay for KDE Plasma.

<img width="1920" height="1080" alt="Screenshot" src="https://github.com/user-attachments/assets/6a2fa49e-15c8-4eb1-9665-66c86476364a" />


---

## Features

- **Fully customizable** – JSONC config file with comments
- **Two display modes** – Symbols (unicode symbols and emoji) or circles
- **Physics simulation** – Wind, wobble, rotation, variable speeds and sizes, etc.
- **Color support** – RGBA, hex, or named colors (in snake_case)
- **KWin integration** – Rule to overlay on all windows and desktops
- **System tray control** – Toggle snow, load configs, edit settings
- **Desktop entry** – Add to application launcher
- **Terminal-only mode** – Run without system tray icon and notifications

---

## Installation

### Prerequisites
- **Python 3.7+**
- **PySide6**
- **KDE Plasma** (self-explanatory, lol)
- **notify-send** – for notifications (ussually preinstalled on most distros)

### Install dependencies

Simply install PySide6 using your distribution's package manager or using `pip`:

```bash
pip install PySide
```
### Get KSnow

```bash
git clone https://github.com/fishcheese/ksnow.git
cd ksnow```

---
## Usage
### Basic start

```bash
python ksnow.py
```

### System Tray Controls

Click tray icon – Toggle snow on/off

Right-click menu:
- Toggle Snow – Enable/disable snowfall
- Select config – Load a JSONC config file
- Use default config – Restore built-in defaults
- Edit default config – Open config in Kate
- Exit – Close KSnow

### Command-line options

```
--config /path/to/config.jsonc   # Load custom config
--gen-config                     # Generate default config
--gen-config-force               # Overwrite existing config
--install-kwin-rule              # Install KWin overlay rule
--remove-kwin-rule               # Remove KWin rule
--add-as-app                     # Create desktop entry
--terminal-only                  # Run without tray/notifications
```
## Configuration
Edit config.jsonc (created in script directory after --gen-config):

```json
{
  "display_type": "symbol",           // "symbol" or "circle"
  "symbols": ["❄", "❆", "*", "·"],    // Symbols for flakes
  "count": 150,                       // Number of snowflakes
  "min_size": 10,                     // Minimum flake size
  "max_size": 30,                     // Maximum flake size
  "min_speed": 1.0,                   // Slowest falling speed
  "max_speed": 4.0,                   // Fastest falling speed
  "colors": [                         // Flake colors
    [255, 255, 255, 220],             // RGBA
    "#c8dcffcc",                      // Hex with alpha
    "light_blue"                      // Named color
  ],
  "wind_strength": 0.8,               // Side-to-side motion
  "wind_frequency": 50,               // Wind wave frequency
  "wobble_amplitude": 0.5,            // Wobble amount
  "wobble_frequency": 100,            // Wobble speed
  "rotation_enabled": true,           // Enable rotation
  "min_rot_speed": -1.0,              // Min rotation speed
  "max_rot_speed": 1.0,               // Max rotation speed
  "background_color": [0, 0, 0, 0]    // Transparent background
}
```

## KWin Rule
KSnow uses a KWin window rule to:
- Appear on all virtual desktops
- Stay above all windows
- Not hide panels with "Dodge windows" behaviour

You can install/uninstall it via:

```bash
python ksnow.py --install-kwin-rule
python ksnow.py --remove-kwin-rule
```

## Removal

```bash
python ksnow.py --remove-kwin-rule
rm ~/.local/share/applications/KSnow.desktop
rm -r ~/ksnow
```

## FAQ

**Q: Does it work on desktop environments other than KDE Plasma?**
A: It somewhat runs (I tested it on COSMIC and Xfce), but it doesn't work properly because KWin rule won’t apply.

**Q: Why is the snow not on top of windows?**
A: Install the KWin rule with --install-kwin-rule.

**Q: Can I use emojis as flakes?**
A: Yup, but it’s resource-heavy. Unicode symbols are recommended.

## License
This project is released under **The Unlicense**.
You can basically do whatever you would like with this software, its use, modification, or distribution, with no limitation whatsoever.

## Reporting Issues
Found a bug? Have a feature request?
[Open an issue!](github.com/fishcheese/ksnow/issues)
