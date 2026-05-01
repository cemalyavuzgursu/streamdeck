"""Main window: hosts the React/HTML UI inside a QWebEngineView and bridges
it to the Python backend through QWebChannel."""
import sys
from pathlib import Path

from PyQt5.QtCore import QUrl
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import QMainWindow

from src.ui.bridge import Bridge
from src.utils.constants import APP_NAME


def _web_dir() -> Path:
    # PyInstaller --onefile extracts bundled data to sys._MEIPASS at runtime.
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    bundled = base / "src" / "ui" / "web"
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parent / "web"


_WEB_DIR = _web_dir()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)

        self._bridge = Bridge(self)

        self._view = QWebEngineView(self)
        page = QWebEnginePage(self._view)
        self._view.setPage(page)

        channel = QWebChannel(page)
        channel.registerObject("bridge", self._bridge)
        page.setWebChannel(channel)

        self._view.load(QUrl.fromLocalFile(str(_WEB_DIR / "index.html")))
        self.setCentralWidget(self._view)

    def closeEvent(self, event):
        try:
            self._bridge._device.disconnect()
        except Exception:
            pass
        super().closeEvent(event)
