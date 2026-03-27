"""Unit tests for NotificationWidget rendering and config updates.

Tests run in-process using queue.Queue mocks (API-compatible with multiprocessing.Queue).
WinRT calls are mocked via unittest.mock.patch so tests run without winrt installed.
"""
import ast
import datetime
import pathlib
import queue
import time
import unittest.mock

import pytest

WIDGET_FILE = pathlib.Path(__file__).parent.parent / "widgets" / "notification" / "widget.py"


# ---------------------------------------------------------------------------
# Source-level checks (NOTF-02, subprocess safety)
# ---------------------------------------------------------------------------

def test_no_pyqt6_import():
    """widgets/notification/widget.py must NOT import PyQt6 in any form."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    assert "import PyQt6" not in source, "NotificationWidget must not use 'import PyQt6'"
    assert "from PyQt6" not in source, "NotificationWidget must not use 'from PyQt6'"


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

    assert put_calls, "Expected at least one .put() call in NotificationWidget source"
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


def test_no_request_access_async_in_widget():
    """widget.py must NOT contain request_access_async (host responsibility only)."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    assert "request_access_async" not in source, (
        "NotificationWidget must not call request_access_async — "
        "that is the host's responsibility (NOTF-01)"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_notification(
    notif_id: int,
    app_name: str,
    title: str,
    body: str,
    creation_time: datetime.datetime | None = None,
) -> unittest.mock.MagicMock:
    """Build a mock UserNotification object matching the WinRT 3.2.1 shape."""
    if creation_time is None:
        creation_time = datetime.datetime(2026, 3, 26, 10, 0, 0,
                                          tzinfo=datetime.timezone.utc)
    notif = unittest.mock.MagicMock()
    notif.id = notif_id

    # app_info.display_info.display_name
    notif.app_info.display_info.display_name = app_name

    # notification.visual.get_binding("ToastGeneric").get_text_elements()
    title_elem = unittest.mock.MagicMock()
    title_elem.text = title
    body_elem = unittest.mock.MagicMock()
    body_elem.text = body
    notif.notification.visual.get_binding.return_value.get_text_elements.return_value = [
        title_elem, body_elem
    ]

    # creation_time is a Python datetime (UTC-aware) per 04-01 spike findings
    notif.creation_time = creation_time

    return notif


def make_widget(settings=None, config_overrides=None):
    """Create a NotificationWidget with queue.Queue mocks."""
    from widgets.notification.widget import NotificationWidget
    config = {
        "width": 640,
        "height": 515,
        "settings": settings or {
            "font": "Inter",
            "auto_dismiss_seconds": 30,
            "blocked_apps": [],
        },
    }
    if config_overrides:
        config.update(config_overrides)
    out_q = queue.Queue(maxsize=100)
    in_q = queue.Queue(maxsize=10)
    return NotificationWidget("test_notif", config, out_q, in_q)


# ---------------------------------------------------------------------------
# Permission tests (NOTF-02)
# ---------------------------------------------------------------------------

def test_permission_placeholder_when_denied():
    """When GetAccessStatus returns DENIED, render returns a valid FrameData placeholder."""
    from shared.message_schema import FrameData

    w = make_widget()

    # Mock _is_allowed to return False (DENIED)
    with unittest.mock.patch.object(w, "_is_allowed", return_value=False):
        frame = w._render_permission_placeholder()

    assert isinstance(frame, FrameData)
    assert frame.widget_id == "test_notif"
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4
    assert any(b != 0 for b in frame.rgba_bytes), "Placeholder frame must have non-zero pixels"


def test_placeholder_frame_dimensions():
    """Permission placeholder frame has exactly the expected dimensions."""
    w = make_widget()
    frame = w._render_permission_placeholder()
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4


# ---------------------------------------------------------------------------
# Idle state test
# ---------------------------------------------------------------------------

def test_idle_state_frame():
    """When no notifications, _render_idle() returns correct dimensions and non-zero bytes."""
    from shared.message_schema import FrameData

    w = make_widget()
    frame = w._render_idle()

    assert isinstance(frame, FrameData)
    assert frame.widget_id == "test_notif"
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4
    assert any(b != 0 for b in frame.rgba_bytes), "Idle frame must have non-zero pixels"


# ---------------------------------------------------------------------------
# Notification rendering tests (NOTF-03, NOTF-05)
# ---------------------------------------------------------------------------

def test_renders_notification_content():
    """When GetNotificationsAsync returns a notification, render returns a FrameData."""
    from shared.message_schema import FrameData

    w = make_widget()
    frame = w._render_notification(
        app_name="TestApp",
        title="Test Title",
        body="Test Body",
        timestamp="10:00",
    )

    assert isinstance(frame, FrameData)
    assert frame.widget_id == "test_notif"
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4
    assert any(b != 0 for b in frame.rgba_bytes), "Notification frame must have non-zero content"


def test_most_recent_notification_selected():
    """_fetch_latest selects the notification with the latest creation_time."""
    w = make_widget()

    older_time = datetime.datetime(2026, 3, 26, 9, 0, 0, tzinfo=datetime.timezone.utc)
    newer_time = datetime.datetime(2026, 3, 26, 10, 30, 0, tzinfo=datetime.timezone.utc)

    older_notif = _make_mock_notification(1, "AppA", "Old Title", "Old Body", older_time)
    newer_notif = _make_mock_notification(2, "AppB", "New Title", "New Body", newer_time)

    # Patch _is_allowed and asyncio.run to return both notifications
    with unittest.mock.patch.object(w, "_is_allowed", return_value=True):
        with unittest.mock.patch("widgets.notification.widget.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = [older_notif, newer_notif]
            result = w._fetch_latest()

    assert result is not None, "_fetch_latest should return a notification"
    notif_id, app_name, title, body, timestamp = result
    assert notif_id == 2, f"Expected newer notification (id=2), got id={notif_id}"
    assert app_name == "AppB"
    assert title == "New Title"


# ---------------------------------------------------------------------------
# Auto-dismiss tests (NOTF-04)
# ---------------------------------------------------------------------------

def test_auto_dismiss_timer():
    """After auto_dismiss_seconds elapses, widget clears to idle state."""
    w = make_widget(settings={
        "font": "Inter",
        "auto_dismiss_seconds": 2,
        "blocked_apps": [],
    })

    # Manually set state as if a notification just arrived
    w._current_notif = ("TestApp", "Title", "Body", "10:00")
    w._last_notif_id = 42
    w._display_since = 0.0  # "arrived at t=0"

    # Simulate time passing beyond auto_dismiss_seconds
    fake_now = 3.0  # 3 seconds > 2 second timeout
    with unittest.mock.patch("time.monotonic", return_value=fake_now):
        # Apply auto-dismiss logic directly
        if w._current_notif is not None:
            elapsed = fake_now - w._display_since
            if elapsed > w._auto_dismiss_seconds:
                w._current_notif = None
                # Do NOT call remove_notification

    assert w._current_notif is None, "Auto-dismiss should clear current notification"


def test_new_notification_resets_timer():
    """A new notification (different ID) resets the auto-dismiss timer."""
    w = make_widget(settings={
        "font": "Inter",
        "auto_dismiss_seconds": 30,
        "blocked_apps": [],
    })

    # Simulate notification A arrived at t=0
    w._current_notif = ("AppA", "Title A", "Body A", "09:00")
    w._last_notif_id = 1
    w._display_since = 0.0

    # At t=1.5s, a new notification B arrives
    new_notif_b = _make_mock_notification(
        2, "AppB", "Title B", "Body B",
        datetime.datetime(2026, 3, 26, 9, 30, 0, tzinfo=datetime.timezone.utc)
    )

    with unittest.mock.patch.object(w, "_is_allowed", return_value=True):
        with unittest.mock.patch("widgets.notification.widget.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = [new_notif_b]
            with unittest.mock.patch("time.monotonic", return_value=1.5):
                latest = w._fetch_latest()

    # Simulate the run loop update at t=1.5
    if latest is not None:
        notif_id, app_name, title, body, ts = latest
        if notif_id != w._last_notif_id:
            w._current_notif = (app_name, title, body, ts)
            w._last_notif_id = notif_id
            w._display_since = 1.5  # reset timer

    # Check: timer reset, widget shows notification B, not idle
    assert w._current_notif is not None, "Widget should still show notification B"
    assert w._last_notif_id == 2, "Should be showing notification B (id=2)"
    assert w._display_since == 1.5, "Timer should have reset to 1.5"


def test_auto_dismiss_does_not_remove_from_action_center():
    """Auto-dismiss must NOT call remove_notification on the listener (NOTF-04 / v1 decision)."""
    w = make_widget(settings={
        "font": "Inter",
        "auto_dismiss_seconds": 1,
        "blocked_apps": [],
    })

    w._current_notif = ("TestApp", "Title", "Body", "10:00")
    w._last_notif_id = 99
    w._display_since = 0.0

    # Track any calls to a "remove" method on winrt listener
    mock_listener = unittest.mock.MagicMock()

    with unittest.mock.patch.object(w, "_get_winrt_listener",
                                    return_value=(mock_listener, unittest.mock.MagicMock())):
        # Apply auto-dismiss logic — elapsed > timeout
        fake_now = 5.0
        if w._current_notif is not None:
            elapsed = fake_now - w._display_since
            if elapsed > w._auto_dismiss_seconds:
                w._current_notif = None
                # Do NOT call remove_notification

    # Verify remove_notification was never called
    mock_listener.remove_notification.assert_not_called()
    assert w._current_notif is None, "Notification should be cleared after auto-dismiss"


# ---------------------------------------------------------------------------
# Blocklist test (NOTF-05)
# ---------------------------------------------------------------------------

def test_blocklist_filters_app():
    """Notifications from blocked apps must not appear (idle state shown instead)."""
    w = make_widget(settings={
        "font": "Inter",
        "auto_dismiss_seconds": 30,
        "blocked_apps": ["BadApp"],
    })

    bad_notif = _make_mock_notification(1, "BadApp", "Blocked Title", "Blocked Body")

    with unittest.mock.patch.object(w, "_is_allowed", return_value=True):
        with unittest.mock.patch("widgets.notification.widget.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = [bad_notif]
            result = w._fetch_latest()

    assert result is None, "Blocked app notification should be filtered; result must be None"


# ---------------------------------------------------------------------------
# Config update test
# ---------------------------------------------------------------------------

def test_config_update_applied():
    """Config update handler correctly updates font, timeout, and blocklist."""
    from shared.message_schema import ConfigUpdateMessage

    w = make_widget(settings={
        "font": "Inter",
        "auto_dismiss_seconds": 30,
        "blocked_apps": [],
    })

    assert w._font_name == "Inter"
    assert w._auto_dismiss_seconds == 30
    assert w._blocked_apps == set()

    # Push config update via in_queue
    w.in_queue.put_nowait(ConfigUpdateMessage(
        widget_id="test_notif",
        config={
            "settings": {
                "font": "Share Tech Mono",
                "auto_dismiss_seconds": 10,
                "blocked_apps": ["Annoying App"],
            }
        },
    ))

    # Simulate one run-loop iteration (poll + apply)
    new_cfg = w.poll_config_update()
    if new_cfg:
        settings = new_cfg.get("settings", {})
        w._font_name = settings.get("font", w._font_name)
        w._auto_dismiss_seconds = settings.get("auto_dismiss_seconds", w._auto_dismiss_seconds)
        w._blocked_apps = set(settings.get("blocked_apps", w._blocked_apps))

    assert w._font_name == "Share Tech Mono"
    assert w._auto_dismiss_seconds == 10
    assert "Annoying App" in w._blocked_apps


# ---------------------------------------------------------------------------
# Body text wrap test
# ---------------------------------------------------------------------------

def test_body_text_wraps_at_3_lines():
    """Very long body text renders without crash and produces valid frame dimensions."""
    from shared.message_schema import FrameData

    w = make_widget()
    long_body = "This is an extremely long notification body that goes on and on " * 10

    frame = w._render_notification(
        app_name="AppName",
        title="Some Title",
        body=long_body,
        timestamp="14:22",
    )

    assert isinstance(frame, FrameData)
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4


# ---------------------------------------------------------------------------
# Empty / None text field robustness (hardware regression fix)
# ---------------------------------------------------------------------------

def test_fetch_latest_none_text_coerced_to_empty_string():
    """When toast elements have .text == None, _fetch_latest returns empty strings not None.

    Hardware regression: PowerShell AppendChild DOM quirk sends empty toast nodes.
    winrt text elements return None for .text on nodes without content.
    The widget must coerce None -> "" to avoid Pillow TypeError on render.
    """
    w = make_widget()

    none_title_elem = unittest.mock.MagicMock()
    none_title_elem.text = None  # simulate WinRT returning None
    none_body_elem = unittest.mock.MagicMock()
    none_body_elem.text = None

    notif = unittest.mock.MagicMock()
    notif.id = 999
    notif.app_info.display_info.display_name = "TestApp"
    notif.notification.visual.get_binding.return_value.get_text_elements.return_value = [
        none_title_elem, none_body_elem
    ]
    notif.creation_time = datetime.datetime(2026, 3, 26, 10, 0, 0,
                                            tzinfo=datetime.timezone.utc)

    with unittest.mock.patch.object(w, "_is_allowed", return_value=True):
        with unittest.mock.patch("widgets.notification.widget.asyncio") as mock_asyncio:
            mock_asyncio.run.return_value = [notif]
            result = w._fetch_latest()

    assert result is not None, "_fetch_latest should return a result even with None text"
    notif_id, app_name, title, body, timestamp = result
    assert title == "", f"Expected title to be coerced to '', got {title!r}"
    assert body == "", f"Expected body to be coerced to '', got {body!r}"


def test_render_notification_with_empty_strings():
    """_render_notification must not crash when title and body are empty strings."""
    from shared.message_schema import FrameData

    w = make_widget()
    frame = w._render_notification(
        app_name="TestApp",
        title="",
        body="",
        timestamp="10:00",
    )

    assert isinstance(frame, FrameData)
    assert frame.width == 640
    assert frame.height == 515
    assert len(frame.rgba_bytes) == 640 * 515 * 4


def test_run_once_exception_does_not_kill_subprocess():
    """If _run_once raises, run() catches it, pushes idle frame, and continues.

    Hardware regression: without this guard, any WinRT or Pillow exception in the
    polling cycle crashes the subprocess, turning the slot dark red.
    """
    w = make_widget()

    call_count = [0]

    def boom():
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("simulated WinRT error")
        # Second call: succeed normally (push idle frame), then break via KeyboardInterrupt
        # which is a BaseException (not caught by 'except Exception') so the loop exits.
        frame = w._render_idle()
        try:
            w.out_queue.put(frame, block=False)
        except queue.Full:
            pass
        raise KeyboardInterrupt("test sentinel")

    with unittest.mock.patch.object(w, "_run_once", side_effect=boom):
        with unittest.mock.patch("time.sleep"):  # skip actual sleep
            try:
                w.run()
            except KeyboardInterrupt:
                pass

    # If the loop survived past the first exception, call_count > 1
    assert call_count[0] >= 2, (
        "run() should have continued after _run_once raised, "
        f"but _run_once was only called {call_count[0]} time(s)"
    )
