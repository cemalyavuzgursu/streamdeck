"""Executes a configured macropad action on the host PC.

ESP32-C3's USB peripheral can't act as an HID device, so the firmware
sends raw button events over USB CDC and this module performs the
actual key injection / app launch on the host.
"""
import shlex
import subprocess
import time
from typing import Any, Dict, Optional

try:
    from pynput.keyboard import Controller, Key
    _HAVE_PYNPUT = True
except ImportError:
    _HAVE_PYNPUT = False
    Controller = None  # type: ignore
    Key = None  # type: ignore


def _build_key_map():
    if not _HAVE_PYNPUT:
        return {}
    m = {
        "ctrl": Key.ctrl_l,
        "control": Key.ctrl_l,
        "alt": Key.alt_l,
        "shift": Key.shift_l,
        "win": Key.cmd,
        "gui": Key.cmd,
        "cmd": Key.cmd,
        "esc": Key.esc,
        "escape": Key.esc,
        "enter": Key.enter,
        "return": Key.enter,
        "tab": Key.tab,
        "backspace": Key.backspace,
        "space": Key.space,
        "left": Key.left,
        "right": Key.right,
        "up": Key.up,
        "down": Key.down,
        "delete": Key.delete,
        "del": Key.delete,
        "insert": Key.insert,
        "home": Key.home,
        "end": Key.end,
        "pageup": Key.page_up,
        "pagedown": Key.page_down,
    }
    for i in range(1, 13):
        m[f"f{i}"] = getattr(Key, f"f{i}")
    return m


def _build_media_map():
    if not _HAVE_PYNPUT:
        return {}
    return {
        "play_pause": Key.media_play_pause,
        "next_track": Key.media_next,
        "prev_track": Key.media_previous,
        "volume_up": Key.media_volume_up,
        "volume_down": Key.media_volume_down,
        "mute": Key.media_volume_mute,
    }


_KEY_MAP = _build_key_map()
_MEDIA_MAP = _build_media_map()


class ActionExecutor:
    def __init__(self):
        self._kbd: Optional[Controller] = Controller() if _HAVE_PYNPUT else None

    @property
    def has_keyboard(self) -> bool:
        return self._kbd is not None

    def execute(self, action_type: str, action_data: Dict[str, Any]) -> str:
        """Execute an action, return a short human-readable status string."""
        action_data = action_data or {}
        if action_type == "shortcut":
            keys = action_data.get("keys", "")
            return self._send_shortcut(keys)
        if action_type == "media":
            return self._send_media(action_data.get("action", ""))
        if action_type == "app_launch":
            return self._launch_app(
                action_data.get("path", ""),
                action_data.get("args", "") or "",
            )
        if action_type == "macro":
            return self._run_macro(action_data.get("sequence", "") or "")
        if action_type in ("none", ""):
            return "no action"
        return f"unsupported: {action_type}"

    # ─────── shortcut ───────
    def _send_shortcut(self, keys: str) -> str:
        if not keys or not self._kbd:
            return "no shortcut"
        parts = [p.strip().lower() for p in keys.split("+") if p.strip()]
        resolved = []
        for p in parts:
            mapped = _KEY_MAP.get(p)
            if mapped is not None:
                resolved.append(mapped)
            elif len(p) == 1:
                resolved.append(p)
        if not resolved:
            return f"unknown keys: {keys}"
        for k in resolved:
            self._kbd.press(k)
        for k in reversed(resolved):
            self._kbd.release(k)
        return f"shortcut {keys}"

    # ─────── media ───────
    def _send_media(self, action: str) -> str:
        if not self._kbd:
            return "no kbd"
        key = _MEDIA_MAP.get(action)
        if not key:
            return f"unknown media: {action}"
        self._kbd.press(key)
        self._kbd.release(key)
        return f"media {action}"

    # ─────── app launch ───────
    def _launch_app(self, path: str, args: str) -> str:
        if not path:
            return "no path"
        try:
            cmd = [path] + (shlex.split(args) if args else [])
            subprocess.Popen(cmd, close_fds=True)
            return f"launched {path}"
        except Exception as e:
            return f"launch failed: {e}"

    # ─────── macro ───────
    def _run_macro(self, sequence: str) -> str:
        if not self._kbd:
            return "no kbd"
        for line in sequence.splitlines():
            line = line.strip()
            if not line:
                continue
            if line.startswith("wait:"):
                try:
                    time.sleep(int(line[5:]) / 1000.0)
                except ValueError:
                    pass
            elif line.startswith("type:"):
                self._kbd.type(line[5:])
            else:
                self._send_shortcut(line)
        return "macro done"
