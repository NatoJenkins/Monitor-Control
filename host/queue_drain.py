from PyQt6.QtCore import QTimer
import queue


class QueueDrainTimer:
    def __init__(self, process_manager, compositor, interval_ms: int = 50):
        self._pm = process_manager
        self._compositor = compositor
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._drain)

    def start(self) -> None:
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def _drain(self) -> None:
        updated = False
        for widget_id in list(self._pm.queues):
            if not self._pm.is_alive(widget_id):
                self._compositor.mark_crashed(widget_id)
                updated = True
                continue
            q = self._pm.queues[widget_id]
            try:
                while True:
                    msg = q.get_nowait()
                    self._compositor.update_frame(widget_id, msg)
                    updated = True
            except queue.Empty:
                pass
        if updated:
            self._compositor.schedule_repaint()
