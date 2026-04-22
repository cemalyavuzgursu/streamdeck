import os
import subprocess
import sys
import tempfile
from typing import Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from src.utils.constants import APP_VERSION, GITHUB_API_URL


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str)  # version, download_url, release_notes
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            import requests

            resp = requests.get(GITHUB_API_URL, timeout=8)
            resp.raise_for_status()
            data = resp.json()

            latest = data.get("tag_name", "").lstrip("v")
            if not latest:
                self.no_update.emit()
                return

            if _parse_version(latest) > _parse_version(APP_VERSION):
                assets = data.get("assets", [])
                url = next(
                    (a["browser_download_url"] for a in assets if a["name"].endswith(".exe")),
                    "",
                )
                notes = data.get("body", "")
                self.update_available.emit(latest, url, notes)
            else:
                self.no_update.emit()
        except Exception as e:
            self.error_occurred.emit(str(e))


class UpdateDownloader(QThread):
    progress = pyqtSignal(int)   # 0–100
    finished = pyqtSignal(str)   # temp file path
    error_occurred = pyqtSignal(str)

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self):
        try:
            import requests

            resp = requests.get(self._url, stream=True, timeout=60)
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            suffix = ".exe" if ".exe" in self._url else ".bin"

            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as f:
                tmp_path = f.name
                downloaded = 0
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total:
                        self.progress.emit(int(downloaded * 100 / total))
            self.progress.emit(100)
            self.finished.emit(tmp_path)
        except Exception as e:
            self.error_occurred.emit(str(e))


class Updater(QObject):
    update_available = pyqtSignal(str, str, str)
    no_update = pyqtSignal()
    download_progress = pyqtSignal(int)
    download_finished = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._checker: Optional[UpdateChecker] = None
        self._downloader: Optional[UpdateDownloader] = None

    def check_for_updates(self):
        self._checker = UpdateChecker()
        self._checker.update_available.connect(self.update_available)
        self._checker.no_update.connect(self.no_update)
        self._checker.error_occurred.connect(self.error_occurred)
        self._checker.start()

    def download_update(self, url: str):
        self._downloader = UpdateDownloader(url)
        self._downloader.progress.connect(self.download_progress)
        self._downloader.finished.connect(self.download_finished)
        self._downloader.error_occurred.connect(self.error_occurred)
        self._downloader.start()

    @staticmethod
    def apply_update(new_exe_path: str):
        """Replace running .exe with downloaded one via a batch script, then restart."""
        if not getattr(sys, "frozen", False):
            return  # Running from source, skip

        current_exe = sys.executable
        bat = (
            "@echo off\n"
            "timeout /t 2 /nobreak >nul\n"
            f'move /y "{new_exe_path}" "{current_exe}"\n'
            f'start "" "{current_exe}"\n'
            'del "%~f0"\n'
        )
        bat_path = os.path.join(tempfile.gettempdir(), "_macropad_update.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat)
        subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
        sys.exit(0)
