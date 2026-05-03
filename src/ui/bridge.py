"""QWebChannel bridge between the React/HTML UI and the Python backend."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from PyQt5.QtCore import QObject, QTimer, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QFileDialog

from src.core.action_executor import ActionExecutor
from src.core.device_manager import DeviceManager
from src.core.firmware_flasher import FirmwareFlasher
from src.core.market_data import MarketFetchWorker, SYMBOL_CATALOG
from src.core.updater import Updater
from src.utils.volume import get_volume_pct
from src.utils.autostart import is_enabled as autostart_is_enabled, set_enabled as autostart_set_enabled
from src.utils.constants import APPDATA_DIR
from src.utils.foreground import get_foreground_process_name


_LAST_CONFIG_PATH = APPDATA_DIR / "last_config.json"


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

    # Auto-connect status pushed to JS so the topbar can render
    # "Bağlı" / "Bağlı değil" without polling.
    device_connection_changed = pyqtSignal(bool, str)

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
        self._cached_profile: Optional[Dict[str, Any]] = self._load_last_config()
        self._all_profiles: list = []
        self._auto_disabled_port: str = ""  # set when user manually disconnects

        # Auto-switch state — last process we evaluated, last manual
        # override timestamp (so a user-driven switch isn't immediately
        # undone by the auto-switcher).
        self._last_proc_name: str = ""
        self._manual_override_until: float = 0.0

        # The firmware has no RTC, so we push the current wall-clock time
        # every 30s. The OLED only redraws if it's in CLOCK mode.
        self._clock_timer = QTimer(self)
        self._clock_timer.setInterval(30_000)
        self._clock_timer.timeout.connect(self._push_clock)
        self._clock_timer.start()

        # On every successful connect: push clock + replay the last config
        # we sent so the OLED comes back to whatever the user had last,
        # even after a power-cycle of the device or a fresh app launch.
        self._device.connection_changed.connect(self._on_connection_changed)

        # Auto-connect: scan every 2s for a likely-ESP port and connect
        # to it if we're not already connected (and the user hasn't
        # manually disconnected from it).
        self._auto_connect_timer = QTimer(self)
        self._auto_connect_timer.setInterval(2_000)
        self._auto_connect_timer.timeout.connect(self._try_auto_connect)
        self._auto_connect_timer.start()
        # Run once immediately so the device picks up on app launch
        # without waiting two seconds.
        QTimer.singleShot(500, self._try_auto_connect)

        # Auto-switch profile based on foreground app + time-of-day rules
        # registered on each profile.
        self._auto_switch_timer = QTimer(self)
        self._auto_switch_timer.setInterval(1_500)
        self._auto_switch_timer.timeout.connect(self._check_auto_switch)
        self._auto_switch_timer.start()

        # Market-data fetcher — refreshes the OLED's crypto/currency/
        # stock view. Multiple symbols can be configured per profile;
        # the rotate timer cycles through them at the user's chosen
        # interval and the fetch happens fresh on each rotation.
        # Workers are kept on a list so the QThread refcount stays
        # alive until the request finishes.
        self._market_target: Optional[Dict[str, Any]] = None
        self._market_index: int = 0
        self._market_workers: list = []
        self._market_rotate_timer = QTimer(self)
        self._market_rotate_timer.setInterval(5_000)
        self._market_rotate_timer.timeout.connect(self._rotate_market)

        # System volume push — when the OLED is in volume mode, we
        # poll the Windows audio endpoint every second and push.
        self._volume_timer = QTimer(self)
        self._volume_timer.setInterval(1_000)
        self._volume_timer.timeout.connect(self._push_volume)
        self._volume_timer.start()

    # ─────────────── Auto-connect / persistence ───────────────
    def _load_last_config(self) -> Optional[Dict[str, Any]]:
        try:
            if _LAST_CONFIG_PATH.exists():
                with open(_LAST_CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_last_config(self) -> None:
        if not self._cached_profile:
            return
        try:
            APPDATA_DIR.mkdir(parents=True, exist_ok=True)
            with open(_LAST_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._cached_profile, f, ensure_ascii=False)
        except Exception:
            pass

    def _try_auto_connect(self) -> None:
        if self._device.is_connected:
            return
        for p in DeviceManager.list_ports_detailed():
            if p.get("is_esp") and p.get("device") != self._auto_disabled_port:
                try:
                    self._device.connect(p["device"])
                except Exception:
                    pass
                return

    def _on_connection_changed(self, connected: bool, port: str) -> None:
        # Always notify JS so the topbar reflects the current state.
        self.device_connection_changed.emit(connected, port)
        if not connected:
            return
        # Re-arm side state so a power-cycle resends the last config.
        QTimer.singleShot(800, self._push_clock)
        QTimer.singleShot(900, self._resend_cached_config)

    def _resend_cached_config(self) -> None:
        if not self._cached_profile or not self._device.is_connected:
            return
        main_mod = next(
            (m for m in self._cached_profile.get("modules", [])
             if (m or {}).get("module_type") == "main"),
            {},
        )
        try:
            self._device.send_config({
                "cmd": "display",
                "profile_name": self._cached_profile.get("name", ""),
                "display_mode": main_mod.get("display_mode", "profile_name"),
                "display_custom_text": main_mod.get("display_custom_text", ""),
            })
        except Exception:
            pass

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

    @pyqtSlot(result=str)
    def get_connection_state(self) -> str:
        """Snapshot for JS components mounting after auto-connect fired."""
        return json.dumps({
            "connected": self._device.is_connected,
            "port": self._device.current_port,
        })

    @pyqtSlot(str, result=bool)
    def connect_device(self, port: str) -> bool:
        # Manual connect re-arms auto-connect for that port.
        if self._auto_disabled_port == port:
            self._auto_disabled_port = ""
        try:
            self._device.connect(port)
            return True
        except Exception:
            return False

    @pyqtSlot(result=bool)
    def disconnect_device(self) -> bool:
        # Disable auto-connect for the current port until the user
        # manually reconnects — otherwise we'd immediately reconnect
        # right after the user clicked disconnect.
        self._auto_disabled_port = self._device.current_port or ""
        self._device.disconnect()
        return True

    @pyqtSlot(str)
    def cache_profile(self, profile_json: str) -> None:
        """Update the local action lookup table without touching the device."""
        try:
            self._cached_profile = json.loads(profile_json)
            self._save_last_config()
        except json.JSONDecodeError:
            pass

    @pyqtSlot(str)
    def cache_profiles(self, profiles_json: str) -> None:
        """Receive the full profile list so auto-switch can find matches."""
        try:
            data = json.loads(profiles_json)
            if isinstance(data, list):
                self._all_profiles = data
        except json.JSONDecodeError:
            pass

    @pyqtSlot()
    def note_manual_switch(self) -> None:
        """User just changed the active profile manually — pause auto-switch
        for ~10 seconds so they don't get yanked back instantly."""
        import time
        self._manual_override_until = time.time() + 10.0

    # ─────────────── Auto-switch ───────────────
    def _time_in_window(self, now, tw: dict) -> bool:
        try:
            frm = tw.get("from", "")
            to = tw.get("to", "")
            if not frm or not to:
                return False
            fh, fm = (int(x) for x in frm.split(":"))
            th, tm = (int(x) for x in to.split(":"))
            cur = now.hour * 60 + now.minute
            a = fh * 60 + fm
            b = th * 60 + tm
            if a <= b:
                return a <= cur < b
            # window wraps midnight (e.g. 22:00 → 02:00)
            return cur >= a or cur < b
        except (ValueError, AttributeError):
            return False

    def _check_auto_switch(self) -> None:
        import time
        if time.time() < self._manual_override_until:
            return
        if not self._all_profiles or not self._cached_profile:
            return
        current_id = str(self._cached_profile.get("id", ""))
        proc = get_foreground_process_name().lower()
        self._last_proc_name = proc
        now = datetime.now()

        for profile in self._all_profiles:
            triggers = (profile or {}).get("triggers") or {}
            apps = [str(a).lower() for a in triggers.get("foreground_apps", []) if a]
            windows = triggers.get("time_windows", []) or []
            if not apps and not windows:
                continue
            target_id = str((profile or {}).get("id", ""))
            if not target_id or target_id == current_id:
                continue
            if proc and apps and proc in apps:
                self.profile_switch_requested.emit(target_id)
                return
            if windows and any(self._time_in_window(now, w) for w in windows):
                self.profile_switch_requested.emit(target_id)
                return

    # ─────────────── Autostart ───────────────
    @pyqtSlot(result=bool)
    def autostart_enabled(self) -> bool:
        return autostart_is_enabled()

    @pyqtSlot(bool, result=bool)
    def autostart_set(self, on: bool) -> bool:
        return autostart_set_enabled(on)

    @pyqtSlot(str, result=bool)
    def send_config(self, profile_json: str) -> bool:
        try:
            profile = json.loads(profile_json)
        except json.JSONDecodeError:
            return False
        # Keep a copy locally — the firmware doesn't run actions itself
        # (ESP32-C3 has no USB HID), so we look up bindings here when
        # a button_event arrives. Persist to disk so a fresh app launch
        # or device replug restores the previous OLED state without the
        # user having to click "Cihaza Gönder" again.
        self._cached_profile = profile
        self._save_last_config()

        main_mod = next(
            (m for m in profile.get("modules", [])
             if (m or {}).get("module_type") == "main"),
            {},
        )
        mode = main_mod.get("display_mode", "profile_name")
        payload = {
            "cmd": "display",
            "profile_name": profile.get("name", ""),
            "display_mode": mode,
            "display_custom_text": main_mod.get("display_custom_text", ""),
            "invert": bool(main_mod.get("display_invert", False)),
        }
        try:
            self._device.send_config(payload)
        except Exception:
            return False
        self._push_clock()

        # Update market-data target when display mode changes. Both
        # display_symbols (new array form) and display_symbol (legacy
        # single value) are accepted.
        if mode in ("crypto", "currency", "stock"):
            symbols = main_mod.get("display_symbols") or []
            if not symbols and main_mod.get("display_symbol"):
                symbols = [main_mod["display_symbol"]]
            symbols = [str(s).strip() for s in symbols if str(s).strip()]
            interval = max(2, int(main_mod.get("display_rotate_seconds") or 5))
            if symbols:
                self._market_target = {
                    "mode": mode, "symbols": symbols, "interval": interval,
                }
                self._market_index = 0
                self._market_rotate_timer.setInterval(interval * 1000)
                # Single symbol → no rotation needed; just fetch once.
                if len(symbols) > 1:
                    self._market_rotate_timer.start()
                else:
                    self._market_rotate_timer.stop()
                self._fetch_market()
            else:
                self._market_target = None
                self._market_rotate_timer.stop()
        else:
            self._market_target = None
            self._market_rotate_timer.stop()
        return True

    def _rotate_market(self) -> None:
        if not self._market_target:
            return
        syms = self._market_target.get("symbols") or []
        if len(syms) <= 1:
            return
        self._market_index = (self._market_index + 1) % len(syms)
        self._fetch_market()

    def _fetch_market(self) -> None:
        if not self._market_target:
            return
        syms = self._market_target.get("symbols") or []
        if not syms:
            return
        idx = self._market_index % len(syms)
        worker = MarketFetchWorker(self._market_target["mode"], syms[idx])
        worker.result.connect(self._on_market_data)
        worker.finished.connect(
            lambda w=worker: self._market_workers.remove(w)
            if w in self._market_workers else None
        )
        self._market_workers.append(worker)
        worker.start()

    def _on_market_data(self, data: dict) -> None:
        if not self._device.is_connected:
            return
        try:
            self._device.send_config({
                "cmd": "market",
                "label": data.get("label", ""),
                "value": data.get("value", ""),
                "change": data.get("change", ""),
                "currency": data.get("currency", ""),
            })
        except Exception:
            pass

    def _push_volume(self) -> None:
        if not self._device.is_connected or not self._cached_profile:
            return
        main_mod = next(
            (m for m in self._cached_profile.get("modules", [])
             if (m or {}).get("module_type") == "main"),
            None,
        )
        if not main_mod or main_mod.get("display_mode") != "volume":
            return
        v = get_volume_pct()
        if v < 0:
            return
        try:
            self._device.send_config({"cmd": "volume", "level": v})
        except Exception:
            pass

    @pyqtSlot(str, result=str)
    def list_market_symbols(self, mode: str) -> str:
        """Return JSON list of {symbol, name} for the given market mode."""
        items = SYMBOL_CATALOG.get(mode, [])
        return json.dumps([{"symbol": s, "name": n} for s, n in items])

    @pyqtSlot(result=int)
    def get_system_volume(self) -> int:
        return get_volume_pct()

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
            None, "Uygulama seç", "", "Çalıştırılabilir (*.exe *.lnk);;All files (*.*)"
        )
        return path or ""

    @pyqtSlot(result=str)
    def list_installed_apps(self) -> str:
        """Scan Start Menu directories for .lnk shortcuts.

        Each shortcut is launched via os.startfile in ActionExecutor,
        which lets Windows resolve the target — so we don't need to
        parse .lnk binary format ourselves.
        """
        import os
        from pathlib import Path
        roots = []
        pd = os.environ.get("PROGRAMDATA")
        if pd:
            roots.append(Path(pd) / "Microsoft" / "Windows" / "Start Menu" / "Programs")
        ad = os.environ.get("APPDATA")
        if ad:
            roots.append(Path(ad) / "Microsoft" / "Windows" / "Start Menu" / "Programs")

        # Folders to ignore (system clutter)
        skip_keywords = ("uninstall", "kaldır", "yardım", "help", "readme")
        seen = {}
        for base in roots:
            if not base.exists():
                continue
            for lnk in base.rglob("*.lnk"):
                name = lnk.stem
                low = name.lower()
                if any(kw in low for kw in skip_keywords):
                    continue
                if name not in seen:
                    seen[name] = str(lnk)

        items = sorted(
            ({"name": n, "path": p} for n, p in seen.items()),
            key=lambda x: x["name"].lower(),
        )
        return json.dumps(items)

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
