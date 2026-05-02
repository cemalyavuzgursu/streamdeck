import os
import subprocess
import sys
import tempfile
from typing import Optional

from PyQt5.QtCore import QObject, QThread, pyqtSignal

from src.utils.constants import (
    APP_VERSION,
    GITHUB_API_URL,
    GITHUB_REPO_NAME,
    GITHUB_REPO_OWNER,
)


_RELEASES_LATEST_HTML = (
    f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"
)
_USER_AGENT = f"MacroPad-Configurator/{APP_VERSION} (+https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME})"


def _parse_version(v: str) -> tuple:
    try:
        return tuple(int(x) for x in v.lstrip("v").split("."))
    except ValueError:
        return (0,)


def _latest_tag_via_redirect(requests_mod) -> Optional[str]:
    """Fetch the latest tag without calling the rate-limited API.

    /releases/latest is a redirect to /releases/tag/vX.Y.Z — we just need
    the Location header. No API quota involved.
    """
    try:
        resp = requests_mod.get(
            _RELEASES_LATEST_HTML,
            allow_redirects=False,
            timeout=8,
            headers={"User-Agent": _USER_AGENT},
        )
        loc = resp.headers.get("Location", "")
        if "/tag/" in loc:
            return loc.rsplit("/", 1)[-1]
    except Exception:
        pass
    return None


class UpdateChecker(QThread):
    update_available = pyqtSignal(str, str, str)  # version, download_url, release_notes
    no_update = pyqtSignal()
    error_occurred = pyqtSignal(str)

    def run(self):
        try:
            import requests
        except Exception as e:
            self.error_occurred.emit(f"requests yüklü değil: {e}")
            return

        latest = ""
        url = ""
        notes = ""

        # Try the JSON API first — gives us proper asset URLs and notes.
        try:
            resp = requests.get(
                GITHUB_API_URL,
                timeout=8,
                headers={"User-Agent": _USER_AGENT, "Accept": "application/vnd.github+json"},
            )
            if resp.status_code == 200:
                data = resp.json()
                latest = data.get("tag_name", "").lstrip("v")
                assets = data.get("assets", [])
                url = next(
                    (a["browser_download_url"] for a in assets if a["name"].endswith(".exe")),
                    "",
                )
                notes = data.get("body", "") or ""
        except Exception:
            pass

        # Fallback: parse the redirect from /releases/latest. This avoids
        # the API rate limit (60/hr anonymous) entirely.
        if not latest:
            tag = _latest_tag_via_redirect(requests)
            if tag:
                latest = tag.lstrip("v")
                url = (
                    f"https://github.com/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
                    f"/releases/download/{tag}/MacroPad.exe"
                )

        if not latest:
            self.error_occurred.emit("Güncelleme bilgisi alınamadı (rate limit veya bağlantı hatası).")
            return

        if _parse_version(latest) > _parse_version(APP_VERSION):
            self.update_available.emit(latest, url, notes)
        else:
            self.no_update.emit()


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

        # Sanity check the download — anything under 10MB isn't our exe.
        try:
            if not os.path.exists(new_exe_path) or os.path.getsize(new_exe_path) < 10_000_000:
                return
        except OSError:
            return

        current_exe = sys.executable

        # COPY + retry beats MOVE for two reasons:
        #   1. MOVE across drives is not atomic and fails mid-flight if the
        #      target file lock is still held by the exiting process.
        #   2. If the copy fails, the source stays intact and the user's
        #      installed exe is untouched — they can re-run it.
        # The retry loop covers the brief window between sys.exit() and
        # the OS releasing the executable file lock.
        bat = (
            "@echo off\n"
            "title MacroPad Updater\n"
            "echo Eski surum kapanmasi bekleniyor...\n"
            "timeout /t 3 /nobreak >nul\n"
            "\n"
            f'set "NEW_FILE={new_exe_path}"\n'
            f'set "CUR_FILE={current_exe}"\n'
            "set RETRIES=20\n"
            "\n"
            ":retry\n"
            'copy /y /b "%NEW_FILE%" "%CUR_FILE%" >nul 2>&1\n'
            "if %errorlevel% equ 0 goto :ok\n"
            "set /a RETRIES=%RETRIES%-1\n"
            "if %RETRIES% gtr 0 (\n"
            "  echo .\n"
            "  timeout /t 1 /nobreak >nul\n"
            "  goto :retry\n"
            ")\n"
            "echo.\n"
            "echo Guncelleme basarisiz oldu. Yeni surum:\n"
            "echo   %NEW_FILE%\n"
            "echo Mevcut konum:\n"
            "echo   %CUR_FILE%\n"
            "echo.\n"
            "echo Manuel kopyalayabilirsin. Pencereyi kapatmak icin bir tusa bas.\n"
            "pause >nul\n"
            "exit /b 1\n"
            "\n"
            ":ok\n"
            'del /q "%NEW_FILE%" 2>nul\n'
            'start "" "%CUR_FILE%"\n'
            "(goto) 2>nul & del \"%~f0\"\n"
        )
        bat_path = os.path.join(tempfile.gettempdir(), "_macropad_update.bat")
        with open(bat_path, "w", encoding="utf-8") as f:
            f.write(bat)
        # Show the cmd window so the user sees progress — silent failures
        # in v1.x.x had us chasing a "failed to move" report with no log.
        subprocess.Popen(["cmd", "/c", bat_path])
        # Give the spawned cmd a moment to start before we yank ourselves.
        import time
        time.sleep(0.4)
        sys.exit(0)
