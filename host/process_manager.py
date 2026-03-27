import multiprocessing
import queue
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
        # On Windows, terminate() calls TerminateProcess() — immediate hard kill.
        # Do NOT call proc.join() here: it deadlocks the Qt main thread because the
        # child's internal multiprocessing.Queue feeder thread may be blocked trying
        # to flush to the pipe, and join() waits for the child to exit while nobody
        # is reading the pipe (drain timer is also on the main thread, so blocked).
        # Daemon processes are collected by the OS when the parent exits.
        proc.terminate()

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
