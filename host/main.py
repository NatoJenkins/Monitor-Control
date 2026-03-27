import sys
import os
import json
import multiprocessing
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QFileSystemWatcher
from host.window import HostWindow
from host.win32_utils import (
    find_target_screen, place_on_screen,
    apply_clip_cursor, compute_allowed_rect,
    register_session_notifications,
    Win32MessageFilter,
)
from host.process_manager import ProcessManager
from host.queue_drain import QueueDrainTimer
from host.config_loader import ConfigLoader, register_widget_type
from widgets.pomodoro.widget import run_pomodoro_widget
from widgets.calendar.widget import run_calendar_widget
from widgets.notification.widget import run_notification_widget


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

    # --- Notification access permission (NOTF-01) ---
    # RequestAccessAsync MUST run from the Qt main thread (STA apartment).
    # This blocks until the user grants/denies permission. Safe to block here
    # because the Qt event loop has not started yet (before app.exec()).
    import asyncio as _asyncio

    async def _request_notification_access():
        from winrt.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
        listener = UserNotificationListener.current
        status = await listener.request_access_async()
        return status

    try:
        _notif_status = _asyncio.run(_request_notification_access())
        from winrt.windows.ui.notifications.management import UserNotificationListenerAccessStatus
        if _notif_status == UserNotificationListenerAccessStatus.ALLOWED:
            print("[Host] Notification access granted", flush=True)
        elif _notif_status == UserNotificationListenerAccessStatus.DENIED:
            print("[Host] Notification access denied — widget will show placeholder", flush=True)
        else:
            print("[Host] Notification access unspecified — will prompt again next run", flush=True)
    except Exception as _notif_err:
        print(f"[Host] Notification access request failed: {_notif_err}", flush=True)

    # --- Config-driven widget startup (CFG-01, CFG-02, CFG-03) ---
    register_widget_type("pomodoro", run_pomodoro_widget)
    register_widget_type("calendar", run_calendar_widget)
    register_widget_type("notification", run_notification_widget)

    pm = ProcessManager()
    config_loader = ConfigLoader("config.json", pm, window.compositor, after_reload=reapply_clip)
    config = config_loader.load()
    config_loader.apply_config(config)

    # --- Command-file watcher for Pomodoro controls (POMO-04) ---
    config_dir = os.path.dirname(os.path.abspath("config.json"))
    cmd_path = os.path.join(config_dir, "pomodoro_command.json")

    cmd_watcher = QFileSystemWatcher()
    # Watch the directory so we catch file creation (not just modification)
    cmd_watcher.addPath(config_dir)

    def _on_cmd_dir_changed(path: str):
        """Check if pomodoro_command.json appeared or changed."""
        if not os.path.exists(cmd_path):
            return
        try:
            with open(cmd_path, encoding="utf-8") as f:
                data = json.load(f)
            command = data.get("cmd")
            if command in ("start", "pause", "reset"):
                pm.send_control_signal("pomodoro", command)
                print(f"[CommandWatcher] forwarded '{command}' to pomodoro", flush=True)
            os.unlink(cmd_path)
        except (OSError, json.JSONDecodeError) as exc:
            print(f"[CommandWatcher] error: {exc}", flush=True)

    cmd_watcher.directoryChanged.connect(_on_cmd_dir_changed)
    window._cmd_watcher = cmd_watcher  # prevent GC

    # Start drain timer — polls all queues at 50ms, updates compositor
    drain_timer = QueueDrainTimer(pm, window.compositor, interval_ms=50)
    drain_timer.start()

    # Keep references alive
    window._pm = pm
    window._drain_timer = drain_timer
    window._config_loader = config_loader

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
