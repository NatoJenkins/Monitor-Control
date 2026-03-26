import multiprocessing
import time
import pytest
from shared.message_schema import FrameData
from widgets.dummy.widget import run_dummy_widget


@pytest.mark.integration
def test_dummy_frame_received():
    """End-to-end: dummy widget subprocess pushes FrameData through a real multiprocessing.Queue."""
    q = multiprocessing.Queue(maxsize=20)
    widget_id = "dummy"
    config = {"width": 200, "height": 515}

    proc = multiprocessing.Process(
        target=run_dummy_widget,
        args=(widget_id, config, q),
        daemon=True,
    )
    proc.start()

    # Allow time for the subprocess to push at least one frame (~20 Hz = 50ms per frame)
    time.sleep(0.5)

    proc.terminate()
    proc.join(timeout=3)

    # Drain the queue
    frames = []
    while True:
        try:
            frames.append(q.get_nowait())
        except Exception:
            break

    assert len(frames) >= 1, "Expected at least one FrameData from the dummy widget subprocess"

    frame = frames[0]
    assert isinstance(frame, FrameData), f"Expected FrameData, got {type(frame)}"
    assert frame.widget_id == widget_id, f"Expected widget_id={widget_id!r}, got {frame.widget_id!r}"
    assert frame.width == config["width"], f"Expected width={config['width']}, got {frame.width}"
    assert frame.height == config["height"], f"Expected height={config['height']}, got {frame.height}"
    expected_bytes = config["width"] * config["height"] * 4
    assert len(frame.rgba_bytes) == expected_bytes, (
        f"Expected {expected_bytes} rgba_bytes, got {len(frame.rgba_bytes)}"
    )
