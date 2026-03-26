import sys
import multiprocessing
from PyQt6.QtWidgets import QApplication
from host.window import HostWindow
from host.win32_utils import (
    find_target_screen, place_on_screen,
    apply_clip_cursor, compute_allowed_rect,
    register_session_notifications,
    Win32MessageFilter,
)


def main():
    app = QApplication(sys.argv)

    window = HostWindow()
    # Flags already set in HostWindow.__init__

    target = find_target_screen(phys_width=1920, phys_height=515)
    if target is None:
        print("WARNING: Display 3 (1920x515) not found. Using last available screen.")
        target = app.screens()[-1]

    place_on_screen(window, target)

    # --- ClipCursor enforcement (HOST-04) ---
    # Compute allowed cursor region: all screens EXCEPT Display 3
    allowed = compute_allowed_rect(target, app.screens())
    apply_clip_cursor(allowed.left, allowed.top, allowed.right, allowed.bottom)

    # Register for WTS session notifications to re-apply ClipCursor after unlock
    hwnd = int(window.winId())
    register_session_notifications(hwnd)

    # Install native event filter for WM_WTSSESSION_CHANGE + WM_DISPLAYCHANGE
    def reapply_clip():
        apply_clip_cursor(allowed.left, allowed.top, allowed.right, allowed.bottom)

    msg_filter = Win32MessageFilter(on_clip_needed=reapply_clip)
    app.installNativeEventFilter(msg_filter)

    # Prevent garbage collection of the filter during app lifetime
    window._msg_filter = msg_filter

    # ProcessManager, QueueDrainTimer wired in plan 01-03

    sys.exit(app.exec())


if __name__ == "__main__":
    # BLOCKER: this guard prevents recursive subprocess spawning on Windows spawn
    multiprocessing.set_start_method("spawn")  # explicit; documents intent
    main()
