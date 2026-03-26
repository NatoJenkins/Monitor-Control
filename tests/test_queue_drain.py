import queue
import sys
import pytest
from unittest.mock import MagicMock, call, patch
from PyQt6.QtWidgets import QApplication
from host.queue_drain import QueueDrainTimer
from shared.message_schema import FrameData


@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication exists for QTimer construction."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


def _make_mock_pm_with_queue(items: list, widget_id: str = "w1", alive: bool = True):
    """Build a mock ProcessManager with a real queue pre-filled with items."""
    q = queue.Queue()
    for item in items:
        q.put(item)

    pm = MagicMock()
    pm.queues = {widget_id: q}
    pm.is_alive.return_value = alive
    return pm, q


def test_drain_loop_empties_queue(qapp):
    """_drain() empties the queue and calls update_frame once per item, schedule_repaint once."""
    frames = [
        FrameData(widget_id="w1", width=10, height=10, rgba_bytes=b"\x00" * 400),
        FrameData(widget_id="w1", width=10, height=10, rgba_bytes=b"\x01" * 400),
        FrameData(widget_id="w1", width=10, height=10, rgba_bytes=b"\x02" * 400),
    ]
    pm, q = _make_mock_pm_with_queue(frames, widget_id="w1", alive=True)
    compositor = MagicMock()

    drain_timer = QueueDrainTimer(pm, compositor)
    drain_timer._drain()

    assert compositor.update_frame.call_count == 3, (
        f"Expected 3 update_frame calls, got {compositor.update_frame.call_count}"
    )
    assert compositor.schedule_repaint.call_count == 1, (
        f"Expected 1 schedule_repaint call, got {compositor.schedule_repaint.call_count}"
    )
    assert q.empty(), "Queue should be empty after drain"


def test_drain_detects_dead_process(qapp):
    """_drain() calls mark_crashed when process is not alive."""
    pm, _ = _make_mock_pm_with_queue([], widget_id="w1", alive=False)
    compositor = MagicMock()

    drain_timer = QueueDrainTimer(pm, compositor)
    drain_timer._drain()

    compositor.mark_crashed.assert_called_once_with("w1")
    assert compositor.schedule_repaint.call_count == 1, (
        "schedule_repaint should be called once even for crash detection"
    )
