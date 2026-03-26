from abc import ABC, abstractmethod
import multiprocessing


class WidgetBase(ABC):
    def __init__(self, widget_id: str, config: dict, out_queue: multiprocessing.Queue):
        self.widget_id = widget_id
        self.config = config
        self.out_queue = out_queue

    @abstractmethod
    def run(self) -> None:
        """Main loop. Runs in subprocess. Push FrameData to self.out_queue."""
