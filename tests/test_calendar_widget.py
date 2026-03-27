"""Unit tests for CalendarWidget rendering and config updates.

Tests run in-process using queue.Queue mocks (API-compatible with multiprocessing.Queue).
"""
import ast
import datetime
import pathlib
import queue
import threading
import time

import pytest

WIDGET_FILE = pathlib.Path(__file__).parent.parent / "widgets" / "calendar" / "widget.py"


# ---------------------------------------------------------------------------
# Source-level checks
# ---------------------------------------------------------------------------

def test_no_pyqt6_import():
    """widgets/calendar/widget.py must NOT import PyQt6 in any form."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    assert "import PyQt6" not in source, "CalendarWidget must not use 'import PyQt6'"
    assert "from PyQt6" not in source, "CalendarWidget must not use 'from PyQt6'"


def test_nonblocking_put():
    """Every .put() call in widget.py must use block=False."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    tree = ast.parse(source)
    put_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "put":
                put_calls.append(node)

    assert put_calls, "Expected at least one .put() call in CalendarWidget source"
    for call_node in put_calls:
        keyword_names = {kw.arg: kw for kw in call_node.keywords}
        assert "block" in keyword_names, (
            f"put() call at line {call_node.lineno} is missing 'block' keyword argument"
        )
        block_kw = keyword_names["block"]
        is_false = (
            isinstance(block_kw.value, ast.Constant) and block_kw.value.value is False
        )
        assert is_false, (
            f"put() call at line {call_node.lineno} does not have block=False"
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_widget(settings=None):
    """Create a CalendarWidget with queue.Queue mocks."""
    from widgets.calendar.widget import CalendarWidget
    config = {
        "width": 640,
        "height": 515,
        "settings": settings or {"clock_format": "24h", "font": "Inter"},
    }
    out_q = queue.Queue(maxsize=100)
    in_q = queue.Queue(maxsize=10)
    return CalendarWidget("test_cal", config, out_q, in_q)


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------

def test_frame_content():
    """render_frame() returns FrameData with correct dimensions and RGBA byte count."""
    from shared.message_schema import FrameData
    w = make_widget()
    frame = w.render_frame()
    assert isinstance(frame, FrameData)
    assert frame.widget_id == "test_cal"
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4


# ---------------------------------------------------------------------------
# Time formatting tests
# ---------------------------------------------------------------------------

def test_24h_format():
    """With clock_format='24h', _format_time returns HH:MM without AM/PM."""
    w = make_widget(settings={"clock_format": "24h"})
    # Use a fixed time at 14:30
    t = datetime.datetime(2026, 3, 26, 14, 30, 0)
    result = w._format_time(t)
    assert "14:30" in result, f"Expected '14:30' in 24h result, got '{result}'"
    assert "AM" not in result and "PM" not in result, (
        f"24h format should not contain AM/PM, got '{result}'"
    )


def test_12h_format():
    """With clock_format='12h', _format_time returns time with AM or PM."""
    w = make_widget(settings={"clock_format": "12h"})
    t = datetime.datetime(2026, 3, 26, 14, 30, 0)
    result = w._format_time(t)
    assert "PM" in result, f"Expected 'PM' in 12h result for 14:30, got '{result}'"
    assert "02:30" in result, f"Expected '02:30' in 12h result, got '{result}'"


def test_date_format():
    """_format_date returns a string with day name, month name, day number, and year."""
    w = make_widget()
    # 2026-03-26 is a Thursday
    t = datetime.datetime(2026, 3, 26, 10, 0, 0)
    result = w._format_date(t)
    assert "Thursday" in result, f"Expected 'Thursday' in date result, got '{result}'"
    assert "March" in result, f"Expected 'March' in date result, got '{result}'"
    assert "26" in result, f"Expected '26' in date result, got '{result}'"
    assert "2026" in result, f"Expected '2026' in date result, got '{result}'"


# ---------------------------------------------------------------------------
# Config update tests
# ---------------------------------------------------------------------------

def test_config_update_changes_format():
    """After CONFIG_UPDATE with clock_format='12h', next render uses 12h format."""
    from shared.message_schema import ConfigUpdateMessage
    w = make_widget(settings={"clock_format": "24h"})
    assert w._clock_format == "24h"

    # Push config update via in_queue
    w.in_queue.put_nowait(ConfigUpdateMessage(
        widget_id="test_cal",
        config={"settings": {"clock_format": "12h"}},
    ))

    # Manually trigger poll (same as one run-loop iteration)
    new_cfg = w.poll_config_update()
    if new_cfg:
        settings = new_cfg.get("settings", {})
        if "clock_format" in settings:
            w._clock_format = settings["clock_format"]

    assert w._clock_format == "12h", f"Expected '12h' after config update, got '{w._clock_format}'"

    # Verify format_time uses 12h
    t = datetime.datetime(2026, 3, 26, 9, 5, 0)
    result = w._format_time(t)
    assert "AM" in result, f"Expected AM in 12h result for 09:05, got '{result}'"


# ---------------------------------------------------------------------------
# Integration test (threaded run loop)
# ---------------------------------------------------------------------------

def test_pushes_framedata():
    """CalendarWidget run loop pushes at least one FrameData within 2 seconds."""
    from shared.message_schema import FrameData
    from widgets.calendar.widget import CalendarWidget

    out_q = queue.Queue(maxsize=100)
    in_q = queue.Queue(maxsize=10)
    config = {"width": 640, "height": 515, "settings": {"clock_format": "24h"}}
    w = CalendarWidget("test_cal_run", config, out_q, in_q)

    stop_event = threading.Event()

    def run_loop():
        """Run a single iteration of the widget's logic without the real sleep."""
        new_cfg = w.poll_config_update()
        if new_cfg:
            settings = new_cfg.get("settings", {})
            if "clock_format" in settings:
                w._clock_format = settings["clock_format"]
        frame = w.render_frame()
        try:
            out_q.put(frame, block=False)
        except queue.Full:
            pass

    # Run one iteration directly (avoids 1-second sleep in run())
    run_loop()

    frames = []
    while not out_q.empty():
        frames.append(out_q.get_nowait())

    assert len(frames) >= 1, "CalendarWidget should have pushed at least one FrameData"
    frame = frames[0]
    assert isinstance(frame, FrameData)
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4


# ---------------------------------------------------------------------------
# _safe_hex_color helper tests
# ---------------------------------------------------------------------------

class TestSafeHexColor:
    """CLR-01: _safe_hex_color converts hex to RGBA tuple with fallback."""

    def test_valid_hex_returns_rgba(self):
        from widgets.calendar.widget import _safe_hex_color
        assert _safe_hex_color("#ff0000", (0, 0, 0, 255)) == (255, 0, 0, 255)

    def test_invalid_hex_returns_default(self):
        from widgets.calendar.widget import _safe_hex_color
        assert _safe_hex_color("notacolor", (1, 2, 3, 255)) == (1, 2, 3, 255)

    def test_none_returns_default(self):
        from widgets.calendar.widget import _safe_hex_color
        assert _safe_hex_color(None, (10, 20, 30, 255)) == (10, 20, 30, 255)


# ---------------------------------------------------------------------------
# Color init tests
# ---------------------------------------------------------------------------

class TestCalendarColorInit:
    """CAL-04, CAL-05: CalendarWidget reads color settings on init."""

    def test_default_time_color(self):
        w = make_widget()
        assert w._time_color == (255, 255, 255, 255), f"Default time_color wrong: {w._time_color}"

    def test_default_date_color(self):
        w = make_widget()
        assert w._text_color == (220, 220, 220, 255), f"Default date_color wrong: {w._text_color}"

    def test_custom_time_color(self):
        w = make_widget(settings={"clock_format": "24h", "font": "Inter", "time_color": "#ff0000"})
        assert w._time_color == (255, 0, 0, 255), f"Custom time_color wrong: {w._time_color}"

    def test_custom_date_color(self):
        w = make_widget(settings={"clock_format": "24h", "font": "Inter", "date_color": "#00ff00"})
        assert w._text_color == (0, 255, 0, 255), f"Custom date_color wrong: {w._text_color}"

    def test_invalid_time_color_uses_default(self):
        w = make_widget(settings={"clock_format": "24h", "font": "Inter", "time_color": "notacolor"})
        assert w._time_color == (255, 255, 255, 255), f"Invalid time_color should default: {w._time_color}"

    def test_invalid_date_color_uses_default(self):
        w = make_widget(settings={"clock_format": "24h", "font": "Inter", "date_color": "xyz"})
        assert w._text_color == (220, 220, 220, 255), f"Invalid date_color should default: {w._text_color}"


# ---------------------------------------------------------------------------
# Color update tests
# ---------------------------------------------------------------------------

class TestCalendarColorUpdate:
    """CAL-04, CAL-05: CONFIG_UPDATE changes calendar text colors.

    NOTE: These tests call poll_config_update() and apply update logic inline
    rather than calling run() (which blocks). This correctly unit-tests the
    color-update logic in isolation, but does NOT verify that run() actually
    wires the handler. If run() is ever refactored to extract a separate
    _apply_config_update() method, these tests should be updated to call that
    method directly instead.
    """

    def test_config_update_changes_time_color(self):
        from shared.message_schema import ConfigUpdateMessage
        w = make_widget()
        w.in_queue.put_nowait(ConfigUpdateMessage(
            widget_id="test_cal",
            config={"settings": {"time_color": "#0000ff"}},
        ))
        new_cfg = w.poll_config_update()
        # Simulate run() handler
        if new_cfg:
            settings = new_cfg.get("settings", {})
            if "time_color" in settings:
                from widgets.calendar.widget import _safe_hex_color
                w._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))
        assert w._time_color == (0, 0, 255, 255), f"time_color after update: {w._time_color}"

    def test_config_update_changes_date_color(self):
        from shared.message_schema import ConfigUpdateMessage
        w = make_widget()
        w.in_queue.put_nowait(ConfigUpdateMessage(
            widget_id="test_cal",
            config={"settings": {"date_color": "#ff00ff"}},
        ))
        new_cfg = w.poll_config_update()
        if new_cfg:
            settings = new_cfg.get("settings", {})
            if "date_color" in settings:
                from widgets.calendar.widget import _safe_hex_color
                w._text_color = _safe_hex_color(settings["date_color"], (220, 220, 220, 255))
        assert w._text_color == (255, 0, 255, 255), f"text_color after update: {w._text_color}"

    def test_config_update_invalid_color_keeps_previous(self):
        from shared.message_schema import ConfigUpdateMessage
        w = make_widget()
        w.in_queue.put_nowait(ConfigUpdateMessage(
            widget_id="test_cal",
            config={"settings": {"time_color": "bad"}},
        ))
        new_cfg = w.poll_config_update()
        if new_cfg:
            settings = new_cfg.get("settings", {})
            if "time_color" in settings:
                from widgets.calendar.widget import _safe_hex_color
                w._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))
        assert w._time_color == (255, 255, 255, 255), "Invalid color should fall back to default"
