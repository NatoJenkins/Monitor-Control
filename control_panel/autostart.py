# control_panel/autostart.py
"""Read/write HKCU Run registry key for MonitorControl autostart."""
import os
import sys
import winreg
from pathlib import Path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_STARTUP_APPROVED_KEY = (
    r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
)
_VALUE_NAME = "MonitorControl"
_COMMAND_FILE = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "MonitorControl" / "host_command.txt"
)

# 12-byte binary values for StartupApproved\Run.
# Format: 4-byte DWORD status + 8-byte FILETIME (zeros = no timestamp).
# Even first byte = enabled, odd = disabled.
_APPROVED_ENABLED = b"\x02\x00\x00\x00" + b"\x00" * 8
_APPROVED_DISABLED = b"\x03\x00\x00\x00" + b"\x00" * 8


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
    """Return True if the MonitorControl HKCU Run entry exists and is approved."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
    except (FileNotFoundError, OSError):
        return False

    # If StartupApproved entry exists, check that it's enabled (even first byte).
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_APPROVED_KEY
        ) as key:
            data, _ = winreg.QueryValueEx(key, _VALUE_NAME)
            if isinstance(data, bytes) and len(data) >= 1 and data[0] % 2 != 0:
                return False  # Odd first byte = disabled
    except (FileNotFoundError, OSError):
        pass  # No StartupApproved entry — Run key alone is sufficient

    return True


def enable_autostart() -> None:
    """Write the MonitorControl entry to HKCU Run and mark as approved."""
    command = _build_command()
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_WRITE
    ) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, command)

    # Also write StartupApproved so Windows doesn't block execution.
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _STARTUP_APPROVED_KEY, 0, winreg.KEY_WRITE
    ) as key:
        winreg.SetValueEx(
            key, _VALUE_NAME, 0, winreg.REG_BINARY, _APPROVED_ENABLED
        )


def disable_autostart() -> None:
    """Remove the MonitorControl entry from HKCU Run. No-ops if absent."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass  # Already absent

    # Also mark as disabled in StartupApproved (don't delete — Windows
    # recreates it on next Settings/TaskManager visit and may pick a
    # stale state).
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _STARTUP_APPROVED_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.SetValueEx(
                key, _VALUE_NAME, 0, winreg.REG_BINARY, _APPROVED_DISABLED
            )
    except FileNotFoundError:
        pass  # Key doesn't exist yet — nothing to disable
