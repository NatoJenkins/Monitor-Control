"""Tests for win32_utils — HOST-01 display targeting and HOST-04 ClipCursor/WTS."""
import ctypes
import ctypes.wintypes
import pytest
import win32con
from unittest.mock import MagicMock, patch


def _make_mock_screen(x, y, logical_w, logical_h, dpr):
    """Helper: create a mock QScreen with given geometry and DPR."""
    screen = MagicMock()
    geo = MagicMock()
    geo.width.return_value = logical_w
    geo.height.return_value = logical_h
    geo.topLeft.return_value = MagicMock()
    screen.geometry.return_value = geo
    screen.devicePixelRatio.return_value = dpr
    return screen


class TestFindTargetScreen:
    """HOST-01: find_target_screen identifies display by physical pixel dimensions."""

    def test_find_target_screen_by_physical_pixels(self):
        """find_target_screen(1920, 515) returns the screen whose logical geometry * DPR
        equals 1920x515.

        Display 3 spec: logical 1536x412 at DPR 1.25 → physical 1920x515.
        """
        from host.win32_utils import find_target_screen

        screen_primary = _make_mock_screen(0, 0, 1920, 1080, 1.0)    # 1920x1080 physical
        screen_secondary = _make_mock_screen(1920, 0, 2560, 1440, 1.0)  # 2560x1440 physical
        screen_display3 = _make_mock_screen(3840, 0, 1536, 412, 1.25)  # 1920x515 physical

        mock_screens = [screen_primary, screen_secondary, screen_display3]

        with patch("PyQt6.QtWidgets.QApplication.screens", return_value=mock_screens):
            result = find_target_screen(1920, 515)

        assert result is screen_display3, (
            "find_target_screen should return the screen with physical dimensions 1920x515"
        )

    def test_find_target_screen_returns_none(self):
        """find_target_screen returns None when no screen matches the target dimensions."""
        from host.win32_utils import find_target_screen

        screen_primary = _make_mock_screen(0, 0, 1920, 1080, 1.0)   # 1920x1080 physical
        screen_secondary = _make_mock_screen(1920, 0, 2560, 1440, 1.0)  # 2560x1440 physical

        mock_screens = [screen_primary, screen_secondary]

        with patch("PyQt6.QtWidgets.QApplication.screens", return_value=mock_screens):
            result = find_target_screen(1920, 515)

        assert result is None, (
            "find_target_screen should return None when no screen matches"
        )


def _make_mock_screen_with_rect(left, top, width, height):
    """Helper: create a mock QScreen whose geometry() returns a QRect-like mock."""
    screen = MagicMock()
    geo = MagicMock()
    geo.left.return_value = left
    geo.top.return_value = top
    geo.width.return_value = width
    geo.height.return_value = height
    geo.right.return_value = left + width - 1   # Qt off-by-one
    geo.bottom.return_value = top + height - 1  # Qt off-by-one
    # united() should return a combined QRect-like mock
    screen.geometry.return_value = geo
    return screen, geo


class TestComputeAllowedRect:
    """HOST-04: compute_allowed_rect excludes Display 3 from the cursor-allowed RECT."""

    def test_compute_allowed_rect_excludes_display3(self):
        """Allowed rect covers all screens EXCEPT Display 3.

        Setup:
          primary   QRect(0,    0, 1920, 1080)
          secondary QRect(1920, 0, 1920, 1080)
          display3  QRect(3840, 0, 1536,  412)

        Expected: left=0, top=0, right=3840, bottom=1080
        """
        from host.win32_utils import compute_allowed_rect

        primary_screen, primary_geo = _make_mock_screen_with_rect(0, 0, 1920, 1080)
        secondary_screen, secondary_geo = _make_mock_screen_with_rect(1920, 0, 1920, 1080)
        display3_screen, display3_geo = _make_mock_screen_with_rect(3840, 0, 1536, 412)

        # Mock the united() call: primary.geo.united(secondary.geo) -> combined mock
        combined_geo = MagicMock()
        combined_geo.left.return_value = 0
        combined_geo.top.return_value = 0
        combined_geo.width.return_value = 3840
        combined_geo.height.return_value = 1080
        primary_geo.united.return_value = combined_geo

        result = compute_allowed_rect(
            display3_screen,
            [primary_screen, secondary_screen, display3_screen],
        )

        assert result.left == 0, f"left should be 0, got {result.left}"
        assert result.top == 0, f"top should be 0, got {result.top}"
        assert result.right == 3840, f"right should be 3840 (left+width), got {result.right}"
        assert result.bottom == 1080, f"bottom should be 1080 (top+height), got {result.bottom}"


class TestApplyClipCursor:
    """HOST-04: apply_clip_cursor delegates to user32.ClipCursor."""

    def test_apply_clip_cursor_calls_user32(self):
        """apply_clip_cursor(0, 0, 3840, 1080) must call _user32.ClipCursor once."""
        from host.win32_utils import apply_clip_cursor

        with patch("host.win32_utils._user32") as mock_user32:
            apply_clip_cursor(0, 0, 3840, 1080)
            mock_user32.ClipCursor.assert_called_once()


class TestWin32MessageFilter:
    """HOST-04: Win32MessageFilter re-applies ClipCursor on unlock and display change."""

    def _make_msg_struct(self, message, wParam):
        """Build a real ctypes MSG struct and return its address as an int."""
        msg = ctypes.wintypes.MSG()
        msg.message = message
        msg.wParam = wParam
        return msg

    def _run_filter(self, message_value, wParam_value):
        """Create filter with a MagicMock callback, feed it a synthetic MSG, return callback."""
        from host.win32_utils import Win32MessageFilter

        callback = MagicMock()
        msg_filter = Win32MessageFilter(on_clip_needed=callback)

        msg_struct = self._make_msg_struct(message_value, wParam_value)

        # Wrap msg_struct in a mock that returns its address via __int__
        mock_message = MagicMock()
        mock_message.__int__ = MagicMock(return_value=ctypes.addressof(msg_struct))

        msg_filter.nativeEventFilter(b"windows_generic_MSG", mock_message)
        return callback, msg_struct  # keep msg_struct alive during assertion

    def test_session_unlock_triggers_clip_reapply(self):
        """WM_WTSSESSION_CHANGE + WTS_SESSION_UNLOCK (0x8) must invoke on_clip_needed."""
        from host.win32_utils import WM_WTSSESSION_CHANGE, WTS_SESSION_UNLOCK

        callback, _ = self._run_filter(WM_WTSSESSION_CHANGE, WTS_SESSION_UNLOCK)
        callback.assert_called_once()

    def test_displaychange_triggers_clip_reapply(self):
        """WM_DISPLAYCHANGE must invoke on_clip_needed."""
        callback, _ = self._run_filter(win32con.WM_DISPLAYCHANGE, 0)
        callback.assert_called_once()

    def test_session_lock_does_not_trigger_clip(self):
        """WM_WTSSESSION_CHANGE + WTS_SESSION_LOCK (0x7) must NOT invoke on_clip_needed."""
        from host.win32_utils import WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK

        callback, _ = self._run_filter(WM_WTSSESSION_CHANGE, WTS_SESSION_LOCK)
        callback.assert_not_called()

    def test_activateapp_activate_triggers_clip_reapply(self):
        """WM_ACTIVATEAPP with wParam=1 (app gaining focus) must invoke on_clip_needed."""
        from host.win32_utils import WM_ACTIVATEAPP

        callback, _ = self._run_filter(WM_ACTIVATEAPP, 1)
        callback.assert_called_once()

    def test_activateapp_deactivate_triggers_clip_reapply(self):
        """WM_ACTIVATEAPP with wParam=0 (app losing focus via alt-tab) must invoke on_clip_needed.

        Windows calls ClipCursor(NULL) when a different application receives focus.
        Intercepting the deactivate message and re-applying the clip immediately
        restores the containment rectangle so the cursor cannot drift onto Display 3.
        """
        from host.win32_utils import WM_ACTIVATEAPP

        callback, _ = self._run_filter(WM_ACTIVATEAPP, 0)
        callback.assert_called_once()
