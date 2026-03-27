"""Canonical path resolution for MonitorControl.

All entry points import get_config_path() from here instead of
hard-coding bare "config.json" strings that resolve from the process cwd.
"""
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def get_config_path() -> Path:
    """Return the absolute path to config.json regardless of launch cwd.

    Resolves relative to this file's location (shared/paths.py -> project root).
    Works correctly under pythonw.exe, HKCU Run key launch, and PyInstaller.
    """
    return _PROJECT_ROOT / "config.json"
