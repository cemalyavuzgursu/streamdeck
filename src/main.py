import sys
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QApplication

# Make sure 'src' is importable when running directly
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.ui.main_window import MainWindow, _icon_path
from src.utils.constants import APP_NAME, APP_VERSION, APPDATA_DIR


def main():
    APPDATA_DIR.mkdir(parents=True, exist_ok=True)

    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    QApplication.setAttribute(Qt.AA_ShareOpenGLContexts, True)

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationVersion(APP_VERSION)
    # Closing the last window normally quits the app. We want it to
    # keep running in the tray instead.
    app.setQuitOnLastWindowClosed(False)
    icon = _icon_path()
    if icon.exists():
        app.setWindowIcon(QIcon(str(icon)))

    window = MainWindow()
    if "--tray" not in sys.argv:
        window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
