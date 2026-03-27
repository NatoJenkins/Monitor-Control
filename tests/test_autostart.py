"""Tests for control_panel/autostart.py — registry read/write/delete."""
import unittest
from unittest.mock import patch, MagicMock
import pytest


# ---------------------------------------------------------------------------
# Tests for is_autostart_enabled
# ---------------------------------------------------------------------------

@patch("control_panel.autostart.winreg")
def test_is_autostart_enabled_true(mock_winreg):
    """Returns True when QueryValueEx succeeds (entry present)."""
    from control_panel.autostart import is_autostart_enabled

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    mock_winreg.QueryValueEx.return_value = ("some_value", 1)

    assert is_autostart_enabled() is True


@patch("control_panel.autostart.winreg")
def test_is_autostart_enabled_false(mock_winreg):
    """Returns False when QueryValueEx raises FileNotFoundError (entry absent)."""
    from control_panel.autostart import is_autostart_enabled

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    mock_winreg.QueryValueEx.side_effect = FileNotFoundError()

    assert is_autostart_enabled() is False


@patch("control_panel.autostart.winreg")
def test_is_autostart_enabled_oserror_returns_false(mock_winreg):
    """Returns False when QueryValueEx raises OSError (permission error etc.)."""
    from control_panel.autostart import is_autostart_enabled

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    mock_winreg.QueryValueEx.side_effect = OSError("permission denied")

    assert is_autostart_enabled() is False


# ---------------------------------------------------------------------------
# Tests for enable_autostart
# ---------------------------------------------------------------------------

@patch("control_panel.autostart.winreg")
def test_enable_autostart_calls_set_value_ex(mock_winreg):
    """enable_autostart() calls SetValueEx once with correct value name and REG_SZ type."""
    from control_panel.autostart import enable_autostart

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    mock_winreg.REG_SZ = 1

    enable_autostart()

    mock_winreg.SetValueEx.assert_called_once()
    call_args = mock_winreg.SetValueEx.call_args[0]
    # call_args: (key, value_name, reserved, reg_type, data)
    assert call_args[1] == "MonitorControl"
    assert call_args[3] == mock_winreg.REG_SZ
    assert isinstance(call_args[4], str)


# ---------------------------------------------------------------------------
# Tests for disable_autostart
# ---------------------------------------------------------------------------

@patch("control_panel.autostart.winreg")
def test_disable_autostart_calls_delete_value(mock_winreg):
    """disable_autostart() calls DeleteValue once with value name 'MonitorControl'."""
    from control_panel.autostart import disable_autostart

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)

    disable_autostart()

    mock_winreg.DeleteValue.assert_called_once()
    call_args = mock_winreg.DeleteValue.call_args[0]
    assert call_args[1] == "MonitorControl"


@patch("control_panel.autostart.winreg")
def test_disable_autostart_noop_when_absent(mock_winreg):
    """disable_autostart() silently no-ops when DeleteValue raises FileNotFoundError."""
    from control_panel.autostart import disable_autostart

    mock_key = MagicMock()
    mock_winreg.OpenKey.return_value.__enter__ = MagicMock(return_value=mock_key)
    mock_winreg.OpenKey.return_value.__exit__ = MagicMock(return_value=False)
    mock_winreg.DeleteValue.side_effect = FileNotFoundError()

    # Should not raise
    disable_autostart()


# ---------------------------------------------------------------------------
# Tests for _build_command
# ---------------------------------------------------------------------------

@patch("control_panel.autostart.sys")
def test_build_command_uses_pythonw(mock_sys):
    """_build_command() uses pythonw.exe (not python.exe) as the interpreter."""
    from control_panel.autostart import _build_command

    mock_sys.executable = r"C:\Python311\python.exe"

    result = _build_command()

    assert "pythonw.exe" in result
    # The interpreter path should be pythonw.exe, not python.exe as the interpreter
    # Verify "python.exe" does not appear as the executable (only pythonw.exe should)
    assert result.count("python.exe") == 0


def test_build_command_contains_launch_script():
    """_build_command() result contains 'launch_host.pyw'."""
    from control_panel.autostart import _build_command

    result = _build_command()
    assert "launch_host.pyw" in result


def test_build_command_quotes_paths():
    """_build_command() result has two individually double-quoted paths."""
    from control_panel.autostart import _build_command

    result = _build_command()

    # Pattern: starts with '"', contains '" "' separator, ends with '"'
    assert result.startswith('"')
    assert '" "' in result
    assert result.endswith('"')
