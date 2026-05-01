"""QWebChannel bridge between the React/HTML UI and the Python backend."""
import json
from typing import Optional

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QFileDialog

from src.core.device_manager import DeviceManager
from src.core.firmware_flasher import FirmwareFlasher
from src.core.updater import Updater


class Bridge(QObject):
    flash_log = pyqtSignal(str)
    flash_progress = pyqtSignal(int)
    flash_done = pyqtSignal(bool, str)

    update_available = pyqtSignal(str, str, str)  # version, url, notes
    update_none = pyqtSignal()
    update_error = pyqtSignal(str)

    modules_discovered = pyqtSignal(str)  # JSON string

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device = DeviceManager(self)
        self._device.modules_updated.connect(self._on_modules_updated)

        self._updater = Updater(self)
        self._updater.update_available.connect(self.update_available)
        self._updater.no_update.connect(self.update_none)
        self._updater.error_occurred.connect(self.update_error)

        self._flasher: Optional[FirmwareFlasher] = None

    # ─────────────── Ports / Device ───────────────
    @pyqtSlot(result=str)
    def list_ports(self) -> str:
        return json.dumps(DeviceManager.list_ports())

    @pyqtSlot(str, result=bool)
    def connect_device(self, port: str) -> bool:
        try:
            self._device.connect(port)
            return True
        except Exception:
            return False

    @pyqtSlot(result=bool)
    def disconnect_device(self) -> bool:
        self._device.disconnect()
        return True

    @pyqtSlot(str, result=bool)
    def send_config(self, profile_json: str) -> bool:
        try:
            profile = json.loads(profile_json)
        except json.JSONDecodeError:
            return False
        payload = {
            "cmd": "config",
            "profile_name": profile.get("name", ""),
            "modules": profile.get("modules", []),
        }
        try:
            self._device.send_config(payload)
            return True
        except Exception:
            return False

    def _on_modules_updated(self, modules):
        serialised = [
            {
                "module_id": m.module_id,
                "module_type": m.module_type,
                "name": m.name,
                "button_count": m.button_count,
                "encoder_count": m.encoder_count,
                "has_display": m.has_display,
            }
            for m in modules
        ]
        self.modules_discovered.emit(json.dumps(serialised))

    # ─────────────── Firmware flash ───────────────
    @pyqtSlot(str)
    def flash_github(self, port: str) -> None:
        self._start_flash(port, bin_path=None, from_github=True)

    @pyqtSlot(str, str)
    def flash_local(self, port: str, bin_path: str) -> None:
        self._start_flash(port, bin_path=bin_path, from_github=False)

    def _start_flash(self, port: str, bin_path: Optional[str], from_github: bool) -> None:
        self._flasher = FirmwareFlasher(port=port, bin_path=bin_path, from_github=from_github)
        self._flasher.progress.connect(self.flash_log)
        self._flasher.log_line.connect(self.flash_log)
        self._flasher.finished.connect(self.flash_done)
        self._flasher.start()

    # ─────────────── File pickers ───────────────
    @pyqtSlot(result=str)
    def pick_firmware_file(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            None, "Firmware .bin seç", "", "Firmware (*.bin);;All files (*.*)"
        )
        return path or ""

    @pyqtSlot(result=str)
    def pick_executable(self) -> str:
        path, _ = QFileDialog.getOpenFileName(
            None, "Uygulama seç", "", "Çalıştırılabilir (*.exe);;All files (*.*)"
        )
        return path or ""

    # ─────────────── Updater ───────────────
    @pyqtSlot()
    def check_for_updates(self) -> None:
        self._updater.check_for_updates()

    @pyqtSlot(str)
    def apply_update(self, url: str) -> None:
        def _on_finished(path: str):
            Updater.apply_update(path)
        self._updater.download_finished.connect(_on_finished)
        self._updater.download_update(url)
