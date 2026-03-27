"""Canonical path resolution for MonitorControl.

All entry points import get_config_path() from here instead of
hard-coding bare "config.json" strings that resolve from the process cwd.
"""
import os
import shutil
from pathlib import Path


def get_config_path() -> Path:
    """Return the absolute path to config.json in the user's AppData directory.

    Uses %LOCALAPPDATA%\\MonitorControl\\config.json so that the packaged
    .exe and the Python host always share the same file regardless of their
    working directories.

    On first call, creates the directory and migrates config.json from the
    project root if it exists there but not yet in AppData.
    """
    config_dir = Path(os.environ["LOCALAPPDATA"]) / "MonitorControl"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / "config.json"

    # One-time migration: copy project-root config.json to AppData on first run.
    if not config_path.exists():
        _project_root = Path(__file__).resolve().parent.parent
        legacy = _project_root / "config.json"
        if legacy.exists():
            shutil.copy2(str(legacy), str(config_path))

    return config_path
