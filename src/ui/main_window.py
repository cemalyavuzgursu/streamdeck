"""Main window: hosts the React/HTML UI inside a QWebEngineView and bridges
it to the Python backend through QWebChannel."""
import sys
from pathlib import Path

from PyQt5.QtCore import QTimer, QUrl, Qt
from PyQt5.QtGui import QIcon
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEnginePage, QWebEngineView
from PyQt5.QtWidgets import (
    QAction, QApplication, QMainWindow, QMenu, QSystemTrayIcon,
)

from src.ui.bridge import Bridge
from src.utils.constants import APP_NAME


def _web_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    bundled = base / "src" / "ui" / "web"
    if bundled.is_dir():
        return bundled
    return Path(__file__).resolve().parent / "web"


def _icon_path() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent.parent))
    return base / "assets" / "icon.ico"


_WEB_DIR = _web_dir()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)

        icon_path = _icon_path()
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self._bridge = Bridge(self)

        self._view = QWebEngineView(self)
        page = QWebEnginePage(self._view)
        self._view.setPage(page)

        channel = QWebChannel(page)
        channel.registerObject("bridge", self._bridge)
        page.setWebChannel(channel)

        self._view.load(QUrl.fromLocalFile(str(_WEB_DIR / "index.html")))
        self.setCentralWidget(self._view)

        self._tray = None
        self._tray_warned = False
        self._setup_tray()
        self._force_quit = False

        if "--tray" in sys.argv and self._tray:
            QTimer.singleShot(1500, self._notify_tray_start)

    # ─────────────── Tray ───────────────
    def _setup_tray(self):
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.windowIcon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip(APP_NAME)

        menu = QMenu()
        show_act = QAction("Göster", self)
        show_act.triggered.connect(self._show_window)
        quit_act = QAction("Çıkış", self)
        quit_act.triggered.connect(self._real_quit)
        menu.addAction(show_act)
        menu.addSeparator()
        menu.addAction(quit_act)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.isVisible():
                self.hide()
            else:
                self._show_window()

    def _notify_tray_start(self):
        if self._tray:
            self._tray.showMessage(
                APP_NAME,
                "Arka planda çalışıyor. Tepsi simgesine tıklayarak açabilirsiniz.",
                QSystemTrayIcon.Information,
                3000,
            )

    def _show_window(self):
        self.showNormal()
        self.activateWindow()
        self.raise_()

    def _real_quit(self):
        self._force_quit = True
        try:
            self._bridge._device.disconnect()
        except Exception:
            pass
        QApplication.quit()

    # ─────────────── Lifecycle ───────────────
    def closeEvent(self, event):
        # Close button hides to tray instead of exiting. Real quit
        # comes from the tray menu's Çıkış action.
        if self._force_quit or not self._tray:
            try:
                self._bridge._device.disconnect()
            except Exception:
                pass
            super().closeEvent(event)
            return
        event.ignore()
        self.hide()
        if not self._tray_warned:
            self._tray_warned = True
            self._tray.showMessage(
                APP_NAME,
                "Arka planda çalışmaya devam ediyor. Tamamen kapatmak için "
                "tepsi simgesinden 'Çıkış' deyin.",
                QSystemTrayIcon.Information,
                3000,
            )
