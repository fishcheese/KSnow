import sys, random, math, signal, json, subprocess, shutil, re, os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QWidget, QSystemTrayIcon, QMenu, QFileDialog
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics, QIcon, QAction

def strip_json_comments(json_str):
    json_str = re.sub(r'/\*[\s\S]*?\*/', '', json_str)
    lines, in_str, cleaned = json_str.split('\n'), False, []
    for line in lines:
        chars, i, esc = [], 0, False
        while i < len(line):
            c = line[i]
            if esc: esc = False; chars.append(c); i+=1; continue
            if c == '\\': esc = True; chars.append(c); i+=1; continue
            if c == '"': in_str = not in_str; chars.append(c); i+=1; continue
            if not in_str and i+1 < len(line) and line[i:i+2] == '//': break
            chars.append(c); i += 1
        cleaned.append(''.join(chars))
    return '\n'.join(cleaned)

DEFAULT_CONFIG_JSONC = """{
  // Display type: "symbol" or "circle"
  "display_type": "symbol",

  // Symbols for snowflakes. Can be unicode symbols or emoji (note: using emoji is resource-heavy). Used when "display_type": "symbol".
  "symbols": ["❄", "❆", "❇", "*", "·"],

  "count": 150,

  "min_size": 10,
  "max_size": 30,

  // Minimum and maximum falling speed
  "min_speed": 1.0,
  "max_speed": 4.0,

  // Snowflake colors in format [R, G, B, A] or strings (can be hex or color name in snake_case)
  "colors": [
    [255, 255, 255, 220],
    [200, 220, 255, 200],
    [220, 240, 255, 180]
  ],

  "wind_strength": 0.8,
  "wind_frequency": 50,

  "wobble_amplitude": 0.5,
  "wobble_frequency": 100,

  "rotation_enabled": true,
  "min_rot_speed": -1.0,
  "max_rot_speed": 1.0,

  "background_color": [0, 0, 0, 0]
}"""

DEFAULT_CONFIG = json.loads(strip_json_comments(DEFAULT_CONFIG_JSONC))

def show_notification(title, msg, icon="dialog-information"):
    try: subprocess.run(["notify-send", title, msg, "-a", "KSnow", "--icon", icon],
                       check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except: pass

TERMINAL_ONLY_MODE = False

def show_kwin_warning_notification():
    if TERMINAL_ONLY_MODE:
        print("Warning: KWin rule is not installed.")
        print("Use --install-kwin-rule to install it.")
        return False

    try:
        result = subprocess.run([
            "notify-send", "KWin rule is not installed",
            "KWin rule must be installed to draw the overlay on top of all windows and on all virtual desktops.",
            "-a", "KSnow", "--icon", "dialog-warning", "--urgency", "critical", "-h", "string:sound-name:dialog-warning",
            "--action", "Install KWin rule"
        ], capture_output=True, text=True, check=False)

        if result.stdout and result.stdout.strip() == "0":
            print("User clicked 'Install KWin rule' in notification")
            return True
    except Exception as e:
        print(f"Notification with action failed: {e}")

    return False

def show_non_kde_warning_notification():
    if TERMINAL_ONLY_MODE:
        print("WARNING: KSnow is designed specifically for KDE Plasma desktop environment.")
        print("The script may not work correctly in other desktop environments (GNOME, Xfce, Cinnamon, COSMIC, etc.).")
        response = input("Do you want to continue anyway? [y/N]: ").strip().lower()
        return response in ['y', 'yes']

    try:
        result = subprocess.run([
            "notify-send", "Non-KDE environment detected",
            "KSnow is designed specifically for KDE Plasma desktop environment. The script may not work correctly in other desktop environments (GNOME, XFCE, COSMIC, etc.).",
            "-a", "KSnow", "--icon", "dialog-warning", "--urgency", "critical", "-h", "string:sound-name:dialog-warning",
            "--action", "Yes", "--action", "No"
        ], capture_output=True, text=True, check=False)

        if result.stdout:
            response = result.stdout.strip()
            if response == "0":
                return True
            elif response == "1":
                return False
    except Exception as e:
        print(f"Notification with action failed: {e}")
        response = input("Do you want to continue anyway? [y/N]: ").strip().lower()
        return response in ['y', 'yes']

    return False

def parse_color(col):
    if isinstance(col, list):
        return QColor(*col) if len(col)==4 else QColor(*col,255)
    elif isinstance(col, str):
        col = col.strip()
        if col.startswith('#'):
            return QColor(col)

        color_str = col.replace('_', ' ')
        color = QColor(color_str)

        if color.isValid():
            return color
        return QColor(255,255,255,220)
    return QColor(255,255,255,220)

class SnowflakeConfig:
    def __init__(self, cfg=None):
        cfg = cfg or json.loads(strip_json_comments(DEFAULT_CONFIG_JSONC))
        for k,v in cfg.items(): setattr(self, k.upper(), v)
        self._normalize()

    def _normalize(self):
        self.BACKGROUND_COLOR = parse_color(self.BACKGROUND_COLOR) if hasattr(self,'BACKGROUND_COLOR') else QColor(0,0,0,0)
        colors = []
        if hasattr(self,'COLORS') and isinstance(self.COLORS,list):
            for c in self.COLORS:
                try: colors.append(parse_color(c))
                except: pass
        self.COLORS = colors or [QColor(255,255,255,220)]

        if not hasattr(self, 'ROTATION_ENABLED'):
            self.ROTATION_ENABLED = True
        if not hasattr(self, 'MIN_ROT_SPEED'):
            self.MIN_ROT_SPEED = -1.0
        if not hasattr(self, 'MAX_ROT_SPEED'):
            self.MAX_ROT_SPEED = 1.0

    def to_dict(self):
        d = {}
        default_dict = json.loads(strip_json_comments(DEFAULT_CONFIG_JSONC))
        for k in default_dict:
            attr = k.upper()
            v = getattr(self, attr) if hasattr(self, attr) else default_dict[k]
            if attr == "BACKGROUND_COLOR" and isinstance(v, QColor):
                d[k] = [v.red(), v.green(), v.blue(), v.alpha()]
            elif attr == "COLORS" and isinstance(v, list):
                d[k] = [[c.red(),c.green(),c.blue(),c.alpha()] if isinstance(c,QColor) else c for c in v]
            else: d[k] = v
        return d

def load_config(path):
    try:
        if not path: return SnowflakeConfig()
        content = path.read_text(encoding='utf-8')
        parsed = json.loads(strip_json_comments(content))
        return SnowflakeConfig(parsed)
    except Exception as e:
        error_msg = f"Config load error: {e}. Using default."
        print(error_msg)
        if not TERMINAL_ONLY_MODE:
            try:
                subprocess.run(["notify-send", "KSnow Config Error",
                               f"Error loading config: {str(e)[:100]}...\nUsing default settings.",
                               "-a", "KSnow", "--icon", "dialog-error", "--urgency", "critical"],
                             check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except:
                pass
        return SnowflakeConfig()

def save_config(path, cfg=None, force=False):
    if path.exists() and not force:
        print(f"Config exists: {path}"); return False
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        content = DEFAULT_CONFIG_JSONC if cfg is None else json.dumps(cfg.to_dict(), indent=2, ensure_ascii=False)
        path.write_text(content, encoding='utf-8')
        print(f"Config saved: {path}"); return True
    except Exception as e: print(f"Save error: {e}"); return False

def check_kwin_rule():
    kwin = Path.home()/".config"/"kwinrulesrc"
    return kwin.exists() and "[ksnow]" in kwin.read_text(errors='ignore')

def read_kwin(): return (Path.home()/".config"/"kwinrulesrc").read_text(encoding='utf-8').splitlines()
def write_kwin(lines): (Path.home()/".config"/"kwinrulesrc").write_text('\n'.join(lines), encoding='utf-8')

def update_general_block(install=True):
    lines = read_kwin()

    general_start = -1
    for i, line in enumerate(lines):
        if line.strip() == "[General]":
            general_start = i
            break

    if general_start == -1:
        if install:
            lines.extend(["[General]", "count=1", "rules=ksnow"])
            write_kwin(lines)
        return

    general_end = general_start + 1
    while general_end < len(lines) and not lines[general_end].startswith("["):
        general_end += 1

    general_lines = lines[general_start:general_end]

    if install:
        count_line = next((i for i, line in enumerate(general_lines) if line.startswith("count=")), -1)
        rules_line = next((i for i, line in enumerate(general_lines) if line.startswith("rules=")), -1)

        if count_line >= 0:
            try:
                count = int(general_lines[count_line].split("=")[1].strip())
                general_lines[count_line] = f"count={count + 1}"
            except:
                general_lines[count_line] = "count=1"

        if rules_line >= 0:
            rules = general_lines[rules_line].split("=")[1].strip()
            if rules and "ksnow" not in rules:
                general_lines[rules_line] = f"rules={rules},ksnow"
            elif not rules:
                general_lines[rules_line] = "rules=ksnow"
        else:
            general_lines.insert(2, "rules=ksnow")
    else:
        for i, line in enumerate(general_lines):
            if line.startswith("rules="):
                rules = [r.strip() for r in line.split("=")[1].split(",") if r.strip()]
                if "ksnow" in rules:
                    rules.remove("ksnow")
                    if rules:
                        general_lines[i] = f"rules={','.join(rules)}"
                    else:
                        del general_lines[i]
                break

    lines[general_start:general_end] = general_lines
    write_kwin(lines)

def restart_kwin():
    try:
        subprocess.run([
            "dbus-send", "--session", "--dest=org.kde.KWin",
            "--type=method_call", "/KWin", "org.kde.KWin.reconfigure"
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        print("KWin reconfigured via DBus")
    except Exception as e:
        print(f"DBus restart error: {e}")

def install_kwin_rule():
    rule = Path(__file__).parent.absolute()/"ksnow.kwinrule"
    if not rule.exists():
        print(f"Error: {rule} not found"); show_notification("KWin Error","Rule file missing","dialog-error"); return False
    lines, in_block, new = read_kwin(), False, []
    for line in lines:
        if line.strip() == "[ksnow]": in_block = True
        elif line.strip().startswith("[") and in_block: in_block = False; new.append(line)
        elif not in_block and line.strip() != "Enabled=false": new.append(line)
    new.append(""); new.append(rule.read_text(encoding='utf-8').strip())
    write_kwin(new)
    update_general_block(install=True)
    restart_kwin()
    print("KWin rule installed"); show_notification("KSnow","Rule installed","dialog-information")
    return True

def remove_kwin_rule():
    lines, in_block, found, new = read_kwin(), False, False, []
    for line in lines:
        if line.strip() == "[ksnow]": in_block, found = True, True; continue
        elif line.strip().startswith("[") and in_block: in_block = False; new.append(line)
        elif not in_block: new.append(line)
    if found:
        write_kwin(new)
        update_general_block(install=False)
        restart_kwin()
        print("Rule removed"); show_notification("KSnow","Rule removed","dialog-information")
    else: print("Rule not found")
    return True

def create_desktop_entry():
    desktop_content = """[Desktop Entry]
Name=KSnow
Comment=Snow overlay for KDE Plasma
Icon=weather-snow
Exec=/usr/bin/python '{}'
Terminal=false
Type=Application
Categories=Utility;Amusement;
""".format(Path(__file__).absolute())

    desktop_dir = Path.home() / ".local" / "share" / "applications"
    desktop_file = desktop_dir / "KSnow.desktop"

    try:
        desktop_dir.mkdir(parents=True, exist_ok=True)
        desktop_file.write_text(desktop_content, encoding='utf-8')
        desktop_file.chmod(0o755)

        subprocess.run(["kbuildsycoca5"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        print(f"Desktop entry created: {desktop_file}")
        show_notification("KSnow", "Desktop entry created successfully", "dialog-information")
        return True
    except Exception as e:
        print(f"Failed to create desktop entry: {e}")
        show_notification("KSnow", f"Failed to create desktop entry: {e}", "dialog-error")
        return False

def parse_args():
    import argparse
    p = argparse.ArgumentParser(description="KSnow - Snow overlay for KDE Plasma")
    p.add_argument('--config', type=str, help='Config file path')
    p.add_argument('--gen-config', action='store_true', help='Generate default config')
    p.add_argument('--gen-config-force', action='store_true', help='Force generate config')
    p.add_argument('--install-kwin-rule', action='store_true', help='Install KWin rule')
    p.add_argument('--remove-kwin-rule', action='store_true', help='Remove KWin rule')
    p.add_argument('--terminal-only', action='store_true', help='Run without system tray and notifications')
    p.add_argument('--add-as-app', action='store_true', help='Create desktop entry')
    return p.parse_args()

class Snowflake:
    __slots__ = ('x','y','size','speed','wobble','rotation','rot_speed','symbol','color','wind_off')
    def __init__(self, w, h, cfg):
        self.x = random.randint(0,w); self.y = random.randint(-h,0)
        self.size = random.uniform(cfg.MIN_SIZE, cfg.MAX_SIZE)
        self.speed = random.uniform(cfg.MIN_SPEED, cfg.MAX_SPEED)
        self.wobble = random.uniform(0,100); self.rotation = random.uniform(0,360)
        if cfg.ROTATION_ENABLED:
            self.rot_speed = random.uniform(cfg.MIN_ROT_SPEED, cfg.MAX_ROT_SPEED)
        else:
            self.rot_speed = 0
        self.wind_off = random.uniform(0,math.pi*2)
        self.symbol = random.choice(cfg.SYMBOLS) if cfg.SYMBOLS else "❄"
        self.color = random.choice(cfg.COLORS)

def open_kate(file):
    try:
        subprocess.Popen(["kate",str(file)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except Exception as e:
        print(f"Kate open failed: {e}")
        return False

class SnowWidget(QWidget):
    def __init__(self, cfg, tray=None, cfg_path=None, terminal_only=False):
        super().__init__()
        self.cfg, self.tray, self.cfg_path, self.snow_enabled = cfg, tray, cfg_path, True
        self.terminal_only = terminal_only
        self.symbol_cache = {}; self.snowflakes = []
        self.setWindowFlags(Qt.BypassWindowManagerHint|Qt.FramelessWindowHint|Qt.WindowStaysOnTopHint|Qt.WindowTransparentForInput)
        self.setAttribute(Qt.WA_TranslucentBackground); self.setWindowTitle("KSnow")
        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(screen); self.w, self.h = screen.width(), screen.height()
        self.snowflakes = [Snowflake(self.w, self.h, cfg) for _ in range(cfg.COUNT)]
        self.timer = QTimer(self); self.timer.timeout.connect(self.update_snow); self.timer.start(16)
        self.show()

        if not check_kwin_rule():
            if not self.terminal_only:
                if show_kwin_warning_notification():
                    if install_kwin_rule():
                        print("Restarting script after KWin rule installation...")
                        os.execv(sys.executable, [sys.executable] + sys.argv)
                    else:
                        show_notification("KSnow", "Failed to install KWin rule", "dialog-error")
                else:
                    show_notification("KSnow", "KWin rule missing. Use --install-kwin-rule", "dialog-warning")
            else:
                print("Warning: KWin rule is not installed. Use --install-kwin-rule to install it.")

    def toggle_snow(self):
        self.snow_enabled = not self.snow_enabled
        if self.snow_enabled:
            self.timer.start(16)
            if self.tray: self.tray.setIcon(QIcon.fromTheme("weather-snow"))
        else:
            self.timer.stop()
            self.update()
            if self.tray:
                from PySide6.QtGui import QPixmap, QPainter
                pixmap = QIcon.fromTheme("weather-snow").pixmap(32, 32)
                disabled = QPixmap(pixmap.size()); disabled.fill(Qt.transparent)
                p = QPainter(disabled); p.setOpacity(0.3); p.drawPixmap(0, 0, pixmap); p.end()
                self.tray.setIcon(QIcon(disabled))

    def load_config(self, path):
        try:
            self.cfg = load_config(path); self.cfg_path = path
            self.snowflakes = [Snowflake(self.w, self.h, self.cfg) for _ in range(self.cfg.COUNT)]
            print(f"Loaded: {path}")
            if not self.terminal_only:
                show_notification("KSnow",f"Loaded: {path.name}","dialog-information")
            self.update_menu()
        except Exception as e: print(f"Load failed: {e}")

    def reload_current_config(self):
        if self.cfg_path and self.cfg_path.exists():
            self.load_config(self.cfg_path)
        else:
            print("No config file to reload")
            if not self.terminal_only:
                show_notification("KSnow", "No config file to reload", "dialog-warning")
        self.update_menu()

    def use_default(self):
        default = Path(__file__).parent.absolute()/"config.jsonc"
        if default.exists():
            self.load_config(default)
        else:
            self.cfg = SnowflakeConfig(); self.cfg_path = None
            self.snowflakes = [Snowflake(self.w,self.h,self.cfg) for _ in range(self.cfg.COUNT)]
            print("Using built-in default")
            self.update_menu()

    def edit_config(self):
        default = Path(__file__).parent.absolute()/"config.jsonc"

        is_default_config = (self.cfg_path is None) or (self.cfg_path == default)

        if is_default_config:
            if default.exists():
                if open_kate(default):
                    print(f"Opening: {default}")
                else:
                    if not self.terminal_only:
                        show_notification("KSnow Error","Kate failed","dialog-error")
            else:
                if save_config(default, None):
                    self.cfg_path = default
                    open_kate(default)
                    if not self.terminal_only:
                        show_notification("KSnow","Default config generated","dialog-information")
                    self.update_menu()
        else:
            if self.cfg_path and self.cfg_path.exists():
                if open_kate(self.cfg_path):
                    print(f"Opening: {self.cfg_path}")
                else:
                    if not self.terminal_only:
                        show_notification("KSnow Error","Kate failed","dialog-error")
            else:
                print(f"Config file not found: {self.cfg_path}")

    def update_menu(self):
        if self.tray:
            default = Path(__file__).parent.absolute()/"config.jsonc"

            is_default_config = (self.cfg_path is None) or (self.cfg_path == default)

            menu = self.tray.contextMenu()
            for action in menu.actions():
                if action.text().startswith("Config:"):
                    config_name = "default" if is_default_config else self.cfg_path.name if self.cfg_path else "unknown"
                    action.setText(f"Config: {config_name}")
                    action.setEnabled(False)
                elif action.text() == "Edit current config" or action.text() == "Edit default config" or action.text() == "Generate config":
                    if is_default_config:
                        if default.exists():
                            action.setText("Edit default config")
                        else:
                            action.setText("Generate config")
                    else:
                        action.setText("Edit current config")

                elif action.text() == "Reload current config":
                    action.setVisible(not is_default_config)

    def get_metrics(self, sym, sz):
        key = (sym, sz)
        if key not in self.symbol_cache:
            f = QFont(); f.setPixelSize(int(sz))
            m = QFontMetrics(f); r = m.boundingRect(sym)
            self.symbol_cache[key] = (r.width(), r.height(), m.descent())
        return self.symbol_cache[key]

    def update_snow(self):
        if not self.snow_enabled: return
        for f in self.snowflakes:
            f.y += f.speed
            wind = math.sin(f.y/self.cfg.WIND_FREQUENCY + f.wobble + f.wind_off) * self.cfg.WIND_STRENGTH
            f.x += wind
            if self.cfg.ROTATION_ENABLED:
                f.rotation += f.rot_speed
            f.x += math.sin(f.y/self.cfg.WOBBLE_FREQUENCY) * self.cfg.WOBBLE_AMPLITUDE
            if f.y > self.h:
                f.y = random.randint(-100,-10); f.x = random.randint(0,self.w)
                f.symbol = random.choice(self.cfg.SYMBOLS) if self.cfg.SYMBOLS else "❄"
                f.color = random.choice(self.cfg.COLORS); f.speed = random.uniform(self.cfg.MIN_SPEED, self.cfg.MAX_SPEED)
        self.update()

    def paintEvent(self, e):
        if not self.snow_enabled:
            p = QPainter(self)
            p.fillRect(self.rect(), self.cfg.BACKGROUND_COLOR)
            return

        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), self.cfg.BACKGROUND_COLOR)
        for f in self.snowflakes:
            p.save(); p.setPen(f.color)
            if self.cfg.DISPLAY_TYPE == "circle":
                p.setBrush(f.color); p.drawEllipse(QPointF(f.x, f.y), f.size/2, f.size/2)
            else:
                font = QFont(); font.setPixelSize(int(f.size)); p.setFont(font)
                p.translate(f.x, f.y)
                if self.cfg.ROTATION_ENABLED:
                    p.rotate(f.rotation)
                w, h, d = self.get_metrics(f.symbol, f.size)
                p.drawText(QPointF(-w/2, h/2 - d), f.symbol)
            p.restore()

    def close_app(self): self.timer.stop(); self.close()

def signal_handler(s, f):
    for w in QApplication.topLevelWidgets():
        if isinstance(w, SnowWidget): w.close_app()
    QApplication.quit()

def select_config(initial_dir=None):
    d = QFileDialog()
    d.setFileMode(QFileDialog.ExistingFile)
    d.setNameFilter("JSONC files (*.jsonc *.json);;All files (*)")

    if initial_dir:
        if isinstance(initial_dir, (str, Path)):
            d.setDirectory(str(initial_dir))

    if d.exec():
        return Path(d.selectedFiles()[0])
    return None

def is_kde_environment():
    current_desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    if "kde" in current_desktop or "plasma" in current_desktop:
        return True

    if os.environ.get("KDE_FULL_SESSION") == "true":
        return True

    if os.environ.get("KDE_SESSION_VERSION"):
        return True

    return False

def main():
    global TERMINAL_ONLY_MODE

    args = parse_args()
    TERMINAL_ONLY_MODE = args.terminal_only

    if TERMINAL_ONLY_MODE:
        def noop_notification(title, msg, icon="dialog-information"):
            print(f"[Notification] {title}: {msg}")
        global show_notification
        show_notification = noop_notification

    if not is_kde_environment():
        print("WARNING: KSnow is designed specifically for KDE Plasma desktop environment.")
        print("The script may not work correctly in other desktop environments (GNOME, Xfce, Cinnamon, COSMIC, etc.).")

        if not show_non_kde_warning_notification():
            print("Exiting.")
            sys.exit(1)

    script = Path(__file__).parent.absolute()
    default = script/"config.jsonc"

    if args.install_kwin_rule:
        install_kwin_rule()
        return 0
    if args.remove_kwin_rule:
        remove_kwin_rule()
        return 0

    if args.gen_config or args.gen_config_force:
        if save_config(default, force=args.gen_config_force):
            show_notification("KSnow", f"Config generated: {default}", "dialog-information")
        return 0

    if not check_kwin_rule():
        print(f"Warning: KWin rule not installed. Use `{sys.argv[0]} --install-kwin-rule`")

    cfg_path = None
    if args.config:
        cfg_path = Path(args.config)
        if not cfg_path.is_absolute(): cfg_path = script/cfg_path
    elif default.exists(): cfg_path = default

    cfg = load_config(cfg_path) if cfg_path else SnowflakeConfig()

    app = QApplication(sys.argv); app.setQuitOnLastWindowClosed(False)
    signal.signal(signal.SIGINT, signal_handler); QTimer().start(200)

    tray = None
    if not TERMINAL_ONLY_MODE and QSystemTrayIcon.isSystemTrayAvailable():
        tray = QSystemTrayIcon()
        if QIcon.hasThemeIcon("weather-snow"):
            tray.setIcon(QIcon.fromTheme("weather-snow"))
        else:
            from PySide6.QtGui import QPixmap, QPainter
            pm = QPixmap(64,64); pm.fill(Qt.transparent);
            p = QPainter(pm); p.setPen(Qt.white); p.setFont(QFont("Arial",40));
            p.drawText(pm.rect(), Qt.AlignCenter, "❄"); p.end()
            tray.setIcon(QIcon(pm))
        tray.setToolTip("KSnow - Snow overlay\nClick to toggle snow")

        menu = QMenu()

        config_name = "default" if cfg_path is None else cfg_path.name if cfg_path else "unknown"
        config_display = QAction(f"Config: {config_name}")
        config_display.setEnabled(False)
        menu.addAction(config_display)
        menu.addSeparator()

        toggle = QAction("Toggle Snow")
        select = QAction("Select config")
        use_def = QAction("Use default config")

        default_config = Path(__file__).parent.absolute()/"config.jsonc"
        is_default_config = (cfg_path is None) or (cfg_path == default_config)

        if is_default_config:
            if default_config.exists():
                edit = QAction("Edit default config")
            else:
                edit = QAction("Generate config")
        else:
            edit = QAction("Edit current config")

        reload = QAction("Reload current config")
        reload.setVisible(not is_default_config)

        exit_a = QAction("Exit")

        menu.addAction(toggle); menu.addSeparator()
        menu.addAction(select); menu.addAction(use_def); menu.addAction(edit)
        menu.addAction(reload); menu.addSeparator(); menu.addAction(exit_a)

        tray.setContextMenu(menu); tray.show()

    win = SnowWidget(cfg, tray, cfg_path, TERMINAL_ONLY_MODE)

    if tray:
        tray.activated.connect(lambda r: win.toggle_snow() if r == QSystemTrayIcon.ActivationReason.Trigger else None)

        toggle.triggered.connect(win.toggle_snow)

        def on_select_config():
            selected = select_config(script)
            if selected:
                win.load_config(selected)

        select.triggered.connect(on_select_config)
        use_def.triggered.connect(win.use_default)
        edit.triggered.connect(win.edit_config)
        reload.triggered.connect(win.reload_current_config)
        exit_a.triggered.connect(app.quit)

    if args.add_as_app:
        create_desktop_entry()
        return 0

    return app.exec()

if __name__ == "__main__": sys.exit(main())
