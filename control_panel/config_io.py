"""Atomic config I/O for the control panel.

The control panel is the sole writer of config.json. It writes atomically
via tempfile.mkstemp (in the same directory as the target) followed by
os.replace, which is guaranteed atomic on POSIX and best-effort on Windows.
"""
import json
import os
import tempfile


DEFAULT_CONFIG = {
    "layout": {
        "display": {"width": 1920, "height": 515}
    },
    "game_mode": False,
    "widgets": []
}


def load_config(path: str) -> dict:
    """Load config from path. Returns DEFAULT_CONFIG if file missing."""
    path = os.path.abspath(path)
    if not os.path.exists(path):
        return dict(DEFAULT_CONFIG)  # shallow copy sufficient for flat structure
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def atomic_write_config(path: str, data: dict) -> None:
    """Write data to path atomically via temp file + os.replace.

    The temp file is created in the same directory as the target so that
    os.replace operates within a single filesystem (avoiding cross-device
    moves). On error, the temp file is removed before re-raising.
    """
    path = os.path.abspath(path)
    dir_path = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # fd is closed by the context manager — safe to replace on Windows
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def write_pomodoro_command(config_dir: str, command: str) -> None:
    """Write a Pomodoro control command atomically.

    Writes {"cmd": command} to pomodoro_command.json in config_dir.
    The host's QFileSystemWatcher picks up the change, forwards it
    as a ControlSignal, and deletes the file.
    """
    cmd_path = os.path.join(os.path.abspath(config_dir), "pomodoro_command.json")
    dir_path = os.path.dirname(cmd_path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"cmd": command}, f)
        os.replace(tmp_path, cmd_path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
