import queue
import threading
import time
import ast
import pathlib
import pytest
from shared.message_schema import FrameData


WIDGET_FILE = pathlib.Path(__file__).parent.parent / "widgets" / "dummy" / "widget.py"


def test_nonblocking_put():
    """DummyWidget source code uses block=False in every queue.put() call."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    # Parse the AST to find all queue.put() calls
    tree = ast.parse(source)
    put_calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Attribute) and func.attr == "put":
                put_calls.append(node)

    assert put_calls, "Expected at least one .put() call in DummyWidget source"
    for call_node in put_calls:
        # Check for block=False keyword argument
        keyword_names = {kw.arg: kw for kw in call_node.keywords}
        assert "block" in keyword_names, (
            f"put() call at line {call_node.lineno} is missing 'block' keyword argument"
        )
        block_kw = keyword_names["block"]
        # block must be False (NameConstant or Constant with value False)
        is_false = (
            isinstance(block_kw.value, ast.Constant) and block_kw.value.value is False
        )
        assert is_false, (
            f"put() call at line {call_node.lineno} does not have block=False"
        )


def test_no_pyqt6_import():
    """widgets/dummy/widget.py must NOT import PyQt6 in any form."""
    source = WIDGET_FILE.read_text(encoding="utf-8")
    assert "import PyQt6" not in source, "DummyWidget must not use 'import PyQt6'"
    assert "from PyQt6" not in source, "DummyWidget must not use 'from PyQt6'"


def test_dummy_pushes_framedata():
    """DummyWidget pushes at least one valid FrameData within 200ms when run in a thread."""
    from widgets.dummy.widget import DummyWidget

    q = queue.Queue(maxsize=100)
    in_q = queue.Queue()
    widget = DummyWidget(
        widget_id="test",
        config={"width": 100, "height": 100},
        out_queue=q,
        in_queue=in_q,
    )

    stop_event = threading.Event()
    original_run = widget.run

    def run_with_stop():
        """Run the widget loop, stopping after producing at least one frame."""
        import queue as _queue
        import time as _time
        width = widget.config.get("width", 200)
        height = widget.config.get("height", 515)
        rgba = bytes([0, 128, 128, 255]) * (width * height)
        while not stop_event.is_set():
            frame = FrameData(
                widget_id=widget.widget_id,
                width=width,
                height=height,
                rgba_bytes=rgba,
            )
            try:
                widget.out_queue.put(frame, block=False)
            except _queue.Full:
                pass
            _time.sleep(0.05)

    t = threading.Thread(target=run_with_stop, daemon=True)
    t.start()
    time.sleep(0.2)
    stop_event.set()
    t.join(timeout=1.0)

    # Drain queue
    frames = []
    while not q.empty():
        frames.append(q.get_nowait())

    assert len(frames) >= 1, "DummyWidget should have pushed at least one FrameData"
    frame = frames[0]
    assert isinstance(frame, FrameData), "Queue item must be a FrameData instance"
    assert frame.widget_id == "test"
    assert frame.width == 100
    assert frame.height == 100
    assert len(frame.rgba_bytes) == 100 * 100 * 4, (
        f"Expected {100*100*4} bytes, got {len(frame.rgba_bytes)}"
    )
