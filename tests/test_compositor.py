import pytest
import sys
from unittest.mock import MagicMock
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPainter, QImage
from PyQt6.QtCore import QRect
from host.compositor import Compositor
from shared.message_schema import FrameData


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for Qt object construction."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_window_mock():
    mock = MagicMock()
    return mock


def test_slot_blit_renders_frame(qapp):
    """Compositor paints a FrameData frame into the correct slot rect."""
    window = _make_window_mock()
    compositor = Compositor(window)
    compositor.set_slots({"w1": QRect(0, 0, 200, 515)})

    # Solid teal frame: RGBA(0,128,128,255)
    rgba = bytes([0, 128, 128, 255]) * (200 * 515)
    frame = FrameData(widget_id="w1", width=200, height=515, rgba_bytes=rgba)
    compositor.update_frame("w1", frame)

    # Paint onto an in-memory image
    canvas = QImage(200, 515, QImage.Format.Format_RGBA8888)
    painter = QPainter(canvas)
    compositor.paint(painter)
    painter.end()

    # Check pixel at (100, 100) is teal
    pixel = canvas.pixel(100, 100)
    r = (pixel >> 16) & 0xFF
    g = (pixel >> 8) & 0xFF
    b = pixel & 0xFF
    assert r == 0, f"Red channel expected 0, got {r}"
    assert g == 128, f"Green channel expected 128, got {g}"
    assert b == 128, f"Blue channel expected 128, got {b}"


def test_placeholder_fill_when_no_frame(qapp):
    """Compositor fills an empty slot with #1a1a1a when no frame is available."""
    window = _make_window_mock()
    compositor = Compositor(window)
    compositor.set_slots({"w1": QRect(0, 0, 200, 200)})
    # No frame set — slot should show placeholder color

    canvas = QImage(200, 200, QImage.Format.Format_RGBA8888)
    painter = QPainter(canvas)
    compositor.paint(painter)
    painter.end()

    pixel = canvas.pixel(100, 100)
    r = (pixel >> 16) & 0xFF
    g = (pixel >> 8) & 0xFF
    b = pixel & 0xFF
    assert r == 26, f"Red channel expected 26 (#1a), got {r}"
    assert g == 26, f"Green channel expected 26 (#1a), got {g}"
    assert b == 26, f"Blue channel expected 26 (#1a), got {b}"


def test_crashed_slot_renders_dark_red(qapp):
    """Compositor fills a crashed slot with #8B0000 (dark red)."""
    window = _make_window_mock()
    compositor = Compositor(window)
    compositor.set_slots({"w1": QRect(0, 0, 200, 200)})
    compositor.mark_crashed("w1")

    canvas = QImage(200, 200, QImage.Format.Format_RGBA8888)
    painter = QPainter(canvas)
    compositor.paint(painter)
    painter.end()

    pixel = canvas.pixel(100, 100)
    r = (pixel >> 16) & 0xFF
    g = (pixel >> 8) & 0xFF
    b = pixel & 0xFF
    assert r == 139, f"Red channel expected 139 (#8B), got {r}"
    assert g == 0, f"Green channel expected 0, got {g}"
    assert b == 0, f"Blue channel expected 0, got {b}"
