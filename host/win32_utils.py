from PyQt6.QtWidgets import QApplication


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

    Uses create() to force native HWND so windowHandle() is non-None,
    then setScreen + move + showFullScreen for reliable placement.
    """
    window.create()  # force native window creation
    window.windowHandle().setScreen(screen)
    window.move(screen.geometry().topLeft())
    window.showFullScreen()
