import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPalette
from PyQt5.QtWidgets import QApplication

# Make sure 'src' is importable when running directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ui.main_window import MainWindow
from src.utils.constants import APP_NAME, APP_VERSION, APPDATA_DIR


def _apply_dark_palette(app: QApplication):
    app.setStyle("Fusion")
    pal = QPalette()
    c = {
        QPalette.Window: "#1e1e2e",
        QPalette.WindowText: "#cdd6f4",
        QPalette.Base: "#181825",
        QPalette.AlternateBase: "#313244",
        QPalette.ToolTipBase: "#1e1e2e",
        QPalette.ToolTipText: "#cdd6f4",
        QPalette.Text: "#cdd6f4",
        QPalette.Button: "#313244",
        QPalette.ButtonText: "#cdd6f4",
        QPalette.BrightText: "#f38ba8",
        QPalette.Link: "#89b4fa",
        QPalette.Highlight: "#89b4fa",
        QPalette.HighlightedText: "#1e1e2e",
        QPalette.Disabled + QPalette.Text: "#585b70",
        QPalette.Disabled + QPalette.ButtonText: "#585b70",
        QPalette.Disabled + QPalette.WindowText: "#585b70",
    }
    for role, color in c.items():
        pal.setColor(role, QColor(color))
    app.setPalette(pal)


def main():
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    _apply_dark_palette(app)

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
