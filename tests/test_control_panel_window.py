"""Tests for control_panel/main_window.py — ControlPanelWindow UI."""
import json
from unittest.mock import patch
import pytest
from PyQt6.QtWidgets import QMainWindow, QTabWidget, QSpinBox, QComboBox, QPushButton, QLineEdit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_minimal_config(path):
    """Write a minimal config.json to the given path (pathlib.Path)."""
    config = {
        "layout": {"display": {"width": 1920, "height": 515}},
        "widgets": [
            {
                "id": "pomodoro-1",
                "type": "pomodoro",
                "x": 0, "y": 0, "width": 400, "height": 515,
                "settings": {
                    "work_minutes": 30,
                    "short_break_minutes": 5,
                    "long_break_minutes": 15,
                    "cycles_before_long_break": 4,
                }
            },
            {
                "id": "calendar-1",
                "type": "calendar",
                "x": 400, "y": 0, "width": 400, "height": 515,
                "settings": {
                    "clock_format": "12h"
                }
            },
        ]
    }
    (path / "config.json").write_text(json.dumps(config), encoding="utf-8")
    return str(path / "config.json")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_window_is_qmainwindow(qapp, tmp_path):
    """ControlPanelWindow is a QMainWindow subclass."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)
    assert isinstance(window, QMainWindow)
    window.close()


def test_window_title(qapp, tmp_path):
    """Window title is 'MonitorControl — Settings'."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)
    assert window.windowTitle() == "MonitorControl \u2014 Settings"
    window.close()


def test_tabs_present(qapp, tmp_path):
    """QTabWidget has 5 tabs: Layout, Pomodoro, Calendar, Notification, Shortcuts."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    tabs = window._tabs
    assert isinstance(tabs, QTabWidget)
    assert tabs.count() == 5
    assert tabs.tabText(0) == "Layout"
    assert tabs.tabText(1) == "Pomodoro"
    assert tabs.tabText(2) == "Calendar"
    assert tabs.tabText(3) == "Notification"
    assert tabs.tabText(4) == "Shortcuts"
    window.close()


def test_pomodoro_fields_present(qapp, tmp_path):
    """Pomodoro tab has QSpinBox fields with correct names and ranges."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    assert isinstance(window._pomo_work, QSpinBox)
    assert window._pomo_work.minimum() == 1
    assert window._pomo_work.maximum() == 120

    assert isinstance(window._pomo_short_break, QSpinBox)
    assert window._pomo_short_break.minimum() == 1
    assert window._pomo_short_break.maximum() == 30

    assert isinstance(window._pomo_long_break, QSpinBox)
    assert window._pomo_long_break.minimum() == 1
    assert window._pomo_long_break.maximum() == 60

    assert isinstance(window._pomo_cycles, QSpinBox)
    assert window._pomo_cycles.minimum() == 1
    assert window._pomo_cycles.maximum() == 10
    window.close()


def test_calendar_clock_format_field(qapp, tmp_path):
    """Calendar tab has QComboBox for clock_format with items '12h' and '24h'."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    combo = window._clock_format
    assert isinstance(combo, QComboBox)
    assert combo.count() == 2
    assert combo.itemText(0) == "12h"
    assert combo.itemText(1) == "24h"
    window.close()


def test_save_button_exists(qapp, tmp_path):
    """Save button (_save_btn) exists with text 'Save'."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    assert isinstance(window._save_btn, QPushButton)
    assert window._save_btn.text() == "Save"
    window.close()


def test_save_writes_config(qapp, tmp_path):
    """Clicking save writes valid JSON to config file."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    window._save_btn.click()

    config_file = tmp_path / "config.json"
    assert config_file.exists()
    with open(config_file, encoding="utf-8") as f:
        data = json.load(f)
    assert "layout" in data
    assert "widgets" in data
    window.close()


def test_load_values_populates_fields(qapp, tmp_path):
    """Window loads config values into form fields at startup."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    # The minimal config has work_minutes=30
    window = ControlPanelWindow(config_path=config_path)

    assert window._pomo_work.value() == 30
    window.close()


def test_pomodoro_controls_exist(qapp, tmp_path):
    """Pomodoro tab has Start, Pause, Reset QPushButton controls."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    assert isinstance(window._pomo_start_btn, QPushButton)
    assert window._pomo_start_btn.text() == "Start"
    assert isinstance(window._pomo_pause_btn, QPushButton)
    assert window._pomo_pause_btn.text() == "Pause"
    assert isinstance(window._pomo_reset_btn, QPushButton)
    assert window._pomo_reset_btn.text() == "Reset"
    window.close()


def test_pomodoro_font_selector(qapp, tmp_path):
    """Pomodoro tab has font QComboBox with correct items."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    assert isinstance(window._pomo_font, QComboBox)
    font_items = [window._pomo_font.itemText(i) for i in range(window._pomo_font.count())]
    assert "Inter" in font_items
    assert "Digital-7" in font_items
    assert "Share Tech Mono" in font_items
    window.close()


def test_pomodoro_accent_colors_load(qapp, tmp_path):
    """Accent color QLineEdits are populated from config at startup."""
    from control_panel.main_window import ControlPanelWindow

    config = {
        "layout": {"display": {"width": 1920, "height": 515}},
        "widgets": [
            {
                "id": "pomodoro-1",
                "type": "pomodoro",
                "x": 0, "y": 0, "width": 400, "height": 515,
                "settings": {
                    "work_minutes": 25,
                    "short_break_minutes": 5,
                    "long_break_minutes": 15,
                    "cycles_before_long_break": 4,
                    "work_accent_color": "#aabbcc",
                    "short_break_accent_color": "#112233",
                    "long_break_accent_color": "#445566",
                }
            },
            {
                "id": "calendar-1",
                "type": "calendar",
                "x": 400, "y": 0, "width": 400, "height": 515,
                "settings": {"clock_format": "24h"}
            },
        ]
    }
    config_path = str(tmp_path / "config.json")
    (tmp_path / "config.json").write_text(json.dumps(config), encoding="utf-8")

    window = ControlPanelWindow(config_path=config_path)

    assert window._pomo_work_color.text() == "#aabbcc"
    assert window._pomo_short_break_color.text() == "#112233"
    assert window._pomo_long_break_color.text() == "#445566"
    window.close()


def test_calendar_font_selector(qapp, tmp_path):
    """Calendar tab has font QComboBox with correct items."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    assert isinstance(window._cal_font, QComboBox)
    font_items = [window._cal_font.itemText(i) for i in range(window._cal_font.count())]
    assert "Inter" in font_items
    assert "Digital-7" in font_items
    assert "Share Tech Mono" in font_items
    window.close()


def test_shortcuts_tab_exists(qapp, tmp_path):
    """Shortcuts tab exists with QLineEdit fields for start/pause/reset."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    assert isinstance(window._shortcut_start_edit, QLineEdit)
    assert isinstance(window._shortcut_pause_edit, QLineEdit)
    assert isinstance(window._shortcut_reset_edit, QLineEdit)
    window.close()


def test_collect_config_includes_new_fields(qapp, tmp_path):
    """_collect_config returns font, accent colors, and shortcuts keys."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    config = window._collect_config()

    # Pomodoro settings should include font and accent colors
    pomo_settings = next(
        w["settings"] for w in config["widgets"] if w["type"] == "pomodoro"
    )
    assert "font" in pomo_settings
    assert "work_accent_color" in pomo_settings
    assert "short_break_accent_color" in pomo_settings
    assert "long_break_accent_color" in pomo_settings

    # Calendar settings should include font
    cal_settings = next(
        w["settings"] for w in config["widgets"] if w["type"] == "calendar"
    )
    assert "font" in cal_settings

    # Shortcuts at top level
    assert "shortcuts" in config
    assert "pomodoro_start" in config["shortcuts"]
    assert "pomodoro_pause" in config["shortcuts"]
    assert "pomodoro_reset" in config["shortcuts"]
    window.close()


def test_send_pomo_command_writes_file(qapp, tmp_path):
    """Clicking Start button calls write_pomodoro_command with 'start'."""
    from control_panel.main_window import ControlPanelWindow

    config_path = _write_minimal_config(tmp_path)
    window = ControlPanelWindow(config_path=config_path)

    with patch("control_panel.main_window.write_pomodoro_command") as mock_write:
        window._pomo_start_btn.click()
        mock_write.assert_called_once()
        args = mock_write.call_args[0]
        assert args[1] == "start"

    window.close()
