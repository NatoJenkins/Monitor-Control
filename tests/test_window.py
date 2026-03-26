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
        """place_on_screen must call move(screen.geometry().topLeft()) and showFullScreen()."""
        from host.window import HostWindow
        from host.win32_utils import place_on_screen

        window = HostWindow()

        mock_screen = MagicMock()
        mock_rect = MagicMock()
        mock_top_left = MagicMock()
        mock_screen.geometry.return_value = mock_rect
        mock_rect.topLeft.return_value = mock_top_left

        mock_handle = MagicMock()

        with patch.object(window, "create"), \
             patch.object(window, "windowHandle", return_value=mock_handle), \
             patch.object(window, "move") as mock_move, \
             patch.object(window, "showFullScreen") as mock_show_full:
            place_on_screen(window, mock_screen)

        mock_handle.setScreen.assert_called_once_with(mock_screen)
        mock_move.assert_called_once_with(mock_top_left)
        mock_show_full.assert_called_once()

        # Cleanup
        window.hide()
        window.destroy()
