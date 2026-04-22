import os
import tempfile
from typing import Optional

from PyQt5.QtCore import QThread, pyqtSignal

from src.utils.constants import GITHUB_API_URL

_FIRMWARE_API = GITHUB_API_URL


class FirmwareFlasher(QThread):
    progress = pyqtSignal(str)       # status line
    log_line = pyqtSignal(str)       # esptool output line
    finished = pyqtSignal(bool, str) # success, message

    def __init__(self, port: str, bin_path: Optional[str] = None, from_github: bool = False):
        super().__init__()
        self._port = port
        self._bin_path = bin_path
        self._from_github = from_github
        self._tmp_file: Optional[str] = None

    def run(self):
        try:
            if self._from_github:
                self.progress.emit("GitHub'dan firmware indiriliyor…")
                self._tmp_file = self._download_latest_bin()

            bin_path = self._tmp_file if self._from_github else self._bin_path
            if not bin_path or not os.path.exists(bin_path):
                self.finished.emit(False, "Firmware dosyası bulunamadı.")
                return

            self.progress.emit(f"ESP32-C3 flash'lanıyor → {self._port}")
            self._flash(bin_path)
            self.finished.emit(True, "Firmware başarıyla yüklendi!")

        except Exception as e:
            self.finished.emit(False, str(e))
        finally:
            if self._tmp_file and os.path.exists(self._tmp_file):
                try:
                    os.unlink(self._tmp_file)
                except OSError:
                    pass

    def _download_latest_bin(self) -> str:
        import requests

        resp = requests.get(_FIRMWARE_API, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        assets = data.get("assets", [])
        url = next((a["browser_download_url"] for a in assets if a["name"].endswith(".bin")), None)
        if not url:
            raise ValueError("Firmware .bin dosyası bu release'de bulunamadı.")

        self.progress.emit(f"İndiriliyor: {url}")
        resp = requests.get(url, stream=True, timeout=120)
        resp.raise_for_status()

        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
            return f.name

    def _flash(self, bin_path: str):
        try:
            import esptool
        except ImportError:
            raise RuntimeError(
                "esptool kurulu değil.\n"
                "Kurmak için: pip install esptool"
            )

        import io
        import contextlib

        args = [
            "--chip", "esp32c3",
            "--port", self._port,
            "--baud", "460800",
            "--before", "default_reset",
            "--after", "hard_reset",
            "write_flash",
            "-z", "--flash_mode", "dio",
            "--flash_freq", "80m",
            "--flash_size", "detect",
            "0x0", bin_path,
        ]

        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            esptool.main(args)

        for line in buf.getvalue().splitlines():
            self.log_line.emit(line)
