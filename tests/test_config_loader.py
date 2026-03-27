"""
Tests for config.json schema, ConfigUpdateMessage, bidirectional queue (Task 1),
and ConfigLoader with QFileSystemWatcher + reconcile logic (Task 2).
"""
import json
import multiprocessing
import queue
import sys
import pytest
from unittest.mock import MagicMock, patch, call
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QRect


# ---------------------------------------------------------------------------
# QApplication fixture (required for QFileSystemWatcher / QTimer)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def qapp():
    """Ensure a QApplication instance exists for Qt objects."""
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app


# ---------------------------------------------------------------------------
# tmp_config_path fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_config_path(tmp_path):
    """Write a minimal valid config.json to a temp directory and return its path."""
    cfg = {
        "layout": {"display": {"width": 1920, "height": 515}},
        "widgets": [
            {
                "id": "dummy",
                "type": "dummy",
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 515,
                "settings": {},
            }
        ],
    }
    p = tmp_path / "config.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    return str(p)


# ===========================================================================
# TASK 1 TESTS
# ===========================================================================

# --- config.json schema ---

def test_config_json_valid_schema():
    """config.json has 'layout' and 'widgets' keys with pomodoro + calendar entries."""
    from shared.paths import get_config_path
    with open(get_config_path(), encoding="utf-8") as f:
        data = json.load(f)
    assert "layout" in data, "config.json must contain 'layout' key"
    assert "widgets" in data, "config.json must contain 'widgets' key"
    widget_ids = [w["id"] for w in data["widgets"]]
    assert "pomodoro" in widget_ids, "config.json must contain a 'pomodoro' widget (Phase 3)"
    assert "calendar" in widget_ids, "config.json must contain a 'calendar' widget (Phase 3)"


# --- ConfigUpdateMessage ---

def test_config_update_message_fields():
    """ConfigUpdateMessage has widget_id and config fields."""
    from shared.message_schema import ConfigUpdateMessage
    msg = ConfigUpdateMessage(widget_id="x", config={"k": 1})
    assert msg.widget_id == "x"
    assert msg.config == {"k": 1}


# --- ProcessManager bidirectional queue ---

def test_process_manager_creates_inbound_queue():
    """ProcessManager.start_widget stores a 3-tuple (proc, out_q, in_q)."""
    from host.process_manager import ProcessManager

    pm = ProcessManager()
    try:
        # Use a module-level worker that is picklable for spawn
        from tests.test_process_manager import _simple_worker
        pm.start_widget("w1", _simple_worker, {})
        entry = pm._widgets.get("w1")
        assert entry is not None, "Widget 'w1' should be in _widgets"
        assert len(entry) == 3, f"Expected 3-tuple, got {len(entry)}-tuple"
        proc, out_q, in_q = entry
        assert isinstance(out_q, multiprocessing.queues.Queue)
        assert isinstance(in_q, multiprocessing.queues.Queue)
    finally:
        pm.stop_all()


def test_send_config_update_delivers_message():
    """send_config_update puts a ConfigUpdateMessage on the in_queue."""
    from host.process_manager import ProcessManager
    from shared.message_schema import ConfigUpdateMessage

    # Mock a 3-tuple entry with a real Queue as in_q
    pm = ProcessManager()
    in_q = multiprocessing.Queue(maxsize=5)
    mock_proc = MagicMock()
    mock_out_q = MagicMock()
    pm._widgets["w1"] = (mock_proc, mock_out_q, in_q)

    pm.send_config_update("w1", {"color": "blue"})

    msg = in_q.get_nowait()
    assert isinstance(msg, ConfigUpdateMessage)
    assert msg.widget_id == "w1"
    assert msg.config == {"color": "blue"}


def test_send_config_update_noop_for_missing_widget():
    """send_config_update is a silent no-op for unknown widget_id."""
    from host.process_manager import ProcessManager

    pm = ProcessManager()
    # Must not raise
    pm.send_config_update("nonexistent", {"x": 1})


def test_send_config_update_drops_on_full_queue():
    """send_config_update drops message silently when in_queue is full."""
    from host.process_manager import ProcessManager

    pm = ProcessManager()
    in_q = multiprocessing.Queue(maxsize=1)
    in_q.put_nowait("already_full")
    pm._widgets["w1"] = (MagicMock(), MagicMock(), in_q)

    # Should not raise even though queue is full
    pm.send_config_update("w1", {"x": 1})


# --- WidgetBase with in_queue ---

def test_widget_base_accepts_in_queue():
    """WidgetBase.__init__ accepts in_queue as fourth parameter."""
    from widgets.base import WidgetBase
    import inspect

    sig = inspect.signature(WidgetBase.__init__)
    params = list(sig.parameters.keys())
    assert "in_queue" in params, "WidgetBase.__init__ must accept 'in_queue' parameter"


def test_widget_base_poll_config_update():
    """poll_config_update returns config dict when ConfigUpdateMessage is on in_queue."""
    from widgets.base import WidgetBase
    from shared.message_schema import ConfigUpdateMessage

    class ConcreteWidget(WidgetBase):
        def run(self):
            pass

    in_q = queue.Queue()
    in_q.put(ConfigUpdateMessage(widget_id="w", config={"size": 42}))
    widget = ConcreteWidget("w", {}, queue.Queue(), in_q)
    result = widget.poll_config_update()
    assert result == {"size": 42}


def test_widget_base_poll_config_update_returns_none_on_empty():
    """poll_config_update returns None when in_queue is empty."""
    from widgets.base import WidgetBase

    class ConcreteWidget(WidgetBase):
        def run(self):
            pass

    in_q = queue.Queue()
    widget = ConcreteWidget("w", {}, queue.Queue(), in_q)
    result = widget.poll_config_update()
    assert result is None


# --- Compositor add_slot / remove_slot ---

def test_compositor_add_remove_slot(qapp):
    """add_slot adds a slot; remove_slot removes it."""
    from host.compositor import Compositor
    from PyQt6.QtCore import QRect

    compositor = Compositor(MagicMock())
    compositor.add_slot("w1", QRect(0, 0, 100, 100))
    assert "w1" in compositor._slots, "Slot should be present after add_slot"

    compositor.remove_slot("w1")
    assert "w1" not in compositor._slots, "Slot should be absent after remove_slot"


# ===========================================================================
# TASK 2 TESTS
# ===========================================================================

def test_config_loader_load_returns_dict(qapp, tmp_config_path):
    """ConfigLoader.load() returns a dict with 'widgets' key."""
    from host.config_loader import ConfigLoader

    pm = MagicMock()
    compositor = MagicMock()
    loader = ConfigLoader(tmp_config_path, pm, compositor)
    result = loader.load()
    assert isinstance(result, dict)
    assert "widgets" in result


def test_config_loader_watcher_readds_path(qapp, tmp_config_path):
    """_on_file_changed re-adds the config path to the watcher."""
    from host.config_loader import ConfigLoader

    pm = MagicMock()
    compositor = MagicMock()
    loader = ConfigLoader(tmp_config_path, pm, compositor)

    with patch.object(loader._watcher, "addPath") as mock_add:
        loader._on_file_changed(tmp_config_path)
        mock_add.assert_called_with(loader._path)


def test_config_loader_debounce_collapses(qapp, tmp_config_path):
    """Two rapid _on_file_changed calls restart the debounce (start called twice, fires once)."""
    from host.config_loader import ConfigLoader

    pm = MagicMock()
    compositor = MagicMock()
    loader = ConfigLoader(tmp_config_path, pm, compositor)

    with patch.object(loader._debounce, "start") as mock_start:
        loader._on_file_changed(tmp_config_path)
        loader._on_file_changed(tmp_config_path)
        assert mock_start.call_count == 2, "Debounce timer.start() should be called on each file change"


def test_reconcile_stops_removed_widget(qapp, tmp_config_path):
    """_reconcile stops a widget that exists in old_config but not in new_config."""
    from host.config_loader import ConfigLoader

    pm = MagicMock()
    compositor = MagicMock()
    loader = ConfigLoader(tmp_config_path, pm, compositor)
    loader._current = {"widgets": [{"id": "A", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100}]}

    loader._reconcile(
        old_config={"widgets": [{"id": "A", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100}]},
        new_config={"widgets": []},
    )

    pm.stop_widget.assert_called_once_with("A")
    compositor.remove_slot.assert_called_once_with("A")


def test_reconcile_starts_added_widget(qapp, tmp_config_path):
    """_reconcile starts a widget present in new_config but not old_config."""
    from host.config_loader import ConfigLoader
    from host.config_loader import register_widget_type

    pm = MagicMock()
    compositor = MagicMock()
    loader = ConfigLoader(tmp_config_path, pm, compositor)

    mock_fn = MagicMock()
    register_widget_type("dummy", mock_fn)

    loader._reconcile(
        old_config={"widgets": []},
        new_config={"widgets": [{"id": "B", "type": "dummy", "x": 0, "y": 0, "width": 200, "height": 100}]},
    )

    pm.start_widget.assert_called_once_with("B", mock_fn, {"id": "B", "type": "dummy", "x": 0, "y": 0, "width": 200, "height": 100})


def test_reconcile_sends_config_update_on_change(qapp, tmp_config_path):
    """_reconcile sends CONFIG_UPDATE when a widget's settings change."""
    from host.config_loader import ConfigLoader

    pm = MagicMock()
    compositor = MagicMock()
    loader = ConfigLoader(tmp_config_path, pm, compositor)

    old_w = {"id": "C", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100, "settings": {"color": "red"}}
    new_w = {"id": "C", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100, "settings": {"color": "blue"}}

    loader._reconcile(
        old_config={"widgets": [old_w]},
        new_config={"widgets": [new_w]},
    )

    pm.send_config_update.assert_called_once_with("C", new_w)


def test_reconcile_removal_before_addition(qapp, tmp_config_path):
    """stop_widget calls precede start_widget calls in reconcile."""
    from host.config_loader import ConfigLoader
    from host.config_loader import register_widget_type

    pm = MagicMock()
    compositor = MagicMock()
    # Use a shared call log via Manager to track order across both mocks
    call_log = []
    pm.stop_widget.side_effect = lambda wid: call_log.append(("stop", wid))
    pm.start_widget.side_effect = lambda wid, fn, cfg: call_log.append(("start", wid))

    mock_fn = MagicMock()
    register_widget_type("dummy", mock_fn)

    loader = ConfigLoader(tmp_config_path, pm, compositor)
    loader._reconcile(
        old_config={"widgets": [{"id": "OLD", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100}]},
        new_config={"widgets": [{"id": "NEW", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100}]},
    )

    stop_indices = [i for i, (op, _) in enumerate(call_log) if op == "stop"]
    start_indices = [i for i, (op, _) in enumerate(call_log) if op == "start"]
    assert stop_indices, "Expected at least one stop_widget call"
    assert start_indices, "Expected at least one start_widget call"
    assert max(stop_indices) < min(start_indices), "All stop_widget calls must precede all start_widget calls"


def test_apply_config_starts_all_widgets(qapp, tmp_config_path):
    """apply_config calls start_widget and add_slot for each widget in config."""
    from host.config_loader import ConfigLoader, register_widget_type

    pm = MagicMock()
    compositor = MagicMock()

    mock_fn = MagicMock()
    register_widget_type("dummy", mock_fn)

    loader = ConfigLoader(tmp_config_path, pm, compositor)
    cfg = {
        "layout": {"display": {"width": 1920, "height": 515}},
        "widgets": [
            {"id": "w1", "type": "dummy", "x": 0, "y": 0, "width": 100, "height": 100},
            {"id": "w2", "type": "dummy", "x": 100, "y": 0, "width": 200, "height": 100},
        ],
    }
    loader.apply_config(cfg)

    assert pm.start_widget.call_count == 2, f"Expected 2 start_widget calls, got {pm.start_widget.call_count}"
    assert compositor.add_slot.call_count == 2, f"Expected 2 add_slot calls, got {compositor.add_slot.call_count}"
