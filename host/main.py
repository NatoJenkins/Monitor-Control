import sys
import multiprocessing
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect
from host.window import HostWindow
from host.win32_utils import (
    find_target_screen, place_on_screen,
    apply_clip_cursor, compute_allowed_rect,
    register_session_notifications,
    Win32MessageFilter,
)
from host.process_manager import ProcessManager
from host.queue_drain import QueueDrainTimer
from widgets.dummy.widget import run_dummy_widget


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

    # --- IPC Pipeline (IPC-01 through IPC-04) ---
    # Configure compositor slots
    # For Phase 1: single dummy widget slot taking full display width
    window.compositor.set_slots({
        "dummy": QRect(0, 0, 1920, 515),
    })

    # Start ProcessManager and dummy widget
    pm = ProcessManager()
    pm.start_widget(
        widget_id="dummy",
        target_fn=run_dummy_widget,
        config={"width": 1920, "height": 515},
    )

    # Start drain timer — polls all queues at 50ms, updates compositor
    drain_timer = QueueDrainTimer(pm, window.compositor, interval_ms=50)
    drain_timer.start()

    # Keep references alive
    window._pm = pm
    window._drain_timer = drain_timer

    # Clean shutdown
    def cleanup():
        drain_timer.stop()
        pm.stop_all()

    app.aboutToQuit.connect(cleanup)

    sys.exit(app.exec())


if __name__ == "__main__":
    # BLOCKER: this guard prevents recursive subprocess spawning on Windows spawn
    multiprocessing.set_start_method("spawn")  # explicit; documents intent
    main()
