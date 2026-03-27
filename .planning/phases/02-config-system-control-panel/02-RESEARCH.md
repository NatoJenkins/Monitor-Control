# Phase 2: Config System + Control Panel — Research

**Researched:** 2026-03-26
**Domain:** PyQt6 QFileSystemWatcher, atomic file I/O, Python config schema, multiprocessing bidirectional queues, PyQt6 QMainWindow control panel
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CFG-01 | `config.json` defines display layout (slot names, geometries) and per-widget settings; single source of truth read by host on startup | Config schema design and `ConfigLoader` patterns documented; dataclass-based typed config confirmed standard for this stack |
| CFG-02 | `QFileSystemWatcher` monitors `config.json`; after each `fileChanged` event the path is re-added (to survive atomic file replacement) and the reload is debounced 100 ms | QFileSystemWatcher drop-after-rename confirmed by official Qt docs; re-add pattern confirmed; double-fire confirmed (Qt Forum); `QTimer.singleShot` debounce verified as correct solution |
| CFG-03 | Config hot-reload diffs old vs new config and reconciles running widgets (stop removed, start added, send CONFIG_UPDATE to changed) without restarting host | Bidirectional queue pattern (two `multiprocessing.Queue` objects) verified; dict diff pattern for config reconciliation documented |
| CTRL-01 | A separate PyQt6 `QMainWindow` process provides the only user-facing configuration surface | Subprocess launch via `subprocess.Popen` or `multiprocessing.Process` with `python -m control_panel` confirmed standard; ClipCursor architectural constraint documented in REQUIREMENTS.md |
| CTRL-02 | Control panel reads and writes `config.json` atomically (write to temp file, then `os.replace`) and is the sole writer | `os.replace()` confirmed atomic on Windows (uses MoveFileEx internally); temp file must be on same filesystem (same directory) — verified |
| CTRL-03 | Control panel exposes widget layout configuration and per-widget settings (Pomodoro durations, clock format); changes saved to config.json picked up by host's file watcher | QFormLayout + QGroupBox + QTabWidget pattern confirmed; `QSpinBox`, `QLineEdit`, `QComboBox` are the correct input widgets |
</phase_requirements>

---

## Summary

Phase 2 has one significant technical risk (QFileSystemWatcher + atomic file replace) that is fully understood and has a verified mitigation. Everything else in this phase is well-trodden PyQt6 territory with no surprises.

The core problem: Python's `os.replace()` is an atomic file replace at the OS level (MoveFileEx on Windows). This causes the old inode to disappear, which causes `QFileSystemWatcher` to drop the path from its watch list after emitting `fileChanged`. If you don't re-add the path, the second save is never detected. The fix is two lines in the `fileChanged` slot: re-add the path unconditionally (it either already exists or you're adding a new watch), then schedule the reload via `QTimer.singleShot(100, self._do_reload)` to debounce the double-fire that occurs when some editors save an empty file then the real content.

The CONFIG_UPDATE delivery problem (CFG-03) is resolved by extending `ProcessManager` with an inbound queue per widget. Phase 1 built `ProcessManager` with one queue per widget (widget → host only). Phase 2 adds a second queue per widget (host → widget) and passes it as a second argument to the widget subprocess. The `WidgetBase` contract gains an `in_queue` field. The host sends a `ConfigUpdateMessage` dataclass to the inbound queue; the widget polls it non-blocking on its render tick. This is a clean, well-understood pattern.

The control panel is a separate Python process (`python -m control_panel`) with its own `QApplication` and `QMainWindow`. It never communicates with the host via sockets or shared memory — the only interface is `config.json` on disk. The host's file watcher picks up changes. This single-file-as-interface design avoids all inter-process synchronization concerns.

**Primary recommendation:** Implement 02-01 (ConfigLoader + watcher) first and validate the double-save success criterion before building the control panel. The watcher re-add pattern is the sole HIGH risk in this phase and must be hardware-verified early.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt6 | 6.10.2 | `QFileSystemWatcher`, `QTimer.singleShot`, `QMainWindow`, all control panel widgets | Already the project stack; all needed APIs present and verified |
| Python stdlib: `json` | built-in | Read/write `config.json` | No external dependency; sufficient for flat config schema |
| Python stdlib: `os` | built-in | `os.replace()` for atomic write, `os.path.exists()` for re-add guard | `os.replace()` is atomic on Windows (MoveFileEx); no library needed |
| Python stdlib: `tempfile` | built-in | `tempfile.NamedTemporaryFile` or `tempfile.mkstemp` for temp file creation in same dir | Must be in same directory as target to guarantee same filesystem |
| Python stdlib: `dataclasses` | built-in | Typed config schema and message types (`WidgetConfig`, `LayoutConfig`, `ConfigUpdateMessage`) | Consistent with existing `FrameData` in `shared/message_schema.py` |
| Python stdlib: `multiprocessing` | built-in | Second inbound queue per widget for CONFIG_UPDATE delivery | Same pattern as existing outbound queue; no new dependencies |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `copy` (stdlib) | built-in | Deep copy of config dict for diff comparison | Use when comparing old vs new config to detect changes |
| `subprocess` (stdlib) | built-in | Launch control panel as separate process from host (if needed) | Use `subprocess.Popen([sys.executable, '-m', 'control_panel'])` for OS-managed launch |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `os.replace()` + `tempfile` | `atomicwrites` PyPI library | Library wraps the same OS call; adds a dependency with no benefit for this use case |
| Plain `dict` config | `pydantic` validation | Pydantic adds dependency and complexity; a dataclass schema with explicit field access is sufficient and consistent with existing code style |
| `subprocess.Popen` for control panel launch | `multiprocessing.Process` | Either works; `subprocess.Popen([sys.executable, '-m', 'control_panel'])` is simpler for a fully independent process that the host doesn't need to join |
| `QTimer.singleShot` debounce | `threading.Timer` | `QTimer.singleShot` runs on the Qt event loop and is safe to call from the main thread; `threading.Timer` fires on a background thread, requiring thread-safe compositor access |

**No new packages to install.** All stack components are either in the existing `requirements.txt` (PyQt6 6.10.2) or Python stdlib. The control panel process uses the same venv.

---

## Architecture Patterns

### Recommended Project Structure

```
host/
├── config_loader.py     # ConfigLoader: load, watch, diff, reconcile
├── main.py              # Updated: load config, set compositor slots from config
├── process_manager.py   # Updated: add in_queue per widget, deliver CONFIG_UPDATE
├── ...

shared/
├── message_schema.py    # Updated: add ConfigUpdateMessage dataclass

control_panel/
├── __init__.py
├── __main__.py          # Entry point: python -m control_panel
├── main_window.py       # ControlPanelWindow(QMainWindow)
├── config_io.py         # atomic_write_config(path, data)

tests/
├── test_config_loader.py
├── test_config_io.py
├── test_control_panel_window.py  # widget instantiation + form fields (no real file I/O)
```

### Pattern 1: QFileSystemWatcher Re-Add + Debounce

**What:** On `fileChanged`, unconditionally re-add the path (it dropped after atomic replace), then arm a one-shot 100ms timer. If `fileChanged` fires again within the 100ms window, the timer is restarted. The reload function runs only once per save event.

**When to use:** Always — for every `fileChanged` connection in this project.

**Implementation:**
```python
# Source: Qt docs https://doc.qt.io/qt-6/qfilesystemwatcher.html
#         + Qt Forum https://forum.qt.io/topic/41401/

from PyQt6.QtCore import QFileSystemWatcher, QTimer


class ConfigLoader:
    def __init__(self, path: str):
        self._path = path
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(100)
        self._debounce_timer.timeout.connect(self._do_reload)

        self._watcher = QFileSystemWatcher()
        self._watcher.addPath(path)
        self._watcher.fileChanged.connect(self._on_file_changed)

    def _on_file_changed(self, path: str) -> None:
        # CRITICAL: re-add after atomic replace — watcher drops path on rename
        if path not in self._watcher.files():
            self._watcher.addPath(path)
        # Debounce: restart 100ms timer to collapse double-fires
        self._debounce_timer.start()

    def _do_reload(self) -> None:
        # Read config, diff, reconcile
        ...
```

### Pattern 2: Bidirectional Queue — Inbound Queue for CONFIG_UPDATE

**What:** Each widget gets two queues: the existing outbound queue (widget → host, frame data) and a new inbound queue (host → widget, control messages). `ProcessManager.start_widget` creates both; the subprocess entry point receives both as arguments.

**When to use:** Any time the host needs to send a message to a running widget without killing it.

**Implementation:**
```python
# shared/message_schema.py addition
from dataclasses import dataclass
from typing import Any

@dataclass
class ConfigUpdateMessage:
    widget_id: str
    config: dict[str, Any]
```

```python
# host/process_manager.py — updated start_widget signature
def start_widget(self, widget_id: str, target_fn, config: dict) -> None:
    out_q = multiprocessing.Queue(maxsize=10)   # widget → host (frames)
    in_q = multiprocessing.Queue(maxsize=5)     # host → widget (config updates)
    proc = multiprocessing.Process(
        target=target_fn,
        args=(widget_id, config, out_q, in_q),  # in_q added
        daemon=True,
    )
    proc.start()
    self._widgets[widget_id] = (proc, out_q, in_q)

def send_config_update(self, widget_id: str, config: dict) -> None:
    """Send CONFIG_UPDATE to running widget. Non-blocking — drops if queue full."""
    entry = self._widgets.get(widget_id)
    if entry is None:
        return
    _, _, in_q = entry
    try:
        in_q.put_nowait(ConfigUpdateMessage(widget_id=widget_id, config=config))
    except queue.Full:
        pass  # widget is not consuming; will get config on next reload
```

```python
# widgets/base.py — updated contract
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
```

**Note on backward compatibility:** `DummyWidget` must be updated to accept and ignore `in_queue`. The subprocess entry point signature changes from `(widget_id, config, out_q)` to `(widget_id, config, out_q, in_q)`.

### Pattern 3: Atomic Config Write

**What:** Write to a temp file in the same directory, then `os.replace()` to atomically swap it in.

**When to use:** All writes from the control panel.

```python
# control_panel/config_io.py
# Source: Python docs https://docs.python.org/3/library/os.html#os.replace
import json
import os
import tempfile


def atomic_write_config(path: str, data: dict) -> None:
    """Write data to path atomically. Safe against partial-write corruption."""
    dir_path = os.path.dirname(os.path.abspath(path))
    # Temp file MUST be on same filesystem as target (same directory)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp_path, path)  # atomic on Windows (MoveFileEx)
    except Exception:
        os.unlink(tmp_path)
        raise
```

### Pattern 4: Config Diff and Reconciliation

**What:** Compare old config widget list against new config widget list; classify each widget as added, removed, or changed. Only changed widgets receive CONFIG_UPDATE; only removed/added widgets are stopped/started.

```python
def _reconcile(self, old_config: dict, new_config: dict) -> None:
    old_widgets = {w["id"]: w for w in old_config.get("widgets", [])}
    new_widgets = {w["id"]: w for w in new_config.get("widgets", [])}

    # Stop removed widgets
    for wid in set(old_widgets) - set(new_widgets):
        self._pm.stop_widget(wid)
        self._compositor.remove_slot(wid)

    # Start added widgets
    for wid in set(new_widgets) - set(old_widgets):
        widget_cfg = new_widgets[wid]
        slot = QRect(widget_cfg["x"], widget_cfg["y"],
                     widget_cfg["width"], widget_cfg["height"])
        self._compositor.add_slot(wid, slot)
        self._pm.start_widget(wid, self._resolve_target_fn(widget_cfg), widget_cfg)

    # Send CONFIG_UPDATE to changed widgets
    for wid in set(old_widgets) & set(new_widgets):
        if old_widgets[wid] != new_widgets[wid]:
            self._pm.send_config_update(wid, new_widgets[wid])
```

### Pattern 5: Control Panel — Separate Process Launch

**What:** Control panel is a standard Python module with its own `QApplication`. Launched independently from the OS (not by the host). The host does not spawn it.

**When to use:** Always — cursor lockout means you can't click in the bar, so the panel is launched by the user directly (system tray, shortcut, or CLI).

```python
# control_panel/__main__.py
import sys
import multiprocessing
from PyQt6.QtWidgets import QApplication
from control_panel.main_window import ControlPanelWindow

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    app = QApplication(sys.argv)
    window = ControlPanelWindow(config_path="config.json")
    window.show()
    sys.exit(app.exec())
```

### Pattern 6: Control Panel Form Layout

**What:** `QTabWidget` with one tab per logical section (Layout, per-widget settings). Each tab uses `QFormLayout` inside a `QGroupBox` for labeled inputs.

```python
# control_panel/main_window.py (skeleton)
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout,
    QFormLayout, QGroupBox, QSpinBox, QLineEdit,
    QComboBox, QPushButton, QLabel
)

class ControlPanelWindow(QMainWindow):
    def __init__(self, config_path: str):
        super().__init__()
        self._config_path = config_path
        self._config = self._load()
        self.setWindowTitle("MonitorControl — Settings")
        self._build_ui()

    def _build_ui(self):
        tabs = QTabWidget()
        tabs.addTab(self._build_layout_tab(), "Layout")
        tabs.addTab(self._build_pomodoro_tab(), "Pomodoro")
        tabs.addTab(self._build_calendar_tab(), "Calendar")
        # Save button at bottom
        ...

    def _build_pomodoro_tab(self) -> QWidget:
        group = QGroupBox("Pomodoro Durations")
        form = QFormLayout(group)
        self._pomo_work = QSpinBox()
        self._pomo_work.setRange(1, 120)
        form.addRow("Work (min):", self._pomo_work)
        # ... short break, long break, cycles
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(group)
        layout.addStretch()
        return container
```

### Anti-Patterns to Avoid

- **Re-adding inside `if not in files()` only:** The Qt docs say to check `watcher.files().contains(path)` before calling `addPath()`, but doing it unconditionally is also safe and simpler — `addPath()` is a no-op if the path is already watched. Use unconditional re-add to avoid a TOCTOU race.
- **Debouncing with `threading.Timer`:** Creates a background thread that calls Qt APIs. Always use `QTimer.singleShot` for debouncing in Qt code — it runs on the event loop.
- **Writing config from the host:** The host is a reader only. If both host and control panel write, you risk clobbering a concurrent write. The REQUIREMENTS.md requirement CTRL-02 is architectural: host never writes config.
- **Passing file path to subprocess instead of queue:** Widgets must not read `config.json` directly. Configuration reaches widgets only through `in_queue`. This keeps the file I/O isolated to the host's `ConfigLoader`.
- **Using `QFileSystemWatcher` in the control panel:** The control panel is the writer, not the watcher. It reads config on startup and writes on save. The host watches. No watcher in the control panel.
- **`tempfile.NamedTemporaryFile` without `delete=False` on Windows:** Windows cannot `os.replace()` a file that is still open. Use `delete=False` or `mkstemp()`, close the fd, then write and replace.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Atomic file write | Custom file-lock + write + rename logic | `tempfile.mkstemp()` + `os.replace()` | `os.replace` is atomic on Windows (MoveFileEx); mkstemp creates in same dir safely |
| Double-fire debouncing | Counter-based or flag-based suppression logic | `QTimer.singleShot(100, ...)` | One-shot timer automatically handles N firings within the window; restartable with `.start()` |
| Config diff | Deep equality framework | Plain `!=` comparison on dict entries | Widget configs are flat dicts; `!=` is sufficient and readable |
| Process-to-process communication | Sockets, pipes, shared memory, file polling | `multiprocessing.Queue` | Already validated in Phase 1; consistent with existing architecture |

**Key insight:** The complexity in this phase is all in the watcher + debounce pattern. Everything else is plumbing. Don't over-engineer the config schema or the control panel — they serve a simple flat configuration with ~5 fields per widget.

---

## Common Pitfalls

### Pitfall 1: QFileSystemWatcher Loses Watch After Atomic Save (PRIMARY RISK)

**What goes wrong:** Host detects first config save but not the second. Host appears to have stale config after users save twice in a row.

**Why it happens:** `os.replace()` is a rename at the OS level. Windows does not update existing directory entries — it removes the old inode and creates a new one. `QFileSystemWatcher` held a handle to the old inode; after the rename it is gone. Qt docs explicitly state: "QFileSystemWatcher stops monitoring files once they have been renamed or removed from disk."

**How to avoid:** In the `fileChanged` slot, always call `self._watcher.addPath(path)` to re-add the path before doing anything else. Verified by official Qt docs and confirmed as the standard pattern.

**Warning signs:** Integration test — save `config.json` twice in rapid succession; if second save does not trigger reload, re-add is missing.

### Pitfall 2: Double-Fire of fileChanged on Atomic Save

**What goes wrong:** Config reload runs twice for every single save. Widget processes are stopped and restarted unnecessarily.

**Why it happens:** Some editors and Python's own `NamedTemporaryFile` write a zero-length file before the real content. This triggers two OS-level file change events and thus two `fileChanged` signals. Confirmed by Qt Forum (topic/41401): editors that "first save with 0 length and then with content" cause two signals.

**How to avoid:** `QTimer.singleShot(100, self._do_reload)` — restart the timer on every `fileChanged`. The 100ms window absorbs both signals; `_do_reload` runs once.

**Warning signs:** Log output shows two reload lines per save operation.

### Pitfall 3: NamedTemporaryFile Still Open on Windows During os.replace

**What goes wrong:** `PermissionError: [WinError 32] The process cannot access the file` when calling `os.replace()`.

**Why it happens:** Windows file locking prevents renaming an open file. `tempfile.NamedTemporaryFile` keeps the file open until `close()` is called; if you call `os.replace()` before closing, Windows raises.

**How to avoid:** Use `tempfile.mkstemp(dir=target_dir)` which returns an fd integer. Write via `os.fdopen(fd, 'w')`, call `f.close()` inside a `with` block to ensure the fd is closed, then call `os.replace()`.

**Warning signs:** `PermissionError` on Windows during config save in control panel.

### Pitfall 4: Temp File on Different Filesystem

**What goes wrong:** `os.replace()` raises `OSError: [Errno 18] Invalid cross-device link` (Linux) or fails silently (Windows fallback to non-atomic copy+delete).

**Why it happens:** If `tempfile.mkstemp()` is called without a `dir=` argument, it uses the system temp directory which may be on a different drive or mount point.

**How to avoid:** Always pass `dir=os.path.dirname(os.path.abspath(config_path))` to `mkstemp()`.

**Warning signs:** Config file writes appear to succeed but file watcher fires twice (delete + create instead of single atomic replace).

### Pitfall 5: DummyWidget Breaks After ProcessManager Signature Change

**What goes wrong:** `TypeError: run_dummy_widget() takes 3 positional arguments but 4 were given` — or vice versa, if the inbound queue is not passed.

**Why it happens:** `ProcessManager.start_widget` now passes 4 args (widget_id, config, out_q, in_q). The existing `DummyWidget` entry point accepts only 3.

**How to avoid:** Update `DummyWidget.run()` and `run_dummy_widget()` to accept `in_queue` as a fourth argument and pass it to `WidgetBase`. The `DummyWidget` does not poll it, but must accept it. All tests that call `start_widget` must also be updated.

**Warning signs:** `TypeError` on startup or in `test_process_manager.py`.

### Pitfall 6: Config Reconciliation Starts New Process Before Old One is Stopped

**What goes wrong:** Two instances of the same widget run simultaneously; compositor renders flicker between two queues.

**Why it happens:** A naive implementation calls `start_widget` before `stop_widget` completes.

**How to avoid:** The diff algorithm strictly applies removals before additions. `stop_widget` is synchronous (blocks until process dead). Only then call `start_widget` for re-added widgets.

---

## Code Examples

### Complete ConfigLoader Skeleton

```python
# host/config_loader.py
# Source: Qt docs https://doc.qt.io/qt-6/qfilesystemwatcher.html

import json
import os
from typing import Callable
from PyQt6.QtCore import QFileSystemWatcher, QTimer


class ConfigLoader:
    def __init__(self, path: str, on_reload: Callable[[dict, dict], None]):
        self._path = os.path.abspath(path)
        self._on_reload = on_reload  # callback(old_config, new_config)
        self._current: dict = {}

        self._debounce = QTimer()
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(100)
        self._debounce.timeout.connect(self._do_reload)

        self._watcher = QFileSystemWatcher()
        self._watcher.addPath(self._path)
        self._watcher.fileChanged.connect(self._on_file_changed)

    def load(self) -> dict:
        """Load and return config synchronously. Called once at startup."""
        with open(self._path, encoding="utf-8") as f:
            self._current = json.load(f)
        return self._current

    def _on_file_changed(self, path: str) -> None:
        # Re-add UNCONDITIONALLY — atomic replace drops the path from watcher
        self._watcher.addPath(self._path)
        # Restart debounce timer to collapse double-fires into single reload
        self._debounce.start()

    def _do_reload(self) -> None:
        if not os.path.exists(self._path):
            return  # file deleted; ignore
        try:
            with open(self._path, encoding="utf-8") as f:
                new_config = json.load(f)
        except (OSError, json.JSONDecodeError):
            return  # partial write; next debounce cycle will retry
        old_config = self._current
        self._current = new_config
        self._on_reload(old_config, new_config)
```

### Atomic Config Write

```python
# control_panel/config_io.py
# Source: Python docs https://docs.python.org/3/library/os.html#os.replace

import json
import os
import tempfile


def atomic_write_config(path: str, data: dict) -> None:
    path = os.path.abspath(path)
    dir_path = os.path.dirname(path)
    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        # fd is closed by the context manager; safe to replace on Windows
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
```

### ConfigUpdateMessage Schema Extension

```python
# shared/message_schema.py addition
from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class FrameData:
    widget_id: str
    width: int
    height: int
    rgba_bytes: bytes
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConfigUpdateMessage:
    """Sent host → widget via in_queue to deliver updated settings."""
    widget_id: str
    config: dict[str, Any]
```

### config.json Schema

```json
{
  "layout": {
    "display": {"width": 1920, "height": 515}
  },
  "widgets": [
    {
      "id": "pomodoro",
      "type": "pomodoro",
      "x": 0, "y": 0, "width": 400, "height": 515,
      "settings": {
        "work_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "cycles_before_long_break": 4
      }
    },
    {
      "id": "calendar",
      "type": "calendar",
      "x": 400, "y": 0, "width": 400, "height": 515,
      "settings": {
        "clock_format": "24h"
      }
    }
  ]
}
```

**Schema design notes:**
- `id` is the stable identifier used as the `widget_id` key in `ProcessManager` and `Compositor`. It must be unique.
- `type` maps to the widget implementation class (resolved by a registry dict in host).
- `x`, `y`, `width`, `height` are logical pixel coordinates within the 1920x515 bar (host-level slot QRect).
- `settings` is the widget-specific config dict; its contents are opaque to the host — passed verbatim to the subprocess and in `ConfigUpdateMessage`.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `watchdog` library for file monitoring | `QFileSystemWatcher` (Qt built-in) | Project decision (STATE.md lists watchdog 6.x as a possible stack item, but CFG-02 specifies QFileSystemWatcher) | No extra dependency; QFileSystemWatcher integrates natively with Qt event loop |
| `os.rename()` (not POSIX atomic on Windows) | `os.replace()` (Python 3.3+) | Python 3.3 | `os.replace()` is the correct cross-platform atomic rename |
| Bidirectional communication via single queue with routing | Two separate queues (one per direction) | Standard Python pattern | Simpler; avoids routing logic; matches existing project queue model |

**Deprecated/outdated:**
- `watchdog 6.x`: STATE.md mentions it but CFG-02 and the requirements explicitly specify `QFileSystemWatcher`. Do not use `watchdog`.
- `NamedTemporaryFile` on Windows without `delete=False`: Does not work for atomic replace due to file locking.

---

## Open Questions

1. **Widget type registry location**
   - What we know: `host/main.py` currently hardcodes `run_dummy_widget`. Phase 3 will add real widgets.
   - What's unclear: Whether to put a `WIDGET_REGISTRY = {"pomodoro": run_pomodoro_widget, ...}` dict in `host/main.py` or in a dedicated `host/widget_registry.py`.
   - Recommendation: Add a `WIDGET_REGISTRY` dict to `host/config_loader.py` or `host/main.py` in Phase 2 (even with only `dummy` registered). Phase 3 adds real types. This avoids a second config reload refactor in Phase 3.

2. **How the control panel is launched by the user**
   - What we know: Cursor lockout prevents in-bar interaction; the control panel must be launched externally.
   - What's unclear: Phase 2 success criteria don't require a specific launch mechanism. A desktop shortcut or system tray is out of scope.
   - Recommendation: For Phase 2, `python -m control_panel` from a terminal is sufficient. The launch mechanism is deferred.

3. **Compositor slot addition/removal API**
   - What we know: `Compositor.set_slots()` replaces the entire slot dict. Hot-reload adds/removes individual slots.
   - What's unclear: Whether to add `add_slot(wid, rect)` / `remove_slot(wid)` methods or call `set_slots()` with the full updated dict each time.
   - Recommendation: Add explicit `add_slot` / `remove_slot` methods to `Compositor` for clarity. This avoids passing the full slot dict around during reconciliation.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (already installed, `pytest.ini` present) |
| Config file | `pytest.ini` at project root |
| Quick run command | `pytest tests/ -m "not integration" -x -q` |
| Full suite command | `pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CFG-01 | ConfigLoader reads config.json on startup, returns typed dict | unit | `pytest tests/test_config_loader.py::test_load_reads_config -x` | Wave 0 |
| CFG-02 | fileChanged triggers re-add + debounce; second save also triggers reload | unit (mock QFileSystemWatcher) | `pytest tests/test_config_loader.py::test_watcher_readds_path_after_atomic_save -x` | Wave 0 |
| CFG-02 | Double-fire collapsed to single reload | unit | `pytest tests/test_config_loader.py::test_debounce_collapses_double_fire -x` | Wave 0 |
| CFG-03 | Diff: removed widget → stop_widget called; added widget → start_widget called | unit (mock ProcessManager) | `pytest tests/test_config_loader.py::test_reconcile_stops_removed_widget -x` | Wave 0 |
| CFG-03 | Diff: changed widget settings → send_config_update called, not stop/start | unit | `pytest tests/test_config_loader.py::test_reconcile_sends_config_update_on_change -x` | Wave 0 |
| CTRL-01 | ControlPanelWindow is a QMainWindow with tab widget | unit (QApplication needed) | `pytest tests/test_control_panel_window.py::test_window_is_qmainwindow -x` | Wave 0 |
| CTRL-02 | atomic_write_config writes valid JSON to target path | unit | `pytest tests/test_config_io.py::test_atomic_write_produces_valid_json -x` | Wave 0 |
| CTRL-02 | atomic_write_config cleans up temp file on error | unit | `pytest tests/test_config_io.py::test_atomic_write_cleans_up_on_error -x` | Wave 0 |
| CTRL-03 | ControlPanelWindow exposes Pomodoro duration fields | unit | `pytest tests/test_control_panel_window.py::test_pomodoro_fields_present -x` | Wave 0 |
| CTRL-03 | ControlPanelWindow exposes calendar clock format field | unit | `pytest tests/test_control_panel_window.py::test_calendar_clock_format_field -x` | Wave 0 |

**Hardware validation (manual, required for SC-1 and SC-2):**
- Success Criterion 1 (double-save triggers two reloads): Run host + `python -m control_panel`, save config twice, observe host log.
- Success Criterion 2 (add/remove widget without host restart): Edit config to add/remove widget entry, observe process spawn/stop.

### Sampling Rate

- **Per task commit:** `pytest tests/ -m "not integration" -x -q`
- **Per wave merge:** `pytest tests/ -q`
- **Phase gate:** Full suite green + manual double-save hardware test before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_config_loader.py` — covers CFG-01, CFG-02, CFG-03 (unit tests with mock watcher and mock ProcessManager)
- [ ] `tests/test_config_io.py` — covers CTRL-02 atomic write
- [ ] `tests/test_control_panel_window.py` — covers CTRL-01, CTRL-03 (requires QApplication fixture from conftest; add to existing conftest.py or new fixture)
- [ ] `control_panel/__init__.py` and `control_panel/__main__.py` — module skeleton needed before tests can import

---

## Sources

### Primary (HIGH confidence)

- Qt docs https://doc.qt.io/qt-6/qfilesystemwatcher.html — `fileChanged` drop-after-rename behavior, `addPath()` re-add pattern explicitly documented
- Qt for Python docs https://doc.qt.io/qtforpython-6/PySide6/QtCore/QFileSystemWatcher.html — Python API signatures confirmed
- Python docs https://docs.python.org/3/library/os.html#os.replace — `os.replace()` atomicity on Windows (MoveFileEx)
- Python docs https://docs.python.org/3/library/tempfile.html — `mkstemp()` with `dir=` for same-filesystem guarantee
- Live introspection of PyQt6 6.10.2 on project machine — `QFileSystemWatcher` methods listed, `QTimer.singleShot` signature verified, all control panel widgets confirmed importable

### Secondary (MEDIUM confidence)

- Qt Forum https://forum.qt.io/topic/41401/solved-qfilesystemwatcher-reports-change-twice — double-fire behavior confirmed; `QTimer.singleShot` debounce solution verified by community consensus
- Python docs https://docs.python.org/3/library/multiprocessing.html — bidirectional two-queue pattern for subprocess IPC

### Tertiary (LOW confidence)

- STATE.md mention of `watchdog 6.x` in stack: superseded by requirements (CFG-02 specifies QFileSystemWatcher); watchdog is NOT used in Phase 2

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are stdlib or already-installed PyQt6; verified via live introspection
- Architecture patterns: HIGH — QFileSystemWatcher re-add pattern is from official Qt docs; atomic write pattern is from Python stdlib docs; bidirectional queue is a standard multiprocessing pattern
- Pitfalls: HIGH — Windows-specific pitfalls (file locking, atomic replace behavior) verified against official docs and confirmed on target platform (Windows 11, PyQt6 6.10.2)

**Research date:** 2026-03-26
**Valid until:** 2026-04-25 (stable APIs; QFileSystemWatcher behavior unchanged since Qt 5)
