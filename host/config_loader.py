import json
import os
from typing import Callable
from PyQt6.QtCore import QFileSystemWatcher, QTimer, QRect


WIDGET_REGISTRY: dict[str, object] = {}


def register_widget_type(type_name: str, target_fn) -> None:
    """Register a widget type name to its subprocess entry function."""
    WIDGET_REGISTRY[type_name] = target_fn


class ConfigLoader:
    def __init__(self, path: str, process_manager, compositor):
        self._path = os.path.abspath(path)
        self._pm = process_manager
        self._compositor = compositor
        self._current: dict = {}

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(100)
        self._debounce.timeout.connect(self._do_reload)

        self._watcher = QFileSystemWatcher()
        self._watcher.addPath(self._path)
        self._watcher.fileChanged.connect(self._on_file_changed)

    @property
    def current_config(self) -> dict:
        return self._current

    def load(self) -> dict:
        """Load config synchronously. Called once at startup."""
        with open(self._path, encoding="utf-8") as f:
            self._current = json.load(f)
        return self._current

    def apply_config(self, config: dict) -> None:
        """Apply a config dict: set compositor slots and start all widgets."""
        for widget_cfg in config.get("widgets", []):
            wid = widget_cfg["id"]
            slot = QRect(widget_cfg["x"], widget_cfg["y"],
                         widget_cfg["width"], widget_cfg["height"])
            self._compositor.add_slot(wid, slot)
            target_fn = WIDGET_REGISTRY.get(widget_cfg["type"])
            if target_fn is not None:
                self._pm.start_widget(wid, target_fn, widget_cfg)

    def _on_file_changed(self, path: str) -> None:
        # CRITICAL: re-add after atomic replace — watcher drops path on rename
        self._watcher.addPath(self._path)
        # Restart debounce timer to collapse double-fires into single reload
        self._debounce.start()

    def _do_reload(self) -> None:
        if not os.path.exists(self._path):
            return
        try:
            with open(self._path, encoding="utf-8") as f:
                new_config = json.load(f)
        except (OSError, json.JSONDecodeError):
            return  # partial write; next event will retry
        old_config = self._current
        self._current = new_config
        self._reconcile(old_config, new_config)

    def _reconcile(self, old_config: dict, new_config: dict) -> None:
        old_widgets = {w["id"]: w for w in old_config.get("widgets", [])}
        new_widgets = {w["id"]: w for w in new_config.get("widgets", [])}

        # STOP removed widgets FIRST (before starting new ones)
        for wid in set(old_widgets) - set(new_widgets):
            self._pm.stop_widget(wid)
            self._compositor.remove_slot(wid)

        # START added widgets
        for wid in set(new_widgets) - set(old_widgets):
            widget_cfg = new_widgets[wid]
            slot = QRect(widget_cfg["x"], widget_cfg["y"],
                         widget_cfg["width"], widget_cfg["height"])
            self._compositor.add_slot(wid, slot)
            target_fn = WIDGET_REGISTRY.get(widget_cfg["type"])
            if target_fn is not None:
                self._pm.start_widget(wid, target_fn, widget_cfg)

        # Send CONFIG_UPDATE to changed widgets (not removed, not new)
        for wid in set(old_widgets) & set(new_widgets):
            if old_widgets[wid] != new_widgets[wid]:
                self._pm.send_config_update(wid, new_widgets[wid])
