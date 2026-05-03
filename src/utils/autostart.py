"""Windows autostart toggle via the per-user Run registry key.

Adds/removes HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run\\MacroPad,
pointing at the running .exe with --tray so the app starts hidden in the
system tray on login.

Source-mode runs (python src/main.py) refuse to register because the
registry would point to python.exe and that's not what the user wants.
"""
import sys

_KEY_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MacroPad"


def _is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def is_enabled() -> bool:
    if sys.platform != "win32":
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _KEY_PATH) as k:
            v, _ = winreg.QueryValueEx(k, _VALUE_NAME)
            return bool(v)
    except (FileNotFoundError, OSError):
        return False


def set_enabled(enabled: bool) -> bool:
    if sys.platform != "win32":
        return False
    if not _is_frozen():
        # Don't pin python.exe to autostart for source-mode dev runs.
        return False
    try:
        import winreg
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _KEY_PATH) as k:
            if enabled:
                exe = sys.executable
                cmd = f'"{exe}" --tray'
                winreg.SetValueEx(k, _VALUE_NAME, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(k, _VALUE_NAME)
                except FileNotFoundError:
                    pass
        return True
    except OSError:
        return False
