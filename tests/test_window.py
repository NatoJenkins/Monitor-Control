"""Tests for HostWindow — HOST-01 (placement) and HOST-02 (window flags)."""
import pytest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtCore import Qt


@pytest.fixture
def qapp_instance():
    """Minimal QApplication needed to instantiate QWidget subclasses."""
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


class TestWindowFlags:
    """HOST-02: All three window flags set atomically in __init__, before show()."""

    def test_window_flags_set_before_show(self, qapp_instance):
        """HostWindow must include FramelessWindowHint, WindowStaysOnTopHint, and Tool
        flags BEFORE any show() call."""
        from host.window import HostWindow

        window = HostWindow()

        flags = window.windowFlags()
        assert flags & Qt.WindowType.FramelessWindowHint, (
            "FramelessWindowHint must be set"
        )
        assert flags & Qt.WindowType.WindowStaysOnTopHint, (
            "WindowStaysOnTopHint must be set"
        )
        assert flags & Qt.WindowType.Tool, (
            "Tool flag must be set (prevents taskbar entry)"
        )

        # Cleanup
        window.hide()
        window.destroy()


class TestWindowPlacement:
    """HOST-01: place_on_screen positions window on target screen."""

    def test_window_placement(self, qapp_instance):
        """place_on_screen must call setGeometry(screen.geometry()) then show().

        Uses explicit geometry instead of showFullScreen() to avoid MonitorFromWindow
        picking the wrong display when the HDMI strip sits on the virtual-desktop boundary.
        """
        from host.window import HostWindow
        from host.win32_utils import place_on_screen

        window = HostWindow()

        mock_screen = MagicMock()
        mock_geo = MagicMock()
        mock_screen.geometry.return_value = mock_geo

        with patch.object(window, "setGeometry") as mock_set_geo, \
             patch.object(window, "show") as mock_show:
            place_on_screen(window, mock_screen)

        mock_set_geo.assert_called_once_with(mock_geo)
        mock_show.assert_called_once()

        # Cleanup
        window.hide()
        window.destroy()
