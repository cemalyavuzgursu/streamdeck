"""Read the current Windows master volume level (0-100).

Uses pycaw + the IAudioEndpointVolume COM interface. Returns -1 on
non-Windows or any failure so the firmware can show "?".
"""
import sys


def get_volume_pct() -> int:
    if sys.platform != "win32":
        return -1
    try:
        from ctypes import cast, POINTER
        from comtypes import CLSCTX_ALL
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

        devices = AudioUtilities.GetSpeakers()
        interface = devices.Activate(
            IAudioEndpointVolume._iid_, CLSCTX_ALL, None
        )
        volume = cast(interface, POINTER(IAudioEndpointVolume))
        scalar = volume.GetMasterVolumeLevelScalar()
        # If the system is muted, treat as 0 so the bar matches what
        # the user actually hears.
        if volume.GetMute():
            return 0
        return int(round(scalar * 100))
    except Exception:
        return -1
