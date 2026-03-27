# control_panel/autostart.py -- stub for Wave 0 test scaffolding
import os
import sys
import winreg
from shared.paths import get_config_path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MonitorControl"


def _get_pythonw() -> str:
    raise NotImplementedError


def _build_command() -> str:
    raise NotImplementedError


def is_autostart_enabled() -> bool:
    raise NotImplementedError


def enable_autostart() -> None:
    raise NotImplementedError


def disable_autostart() -> None:
    raise NotImplementedError
