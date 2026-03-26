import pytest
from unittest.mock import MagicMock, patch


def _make_qrect(x, y, w, h):
    """Create a mock QRect-like object."""
    rect = MagicMock()
    rect.x.return_value = x
    rect.y.return_value = y
    rect.width.return_value = w
    rect.height.return_value = h
    rect.topLeft.return_value = MagicMock(x=lambda: x, y=lambda: y)
    return rect


@pytest.fixture
def mock_screen_primary():
    """Mock QScreen for Display 1: 1920x1080 at DPR 1.0."""
    screen = MagicMock()
    screen.geometry.return_value = _make_qrect(0, 0, 1920, 1080)
    screen.devicePixelRatio.return_value = 1.0
    return screen


@pytest.fixture
def mock_screen_display3():
    """Mock QScreen for Display 3: logical 1536x412 at DPR 1.25 (physical 1920x515)."""
    screen = MagicMock()
    screen.geometry.return_value = _make_qrect(3840, 0, 1536, 412)
    screen.devicePixelRatio.return_value = 1.25
    return screen


@pytest.fixture
def mock_qapp(mock_screen_primary, mock_screen_display3):
    """Patch QApplication.instance() and QApplication.screens() with mock screens."""
    with patch("PyQt6.QtWidgets.QApplication.instance") as mock_instance, \
         patch("PyQt6.QtWidgets.QApplication.screens") as mock_screens:
        mock_instance.return_value = MagicMock()
        mock_screens.return_value = [mock_screen_primary, mock_screen_display3]
        yield mock_screens
