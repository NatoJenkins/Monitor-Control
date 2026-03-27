import ctypes
import ctypes.wintypes
import win32ts
import win32con
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QAbstractNativeEventFilter


_user32 = ctypes.windll.user32
WM_WTSSESSION_CHANGE = 0x02B1
WTS_SESSION_UNLOCK = 0x8
WTS_SESSION_LOCK = 0x7


class RECT(ctypes.Structure):
    _fields_ = [
        ("left",   ctypes.c_long),
        ("top",    ctypes.c_long),
        ("right",  ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]


def apply_clip_cursor(left: int, top: int, right: int, bottom: int) -> None:
    rect = RECT(left, top, right, bottom)
    _user32.ClipCursor(ctypes.byref(rect))


def release_clip_cursor() -> None:
    _user32.ClipCursor(None)


def compute_allowed_rect(excluded_screen, all_screens) -> RECT:
    combined = None
    for screen in all_screens:
        if screen is excluded_screen:
            continue
        geo = screen.geometry()
        combined = geo if combined is None else combined.united(geo)
    if combined is None:
        return RECT(0, 0, 1920, 1080)
    # QRect.right() returns left+width-1; use left()+width() for actual right edge
    return RECT(
        combined.left(),
        combined.top(),
        combined.left() + combined.width(),
        combined.top() + combined.height(),
    )


def register_session_notifications(hwnd: int) -> None:
    win32ts.WTSRegisterSessionNotification(hwnd, win32ts.NOTIFY_FOR_THIS_SESSION)


def unregister_session_notifications(hwnd: int) -> None:
    win32ts.WTSUnRegisterSessionNotification(hwnd)


class Win32MessageFilter(QAbstractNativeEventFilter):
    def __init__(self, on_clip_needed):
        super().__init__()
        self._on_clip_needed = on_clip_needed

    def nativeEventFilter(self, event_type, message):
        if event_type == b"windows_generic_MSG":
            msg = ctypes.wintypes.MSG.from_address(message.__int__())
            if msg.message == WM_WTSSESSION_CHANGE:
                if msg.wParam == WTS_SESSION_UNLOCK:
                    self._on_clip_needed()
            elif msg.message == win32con.WM_DISPLAYCHANGE:
                self._on_clip_needed()
        return False, 0


def find_target_screen(phys_width: int = 1920, phys_height: int = 515):
    """Find screen matching given physical pixel dimensions.

    QScreen.geometry() returns logical pixels. Multiply by devicePixelRatio
    to get physical pixels for comparison. Returns QScreen or None.
    """
    for screen in QApplication.screens():
        logical_geo = screen.geometry()
        dpr = screen.devicePixelRatio()
        actual_w = int(logical_geo.width() * dpr)
        actual_h = int(logical_geo.height() * dpr)
        if actual_w == phys_width and actual_h == phys_height:
            return screen
    return None


def place_on_screen(window, screen):
    """Place window on target screen. Call AFTER flags set, BEFORE show.

    Sets geometry explicitly to the target screen's rect, then calls show().
    Avoids showFullScreen() which uses MonitorFromWindow internally and can
    pick the wrong display when the target screen sits below the primary
    monitors (e.g. an HDMI strip at y=1440 on the virtual-desktop boundary).
    """
    window.setGeometry(screen.geometry())
    window.show()
