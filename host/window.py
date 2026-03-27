from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor
from host.compositor import Compositor


class HostWindow(QWidget):
    def __init__(self):
        super().__init__()
        # BLOCKER: ALL flags in ONE call, BEFORE show()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self._bg_qcolor = QColor("#1a1a2e")   # default matches v1.1 hardcoded value
        self.compositor = Compositor(self)

    def set_bg_color(self, hex_str: str) -> None:
        """Update background color. Called from host after config reload."""
        color = QColor(hex_str)
        if color.isValid():
            self._bg_qcolor = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_qcolor)   # self.rect() not event.rect()
        self.compositor.paint(painter)
        painter.end()
