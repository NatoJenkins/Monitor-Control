from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QColor


class HostWindow(QWidget):
    def __init__(self):
        super().__init__()
        # BLOCKER: ALL flags in ONE call, BEFORE show()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self._frames = {}  # widget_id -> FrameData (populated by compositor in plan 01-03)

    def paintEvent(self, event):
        # Minimal implementation — black background; compositor logic added in plan 01-03
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))
        painter.end()
