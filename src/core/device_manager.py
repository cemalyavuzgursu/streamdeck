import json
from typing import List, Optional

import serial
import serial.tools.list_ports
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal


class ModuleInfo:
    def __init__(
        self,
        module_id: str,
        module_type: str,
        name: str = "",
        button_count: int = 0,
        encoder_count: int = 0,
        has_display: bool = False,
        i2c_address: int = 0,
    ):
        self.module_id = module_id
        self.module_type = module_type
        self.name = name or f"Modül {module_id}"
        self.button_count = button_count
        self.encoder_count = encoder_count
        self.has_display = has_display
        self.i2c_address = i2c_address


class SerialWorker(QThread):
    modules_discovered = pyqtSignal(list)
    firmware_version_received = pyqtSignal(str)
    connection_changed = pyqtSignal(bool, str)
    message_received = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)

    def __init__(self, port: str, baud: int = 115200):
        super().__init__()
        self._port = port
        self._baud = baud
        self._serial: Optional[serial.Serial] = None
        self._running = False
        self._pending_writes: list = []

    def run(self):
        self._running = True
        try:
            # Configure DTR/RTS BEFORE opening so the EN pin on ESP32 dev
            # boards isn't pulsed by the open() call. Without this the
            # chip reboots on every connect, USB re-enumerates, and the
            # link drops in a loop.
            self._serial = serial.Serial()
            self._serial.port = self._port
            self._serial.baudrate = self._baud
            self._serial.timeout = 0.1
            self._serial.dtr = False
            self._serial.rts = False
            self._serial.open()

            self.connection_changed.emit(True, self._port)
            self._send_raw({"cmd": "discover"})

            while self._running:
                # Flush pending writes
                while self._pending_writes:
                    payload = self._pending_writes.pop(0)
                    try:
                        self._serial.write(payload)
                    except serial.SerialException:
                        pass

                try:
                    line = self._serial.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self._handle_line(line)
                except serial.SerialException as e:
                    self.error_occurred.emit(str(e))
                    break

        except serial.SerialException as e:
            self.error_occurred.emit(str(e))
        finally:
            if self._serial and self._serial.is_open:
                self._serial.close()
            self._running = False
            self.connection_changed.emit(False, self._port)

    def stop(self):
        self._running = False

    def _send_raw(self, data: dict):
        if self._serial and self._serial.is_open:
            payload = (json.dumps(data) + "\n").encode("utf-8")
            self._pending_writes.append(payload)

    def send_command(self, data: dict):
        self._send_raw(data)

    def _handle_line(self, line: str):
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            return

        msg_type = data.get("type")
        if msg_type == "modules":
            fw_ver = str(data.get("firmware_version", ""))
            if fw_ver:
                self.firmware_version_received.emit(fw_ver)
            modules = []
            for m in data.get("modules", []):
                modules.append(
                    ModuleInfo(
                        module_id=str(m.get("id", "")),
                        module_type=m.get("type", "slave"),
                        name=m.get("name", ""),
                        button_count=int(m.get("buttons", 0)),
                        encoder_count=int(m.get("encoders", 0)),
                        has_display=bool(m.get("display", False)),
                        i2c_address=int(m.get("addr", 0)),
                    )
                )
            self.modules_discovered.emit(modules)
        else:
            self.message_received.emit(data)


class DeviceManager(QObject):
    connection_changed = pyqtSignal(bool, str)  # connected, port
    modules_updated = pyqtSignal(list)           # List[ModuleInfo]
    error_occurred = pyqtSignal(str)
    config_sent = pyqtSignal()
    message_received = pyqtSignal(dict)          # any non-modules JSON line
    firmware_version_received = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._worker: Optional[SerialWorker] = None
        self._connected = False
        self._port = ""
        self._modules: List[ModuleInfo] = []

        self._port_scan_timer = QTimer(self)
        self._port_scan_timer.timeout.connect(self._scan_ports)
        self._port_scan_timer.start(3000)
        self._known_ports: set = set()

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def current_port(self) -> str:
        return self._port

    @property
    def modules(self) -> List[ModuleInfo]:
        return self._modules

    @staticmethod
    def list_ports() -> List[str]:
        return [p.device for p in serial.tools.list_ports.comports()]

    @staticmethod
    def list_ports_detailed() -> list:
        items = []
        for p in serial.tools.list_ports.comports():
            desc = (p.description or "").strip()
            manufacturer = (p.manufacturer or "").strip()
            blob = f"{desc} {manufacturer}".upper()
            is_esp = (
                getattr(p, "vid", None) == 0x303A  # Espressif native USB
                or "ESP32" in blob
                or "ESPRESSIF" in blob
                or "CP210" in blob
                or "CH340" in blob
                or "CH9102" in blob
            )
            label = p.device
            if is_esp:
                label = f"{p.device} — ESP32-C3"
            elif desc and desc.lower() != p.device.lower():
                short = desc[:32]
                label = f"{p.device} — {short}"
            items.append({"device": p.device, "label": label, "is_esp": is_esp})
        return items

    def connect(self, port: str):
        self.disconnect()
        self._worker = SerialWorker(port)
        self._worker.modules_discovered.connect(self._on_modules_discovered)
        self._worker.connection_changed.connect(self._on_connection_changed)
        self._worker.error_occurred.connect(self.error_occurred)
        self._worker.message_received.connect(self.message_received)
        self._worker.firmware_version_received.connect(self.firmware_version_received)
        self._worker.start()

    def disconnect(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
            self._worker = None

    def send_config(self, config: dict):
        if self._worker and self._connected:
            self._worker.send_command(config)
            self.config_sent.emit()

    def refresh_modules(self):
        if self._worker and self._connected:
            self._worker.send_command({"cmd": "discover"})

    def _on_modules_discovered(self, modules: List[ModuleInfo]):
        self._modules = modules
        self.modules_updated.emit(modules)

    def _on_connection_changed(self, connected: bool, port: str):
        self._connected = connected
        self._port = port if connected else ""
        if not connected:
            self._modules = []
        self.connection_changed.emit(connected, port)

    def _scan_ports(self):
        current = set(self.list_ports())
        if current != self._known_ports:
            self._known_ports = current
