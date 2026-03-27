from PyQt6.QtGui import QPainter, QImage, QColor
from PyQt6.QtCore import QRect
from shared.message_schema import FrameData


class Compositor:
    def __init__(self, host_window):
        self._window = host_window
        self._frames: dict[str, FrameData] = {}
        self._slots: dict[str, QRect] = {}
        self._crashed: set[str] = set()

    def set_slots(self, slots: dict[str, QRect]) -> None:
        """Configure widget slot positions. slots = {widget_id: QRect(x,y,w,h)}"""
        self._slots = slots

    def add_slot(self, widget_id: str, slot_rect: QRect) -> None:
        """Add or update a single widget slot."""
        self._slots[widget_id] = slot_rect

    def remove_slot(self, widget_id: str) -> None:
        """Remove a widget slot and its cached frame/crash state."""
        self._slots.pop(widget_id, None)
        self._frames.pop(widget_id, None)
        self._crashed.discard(widget_id)

    def update_frame(self, widget_id: str, frame: FrameData) -> None:
        self._frames[widget_id] = frame
        self._crashed.discard(widget_id)

    def mark_crashed(self, widget_id: str) -> None:
        self._crashed.add(widget_id)

    def schedule_repaint(self) -> None:
        self._window.update()

    def paint(self, painter: QPainter) -> None:
        """Called from HostWindow.paintEvent. Renders all slots."""
        for widget_id, slot_rect in self._slots.items():
            if widget_id in self._crashed:
                painter.fillRect(slot_rect, QColor("#8B0000"))  # dark red = crashed
                continue
            frame = self._frames.get(widget_id)
            if frame and frame.rgba_bytes:
                img = QImage(
                    frame.rgba_bytes,
                    frame.width,
                    frame.height,
                    frame.width * 4,  # bytes per line
                    QImage.Format.Format_RGBA8888,
                )
                painter.drawImage(slot_rect, img)
            else:
                painter.fillRect(slot_rect, QColor("#1a1a1a"))  # empty slot
