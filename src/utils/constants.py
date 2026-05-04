import os
import sys
from pathlib import Path

APP_NAME = "MacroPad Configurator"
APP_VERSION = "1.17.0"

if sys.platform == "win32":
    APPDATA_DIR = Path(os.environ.get("APPDATA", "~")) / "MacroPad"
else:
    APPDATA_DIR = Path.home() / ".config" / "MacroPad"

PROFILES_DIR = APPDATA_DIR / "profiles"

GITHUB_REPO_OWNER = "cemalyavuzgursu"
GITHUB_REPO_NAME = "streamdeck"
GITHUB_API_URL = (
    f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
)

BAUD_RATE = 115200
SERIAL_TIMEOUT = 2

ACTION_NONE = "none"
ACTION_SHORTCUT = "shortcut"
ACTION_MEDIA = "media"
ACTION_APP = "app_launch"
ACTION_MACRO = "macro"
ACTION_PROFILE_SWITCH = "profile_switch"

ACTION_LABELS = {
    ACTION_NONE: "Yok",
    ACTION_SHORTCUT: "Klavye Kısayolu",
    ACTION_MEDIA: "Medya Kontrolü",
    ACTION_APP: "Uygulama Aç",
    ACTION_MACRO: "Makro (Tuş Dizisi)",
    ACTION_PROFILE_SWITCH: "Profil Değiştir",
}

MEDIA_ACTIONS = {
    "volume_up": "Ses Artır (+)",
    "volume_down": "Ses Azalt (−)",
    "mute": "Sessiz / Aç",
    "play_pause": "Oynat / Duraklat",
    "next_track": "Sonraki Parça",
    "prev_track": "Önceki Parça",
    "stop": "Durdur",
}

DISPLAY_CLOCK = "clock"
DISPLAY_PROFILE = "profile_name"
DISPLAY_VOLUME = "volume"
DISPLAY_CUSTOM = "custom_text"

DISPLAY_MODES = {
    DISPLAY_CLOCK: "Saat",
    DISPLAY_PROFILE: "Aktif Profil Adı",
    DISPLAY_VOLUME: "Ses Seviyesi",
    DISPLAY_CUSTOM: "Özel Metin",
}

STYLE_DARK = """
QMainWindow, QDialog, QWidget#central {
    background-color: #1e1e2e;
    color: #cdd6f4;
}
QWidget {
    font-family: 'Segoe UI', sans-serif;
    font-size: 13px;
    color: #cdd6f4;
}
QToolBar {
    background-color: #181825;
    border-bottom: 2px solid #313244;
    padding: 4px 8px;
    spacing: 6px;
}
QStatusBar {
    background-color: #181825;
    color: #6c7086;
    border-top: 1px solid #313244;
}
QMenuBar {
    background-color: #181825;
    color: #cdd6f4;
    border-bottom: 1px solid #313244;
}
QMenuBar::item:selected { background-color: #313244; }
QMenu {
    background-color: #1e1e2e;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 4px;
}
QMenu::item { padding: 6px 24px; border-radius: 4px; }
QMenu::item:selected { background-color: #313244; }
QMenu::separator { height: 1px; background: #313244; margin: 4px 8px; }
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 14px;
    min-width: 70px;
}
QPushButton:hover { background-color: #45475a; border-color: #89b4fa; }
QPushButton:pressed { background-color: #585b70; }
QPushButton:disabled { color: #585b70; border-color: #313244; background-color: #252535; }
QPushButton#primary {
    background-color: #89b4fa;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#primary:hover { background-color: #b4d0ff; }
QPushButton#primary:pressed { background-color: #74a8e8; }
QPushButton#primary:disabled { background-color: #45475a; color: #6c7086; }
QPushButton#danger {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#danger:hover { background-color: #ff9db5; }
QPushButton#success {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
    border: none;
}
QPushButton#success:hover { background-color: #b8f0b3; }
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
    min-width: 120px;
}
QComboBox:focus { border-color: #89b4fa; }
QComboBox::drop-down { border: none; width: 24px; }
QComboBox::down-arrow { width: 12px; height: 12px; }
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
    border: 1px solid #45475a;
    outline: none;
}
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 5px 10px;
}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus { border-color: #89b4fa; }
QListWidget {
    background-color: #181825;
    border: 1px solid #313244;
    border-radius: 8px;
    outline: none;
    padding: 4px;
}
QListWidget::item { padding: 8px 6px; border-radius: 6px; }
QListWidget::item:selected { background-color: #313244; color: #89b4fa; }
QListWidget::item:hover:!selected { background-color: #25253a; }
QScrollBar:vertical {
    background: #181825;
    width: 8px;
    border-radius: 4px;
}
QScrollBar::handle:vertical {
    background: #45475a;
    border-radius: 4px;
    min-height: 24px;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar:horizontal {
    background: #181825;
    height: 8px;
}
QScrollBar::handle:horizontal { background: #45475a; border-radius: 4px; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QGroupBox {
    border: 1px solid #313244;
    border-radius: 8px;
    margin-top: 14px;
    padding-top: 10px;
    font-weight: bold;
    color: #89b4fa;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLabel { color: #cdd6f4; }
QProgressBar {
    background-color: #313244;
    border: none;
    border-radius: 4px;
    height: 8px;
    text-align: center;
    color: transparent;
}
QProgressBar::chunk { background-color: #89b4fa; border-radius: 4px; }
QSplitter::handle { background-color: #313244; }
QSplitter::handle:horizontal { width: 2px; }
QSplitter::handle:vertical { height: 2px; }
QTabWidget::pane { border: 1px solid #313244; border-radius: 0 6px 6px 6px; background-color: #1e1e2e; }
QTabBar::tab {
    background-color: #181825;
    color: #6c7086;
    padding: 8px 18px;
    border: 1px solid #313244;
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    margin-right: 2px;
}
QTabBar::tab:selected { background-color: #1e1e2e; color: #cdd6f4; border-color: #313244; }
QTabBar::tab:hover:!selected { background-color: #252535; }
QCheckBox { spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px;
    border: 2px solid #45475a;
    border-radius: 4px;
    background-color: #313244;
}
QCheckBox::indicator:checked { background-color: #89b4fa; border-color: #89b4fa; }
QFrame#separator { background-color: #313244; max-height: 1px; }
"""
