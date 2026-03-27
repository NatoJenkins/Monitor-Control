from abc import ABC, abstractmethod
import multiprocessing
import queue
from shared.message_schema import ConfigUpdateMessage


class WidgetBase(ABC):
    def __init__(self, widget_id: str, config: dict,
                 out_queue: multiprocessing.Queue,
                 in_queue: multiprocessing.Queue):
        self.widget_id = widget_id
        self.config = config
        self.out_queue = out_queue
        self.in_queue = in_queue

    def poll_config_update(self) -> dict | None:
        """Call from render loop. Returns new config dict or None."""
        try:
            msg = self.in_queue.get_nowait()
            if isinstance(msg, ConfigUpdateMessage):
                return msg.config
        except queue.Empty:
            pass
        return None

    @abstractmethod
    def run(self) -> None:
        """Main loop. Runs in subprocess. Push FrameData to self.out_queue."""
