# control_panel/autostart.py
"""Read/write HKCU Run registry key for MonitorControl autostart."""
import os
import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MonitorControl"
_COMMAND_FILE = Path(os.environ.get("LOCALAPPDATA", "")) / "MonitorControl" / "host_command.txt"


def _build_command() -> str:
    """Build the Run key command value.

    When running from source: derive from __file__ and write to host_command.txt
    so the packaged exe can reuse it.
    When frozen: read the stored command written by the source installation.
    """
    if getattr(sys, "frozen", False):
        if not _COMMAND_FILE.exists():
            raise RuntimeError(
                "Autostart has not been configured yet.\n\n"
                "Enable autostart once from the Python source installation:\n"
                "  pythonw -m control_panel\n\n"
                "After that, this toggle will work from the packaged exe."
            )
        return _COMMAND_FILE.read_text(encoding="utf-8").strip()

    # Running from source — derive the command and persist it for the exe.
    project_root = Path(__file__).resolve().parent.parent
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    launch_script = project_root / "launch_host.pyw"
    command = f'"{pythonw}" "{launch_script}"'
    _COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COMMAND_FILE.write_text(command, encoding="utf-8")
    return command


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
