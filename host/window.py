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
        self.compositor = Compositor(self)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#000000"))  # background
        self.compositor.paint(painter)
        painter.end()
