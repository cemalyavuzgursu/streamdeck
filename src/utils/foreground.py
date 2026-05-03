"""Helpers for detecting the currently focused application on Windows.

Used by the auto-switch feature: when the active foreground process name
matches a trigger registered on a profile, the bridge fires a
profile_switch_requested so the UI flips to that profile (and the
device's OLED follows).
"""
import sys


def get_foreground_process_name() -> str:
    """Return the executable name (e.g. "spotify.exe") of the foreground
    window's owning process, or empty string on failure / non-Windows."""
    if sys.platform != "win32":
        return ""
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32

        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return ""

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        if not pid.value:
            return ""

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        h_proc = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not h_proc:
            return ""

        try:
            buf = ctypes.create_unicode_buffer(512)
            size = wintypes.DWORD(len(buf))
            if kernel32.QueryFullProcessImageNameW(
                h_proc, 0, buf, ctypes.byref(size)
            ):
                full = buf.value
                return full.rsplit("\\", 1)[-1]
        finally:
            kernel32.CloseHandle(h_proc)
    except Exception:
        pass
    return ""
