import multiprocessing
import queue
import time


class ProcessManager:
    def __init__(self):
        self._widgets: dict[str, tuple[multiprocessing.Process, multiprocessing.Queue]] = {}

    def start_widget(self, widget_id: str, target_fn, config: dict) -> None:
        q = multiprocessing.Queue(maxsize=10)
        proc = multiprocessing.Process(
            target=target_fn,
            args=(widget_id, config, q),
            daemon=True,
        )
        proc.start()
        self._widgets[widget_id] = (proc, q)

    def stop_widget(self, widget_id: str) -> None:
        if widget_id not in self._widgets:
            return
        proc, q = self._widgets.pop(widget_id)
        proc.terminate()
        # BLOCKER: drain queue FULLY before join — prevents feeder thread deadlock
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                q.get_nowait()
            except queue.Empty:
                break
        proc.join(timeout=5)
        if proc.is_alive():
            proc.kill()
            proc.join(timeout=2)

    def stop_all(self) -> None:
        for widget_id in list(self._widgets):
            self.stop_widget(widget_id)

    def is_alive(self, widget_id: str) -> bool:
        entry = self._widgets.get(widget_id)
        if entry is None:
            return False
        proc, _ = entry
        return proc.is_alive()

    @property
    def queues(self) -> dict[str, multiprocessing.Queue]:
        return {wid: q for wid, (_, q) in self._widgets.items()}

    @property
    def widget_ids(self) -> list[str]:
        return list(self._widgets.keys())
