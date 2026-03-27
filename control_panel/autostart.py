# control_panel/autostart.py
"""Manage MonitorControl autostart via the Windows Startup folder.

Uses a .lnk shortcut in shell:startup rather than HKCU\Run because
Windows 11 has known reliability issues with the Run + StartupApproved
registry mechanism (profile corruption from KB updates, dynamic
idle-wait delays, Settings app overriding enabled state).

The Startup folder approach is processed by a different Explorer code
path and is not subject to these issues.
"""
import os
import subprocess
import sys
from pathlib import Path

_STARTUP_FOLDER = (
    Path(os.environ.get("APPDATA", ""))
    / "Microsoft"
    / "Windows"
    / "Start Menu"
    / "Programs"
    / "Startup"
)
_SHORTCUT_NAME = "MonitorControl.lnk"
_SHORTCUT_PATH = _STARTUP_FOLDER / _SHORTCUT_NAME
_COMMAND_FILE = (
    Path(os.environ.get("LOCALAPPDATA", "")) / "MonitorControl" / "host_command.txt"
)


def _get_pythonw_and_script() -> tuple[str, str]:
    """Return (pythonw_path, launch_script_path).

    When running from source: derive from __file__ and persist for the exe.
    When frozen: read stored paths from host_command.txt.
    """
    if getattr(sys, "frozen", False):
        if not _COMMAND_FILE.exists():
            raise RuntimeError(
                "Autostart has not been configured yet.\n\n"
                "Enable autostart once from the Python source installation:\n"
                "  pythonw -m control_panel\n\n"
                "After that, this toggle will work from the packaged exe."
            )
        parts = _COMMAND_FILE.read_text(encoding="utf-8").strip().split('" "')
        pythonw = parts[0].strip('"')
        script = parts[1].strip('"') if len(parts) > 1 else ""
        return pythonw, script

    project_root = Path(__file__).resolve().parent.parent
    pythonw = str(Path(sys.executable).with_name("pythonw.exe"))
    launch_script = str(project_root / "launch_host.pyw")
    # Persist for the packaged exe.
    _COMMAND_FILE.parent.mkdir(parents=True, exist_ok=True)
    _COMMAND_FILE.write_text(f'"{pythonw}" "{launch_script}"', encoding="utf-8")
    return pythonw, launch_script


def _create_shortcut(target: str, arguments: str, working_dir: str) -> None:
    """Create a .lnk shortcut via PowerShell (no extra Python deps)."""
    ps_script = (
        f'$ws = New-Object -ComObject WScript.Shell; '
        f'$s = $ws.CreateShortcut("{_SHORTCUT_PATH}"); '
        f'$s.TargetPath = "{target}"; '
        f'$s.Arguments = \'"{arguments}"\'; '
        f'$s.WorkingDirectory = "{working_dir}"; '
        f'$s.WindowStyle = 7; '
        f'$s.Save()'
    )
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_script],
        check=True,
        capture_output=True,
    )


def is_autostart_enabled() -> bool:
    """Return True if the MonitorControl startup shortcut exists."""
    return _SHORTCUT_PATH.exists()


def enable_autostart() -> None:
    """Create a MonitorControl.lnk shortcut in the Startup folder."""
    pythonw, script = _get_pythonw_and_script()
    working_dir = str(Path(script).parent)
    _create_shortcut(pythonw, script, working_dir)
    _cleanup_registry()


def disable_autostart() -> None:
    """Remove the startup shortcut. No-ops if absent."""
    try:
        _SHORTCUT_PATH.unlink()
    except FileNotFoundError:
        pass
    _cleanup_registry()


def _cleanup_registry() -> None:
    """Remove stale HKCU Run entries from previous approach."""
    import winreg

    run_key = r"Software\Microsoft\Windows\CurrentVersion\Run"
    approved_key = (
        r"Software\Microsoft\Windows\CurrentVersion\Explorer\StartupApproved\Run"
    )
    name = "MonitorControl"

    for key_path in (run_key,):
        try:
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE
            ) as key:
                winreg.DeleteValue(key, name)
        except (FileNotFoundError, OSError):
            pass

    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, approved_key, 0, winreg.KEY_WRITE
        ) as key:
            winreg.DeleteValue(key, name)
    except (FileNotFoundError, OSError):
        pass
