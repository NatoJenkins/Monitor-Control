"""Unit tests for PomodoroWidget state machine, rendering, and config updates.

Tests run in-process (no subprocess needed) by instantiating PomodoroWidget
with queue.Queue mocks (API-compatible with multiprocessing.Queue for in-process use).
"""
import ast
import pathlib
import queue
import time

import pytest

WIDGET_FILE = pathlib.Path(__file__).parent.parent / "widgets" / "pomodoro" / "widget.py"


# ---------------------------------------------------------------------------
# Source-level checks
# ---------------------------------------------------------------------------

def test_no_pyqt6_import():
    """widgets/pomodoro/widget.py must NOT import PyQt6 in any form."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    assert "import PyQt6" not in source, "PomodoroWidget must not use 'import PyQt6'"
    assert "from PyQt6" not in source, "PomodoroWidget must not use 'from PyQt6'"


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

    assert put_calls, "Expected at least one .put() call in PomodoroWidget source"
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

def make_widget(settings=None, width=640, height=515):
    """Create a PomodoroWidget with queue.Queue mocks."""
    from widgets.pomodoro.widget import PomodoroWidget
    config = {
        "width": width,
        "height": height,
        "settings": settings or {
            "work_minutes": 25,
            "short_break_minutes": 5,
            "long_break_minutes": 15,
            "cycles_before_long_break": 4,
            "font": "Inter",
            "work_accent_color": "#ff4444",
            "short_break_accent_color": "#44ff44",
            "long_break_accent_color": "#4488ff",
        },
    }
    out_q = queue.Queue(maxsize=100)
    in_q = queue.Queue(maxsize=10)
    return PomodoroWidget("test_pomo", config, out_q, in_q)


# ---------------------------------------------------------------------------
# format_mm_ss
# ---------------------------------------------------------------------------

def test_format_mm_ss():
    """format_mm_ss produces correct MM:SS strings."""
    from widgets.pomodoro.widget import format_mm_ss
    assert format_mm_ss(1500) == "25:00"
    assert format_mm_ss(277) == "04:37"
    assert format_mm_ss(0) == "00:00"
    assert format_mm_ss(-5) == "00:00"  # clamps negatives


# ---------------------------------------------------------------------------
# State machine tests
# ---------------------------------------------------------------------------

def test_state_machine_idle_to_work():
    """PomodoroState starts IDLE; 'start' command transitions to WORK."""
    from widgets.pomodoro.widget import PomodoroState
    w = make_widget()
    assert w._state == PomodoroState.IDLE
    w._handle_command("start")
    assert w._state == PomodoroState.WORK


def test_state_machine_work_to_short_break():
    """After WORK countdown expires, state auto-advances to SHORT_BREAK."""
    from widgets.pomodoro.widget import PomodoroState
    w = make_widget()
    w._handle_command("start")  # IDLE -> WORK
    assert w._state == PomodoroState.WORK

    # Expire the deadline artificially
    w._deadline = time.monotonic() - 1.0
    w._update_remaining()

    assert w._state == PomodoroState.SHORT_BREAK


def test_state_machine_cycle_counting():
    """After cycles_before_long_break work cycles, the next break is LONG_BREAK."""
    from widgets.pomodoro.widget import PomodoroState
    w = make_widget(settings={
        "work_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "cycles_before_long_break": 4,
    })
    # Simulate 3 work -> short_break cycles manually
    for _ in range(3):
        w._handle_command("start")
        assert w._state in (PomodoroState.WORK, PomodoroState.SHORT_BREAK)
        w._state = PomodoroState.WORK  # ensure we're in WORK
        w._deadline = time.monotonic() - 1.0
        w._update_remaining()  # expire -> SHORT_BREAK
        assert w._state == PomodoroState.SHORT_BREAK, f"Expected SHORT_BREAK, got {w._state}"
        # Auto-advance break -> WORK
        w._deadline = time.monotonic() - 1.0
        w._update_remaining()
        assert w._state == PomodoroState.WORK

    # 4th cycle: work expires -> should be LONG_BREAK
    w._deadline = time.monotonic() - 1.0
    w._update_remaining()
    assert w._state == PomodoroState.LONG_BREAK, (
        f"Expected LONG_BREAK after {w._cycles_before_long} cycles, got {w._state}"
    )


def test_state_machine_long_break_to_work():
    """After LONG_BREAK expires, state returns to WORK and cycle_count resets."""
    from widgets.pomodoro.widget import PomodoroState
    w = make_widget(settings={
        "work_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "cycles_before_long_break": 2,
    })
    # Run 2 cycles to reach LONG_BREAK
    for _ in range(2):
        w._state = PomodoroState.WORK
        w._deadline = time.monotonic() - 1.0
        w._update_remaining()
        if w._state == PomodoroState.SHORT_BREAK:
            w._deadline = time.monotonic() - 1.0
            w._update_remaining()

    assert w._state == PomodoroState.LONG_BREAK

    # Expire LONG_BREAK
    w._deadline = time.monotonic() - 1.0
    w._update_remaining()

    assert w._state == PomodoroState.WORK
    assert w._cycle_count == 0


def test_state_machine_pause():
    """Calling pause during WORK freezes the countdown (deadline becomes None)."""
    from widgets.pomodoro.widget import PomodoroState
    w = make_widget()
    w._handle_command("start")  # IDLE -> WORK
    assert w._deadline is not None

    w._handle_command("pause")
    assert w._deadline is None
    assert w._paused_remaining is not None and w._paused_remaining > 0


def test_state_machine_reset():
    """reset from any state returns to IDLE with cycle_count=0 and deadline=None."""
    from widgets.pomodoro.widget import PomodoroState
    w = make_widget()
    w._handle_command("start")  # IDLE -> WORK
    assert w._state == PomodoroState.WORK

    w._handle_command("reset")
    assert w._state == PomodoroState.IDLE
    assert w._cycle_count == 0
    assert w._deadline is None


# ---------------------------------------------------------------------------
# Rendering tests
# ---------------------------------------------------------------------------

def test_frame_content():
    """render_frame() returns FrameData with correct dimensions and RGBA byte count."""
    from shared.message_schema import FrameData
    w = make_widget()
    frame = w.render_frame()
    assert isinstance(frame, FrameData)
    assert frame.widget_id == "test_pomo"
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4


# ---------------------------------------------------------------------------
# Config update tests
# ---------------------------------------------------------------------------

def test_config_update_defers_durations():
    """CONFIG_UPDATE with work_minutes during WORK does NOT change current countdown;
    new duration applies when next WORK phase begins."""
    from widgets.pomodoro.widget import PomodoroState
    from shared.message_schema import ConfigUpdateMessage
    w = make_widget()
    w._handle_command("start")  # IDLE -> WORK
    assert w._state == PomodoroState.WORK

    original_deadline = w._deadline

    # Push config update with new work_minutes via in_queue
    w.in_queue.put_nowait(ConfigUpdateMessage(
        widget_id="test_pomo",
        config={"settings": {"work_minutes": 30}},
    ))
    new_cfg, cmd = w._poll_in_queue()
    w._apply_config(new_cfg)

    # Deadline should NOT have changed — still counting down the original 25min
    assert w._deadline == original_deadline, "Deferred duration should not change active countdown"
    assert w._work_secs == 25 * 60, "work_secs should still be 25 min until transition"

    # Now expire WORK and transition to SHORT_BREAK then back to WORK
    w._deadline = time.monotonic() - 1.0
    w._update_remaining()  # WORK -> SHORT_BREAK (pending durations applied here)

    # WORK duration should have updated
    assert w._work_secs == 30 * 60, f"work_secs should be 30*60 after transition, got {w._work_secs}"


def test_config_update_applies_colors_immediately():
    """CONFIG_UPDATE with work_accent_color takes effect on the very next rendered frame."""
    w = make_widget()
    # Initially red
    assert w._work_color == "#ff4444"

    new_cfg = {"settings": {"work_accent_color": "#00ff00"}}
    w._apply_config(new_cfg)

    assert w._work_color == "#00ff00"
    # _accent_color() in IDLE state maps to work color
    color = w._accent_color()
    assert color == (0, 255, 0, 255), f"Expected (0,255,0,255), got {color}"
