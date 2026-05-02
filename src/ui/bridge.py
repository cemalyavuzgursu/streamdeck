"""QWebChannel bridge between the React/HTML UI and the Python backend."""
import json
from datetime import datetime
from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QFileDialog

from src.core.action_executor import ActionExecutor
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

    # Fired when the device reports a button press whose action is
    # "profile_switch" — JS catches this and changes activeProfileId.
    profile_switch_requested = pyqtSignal(str)  # target profile_id

    # Visible feedback for action execution (logged in JS console + toast).
    action_executed = pyqtSignal(str, str)  # action_type, status

    def __init__(self, parent=None):
        super().__init__(parent)
        self._device = DeviceManager(self)
        self._device.modules_updated.connect(self._on_modules_updated)
        self._device.message_received.connect(self._on_device_message)

        self._updater = Updater(self)
        self._updater.update_available.connect(self.update_available)
        self._updater.no_update.connect(self.update_none)
        self._updater.error_occurred.connect(self.update_error)

        self._flasher: Optional[FirmwareFlasher] = None
        self._executor = ActionExecutor()
        self._cached_profile: Optional[Dict[str, Any]] = None

        # The firmware has no RTC, so we push the current wall-clock time
        # every 30s. The OLED only redraws if it's in CLOCK mode.
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(30_000)
        self._clock_timer.timeout.connect(self._push_clock)
        self._clock_timer.start()
        # Also push immediately when a connection completes.
        self._device.connection_changed.connect(
            lambda connected, _port: self._push_clock() if connected else None
        )

    def _push_clock(self) -> None:
        if not self._device.is_connected:
            return
        now = datetime.now()
        try:
            self._device.send_config({
                "cmd": "clock",
                "time": now.strftime("%H:%M"),
                "date": now.strftime("%d.%m.%Y"),
            })
        except Exception:
            pass

    def _on_device_message(self, msg: dict) -> None:
        """Dispatch incoming JSON messages from the firmware."""
        if msg.get("type") == "button_event" and msg.get("pressed"):
            self._handle_button_press(
                str(msg.get("module_id", "")),
                int(msg.get("index", -1)),
            )

    def _handle_button_press(self, module_id: str, index: int) -> None:
        if not self._cached_profile or index < 0:
            return
        for mod in self._cached_profile.get("modules", []):
            if str(mod.get("module_id", "")) != module_id:
                continue
            buttons = mod.get("buttons", [])
            if 0 <= index < len(buttons):
                btn = buttons[index] or {}
                action_type = btn.get("action_type", "none")
                action_data = btn.get("action_data", {}) or {}
                if action_type == "profile_switch":
                    target = str(action_data.get("profile_id", ""))
                    if target:
                        self.profile_switch_requested.emit(target)
                    self.action_executed.emit(action_type, f"switch → {target}")
                else:
                    status = self._executor.execute(action_type, action_data)
                    self.action_executed.emit(action_type, status)
            return

    # ─────────────── Ports / Device ───────────────
    @pyqtSlot(result=str)
    def list_ports(self) -> str:
        return json.dumps(DeviceManager.list_ports())

    @pyqtSlot(result=str)
    def list_ports_detailed(self) -> str:
        return json.dumps(DeviceManager.list_ports_detailed())

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

    @pyqtSlot(str)
    def cache_profile(self, profile_json: str) -> None:
        """Update the local action lookup table without touching the device."""
        try:
            self._cached_profile = json.loads(profile_json)
        except json.JSONDecodeError:
            pass

    @pyqtSlot(str, result=bool)
    def send_config(self, profile_json: str) -> bool:
        try:
            profile = json.loads(profile_json)
        except json.JSONDecodeError:
            return False
        # Keep a copy locally — the firmware doesn't run actions itself
        # (ESP32-C3 has no USB HID), so we look up bindings here when
        # a button_event arrives.
        self._cached_profile = profile
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
        if not port:
            self.flash_done.emit(False, "Port seçilmedi.")
            return
        # esptool needs exclusive access; release the port before flashing.
        try:
            self._device.disconnect()
        except Exception:
            pass
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
