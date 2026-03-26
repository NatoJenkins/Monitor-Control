import queue
import time
from widgets.base import WidgetBase
from shared.message_schema import FrameData


class DummyWidget(WidgetBase):
    def run(self) -> None:
        width = self.config.get("width", 200)
        height = self.config.get("height", 515)
        # Solid teal rectangle — RGBA bytes
        rgba = bytes([0, 128, 128, 255]) * (width * height)
        while True:
            frame = FrameData(
                widget_id=self.widget_id,
                width=width,
                height=height,
                rgba_bytes=rgba,
            )
            try:
                self.out_queue.put(frame, block=False)  # IPC-01: NEVER block=True
            except queue.Full:
                pass  # silently drop frame if host drain is slow
            time.sleep(0.05)  # push at ~20 Hz


def run_dummy_widget(widget_id: str, config: dict, out_queue) -> None:
    """Subprocess entry point. Called by ProcessManager."""
    widget = DummyWidget(widget_id, config, out_queue)
    widget.run()
