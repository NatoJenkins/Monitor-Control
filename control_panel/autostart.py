# control_panel/autostart.py
"""Read/write HKCU Run registry key for MonitorControl autostart."""
import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MonitorControl"


def _build_command() -> str:
    """Build the Run key command value: quoted pythonw.exe + quoted launch_host.pyw."""
    if getattr(sys, "frozen", False):
        raise RuntimeError(
            "Autostart must be configured from the Python source installation — "
            "the packaged control panel cannot locate launch_host.pyw."
        )
    # autostart.py lives at <project_root>/control_panel/autostart.py
    project_root = Path(__file__).resolve().parent.parent
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launch_script = project_root / "launch_host.pyw"
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
