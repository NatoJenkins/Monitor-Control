"""Tests for win32_utils — HOST-01 display targeting."""
import pytest
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
