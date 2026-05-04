"""Read the current Windows master volume level (0-100).

Uses pycaw's high-level AudioDevice wrapper. Returns -1 on non-Windows
or any failure so the firmware can show "?".
"""
import sys


def get_volume_pct() -> int:
    if sys.platform != "win32":
        return -1
    try:
        from pycaw.pycaw import AudioUtilities

        device = AudioUtilities.GetSpeakers()
        endpoint = device.EndpointVolume
        if endpoint.GetMute():
            return 0
        return int(round(endpoint.GetMasterVolumeLevelScalar() * 100))
    except Exception:
        return -1
