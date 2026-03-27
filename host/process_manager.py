import multiprocessing
import queue
import time
from shared.message_schema import ConfigUpdateMessage


class ProcessManager:
    def __init__(self):
        self._widgets: dict[str, tuple[multiprocessing.Process, multiprocessing.Queue, multiprocessing.Queue]] = {}

    def start_widget(self, widget_id: str, target_fn, config: dict) -> None:
        out_q = multiprocessing.Queue(maxsize=10)
        in_q = multiprocessing.Queue(maxsize=5)
        proc = multiprocessing.Process(
            target=target_fn,
            args=(widget_id, config, out_q, in_q),
            daemon=True,
        )
        proc.start()
        self._widgets[widget_id] = (proc, out_q, in_q)

    def stop_widget(self, widget_id: str) -> None:
        if widget_id not in self._widgets:
            return
        proc, out_q, in_q = self._widgets.pop(widget_id)
        proc.terminate()
        # BLOCKER: drain out_queue FULLY before join — prevents feeder thread deadlock
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            try:
                out_q.get_nowait()
            except queue.Empty:
                break
        # Drain in_queue as well
        while True:
            try:
                in_q.get_nowait()
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
        proc, _, _ = entry
        return proc.is_alive()

    def send_config_update(self, widget_id: str, config: dict) -> None:
        entry = self._widgets.get(widget_id)
        if entry is None:
            return
        _, _, in_q = entry
        try:
            in_q.put_nowait(ConfigUpdateMessage(widget_id=widget_id, config=config))
        except queue.Full:
            pass

    @property
    def queues(self) -> dict[str, multiprocessing.Queue]:
        return {wid: out_q for wid, (_, out_q, _) in self._widgets.items()}

    @property
    def widget_ids(self) -> list[str]:
        return list(self._widgets.keys())
