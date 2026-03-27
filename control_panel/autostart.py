# control_panel/autostart.py
"""Read/write HKCU Run registry key for MonitorControl autostart."""
import os
import sys
import winreg
from shared.paths import get_config_path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MonitorControl"


def _get_pythonw() -> str:
    """Return the absolute path to pythonw.exe alongside the running python.exe."""
    return os.path.join(os.path.dirname(sys.executable), "pythonw.exe")


def _build_command() -> str:
    """Build the Run key command value: quoted pythonw.exe + quoted launch_host.pyw."""
    pythonw = _get_pythonw()
    project_root = str(get_config_path().parent)
    launch_script = os.path.join(project_root, "launch_host.pyw")
    return f'"{pythonw}" "{launch_script}"'


def is_autostart_enabled() -> bool:
    """Return True if the MonitorControl HKCU Run entry exists."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable_autostart() -> None:
    """Write the MonitorControl entry to HKCU Run."""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_WRITE
    ) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _build_command())


def disable_autostart() -> None:
    """Remove the MonitorControl entry from HKCU Run. No-ops if absent."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass  # Already absent -- no-op is correct
