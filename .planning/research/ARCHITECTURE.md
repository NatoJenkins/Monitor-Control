# Architecture Research

**Domain:** Python desktop widget bar — host-renders / widget-pushes-data on Windows
**Researched:** 2026-03-26
**Confidence:** HIGH (core architecture), MEDIUM (notification interception), LOW (notification suppression)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│  CONTROL PANEL PROCESS  (PyQt6 window, user-visible, any monitor)       │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  ControlPanel (QMainWindow)  ─── reads/writes ──► config.json   │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────┬──────────────────────────────────────────────┘
                           │  writes config.json
                           ▼
                     [ config.json ]  ◄── watched by host
                           │
┌──────────────────────────▼──────────────────────────────────────────────┐
│  HOST PROCESS  (main Python process / PyQt6 event loop)                 │
│                                                                         │
│  ┌──────────────┐   ┌────────────────┐   ┌─────────────────────────┐   │
│  │ ConfigLoader │   │  ProcessManager│   │   HostWindow            │   │
│  │ /Watcher     │──►│  (spawn/stop   │   │   (QWidget, borderless, │   │
│  │(QFileSystem  │   │   widget procs)│   │    always-on-top,       │   │
│  │  Watcher)    │   └───────┬────────┘   │    Display 3, 1920x515) │   │
│  └──────────────┘           │            │                         │   │
│         │                   │            │   ┌─────────────────┐   │   │
│         │ layout/config     │ owns       │   │  Compositor     │   │   │
│         └───────────────────┤            │   │  (paintEvent /  │   │   │
│                             │            │   │   QPainter)     │   │   │
│                   multiprocessing.Queue  │   └────────┬────────┘   │   │
│                   (one per widget)       │            │            │   │
│                             │            └────────────┼────────────┘   │
│                   ┌─────────▼──────────┐              │                │
│                   │  QueueDrainTimer   │◄─────────────┘                │
│                   │  (QTimer 50ms)     │  triggers repaint             │
│                   └────────────────────┘                               │
│                                                                         │
│  Win32 layer:  ClipCursor()  ·  SetWindowPos()  ·  EnumDisplayMonitors │
└─────────────────────────────────────────────────────────────────────────┘
          ▲                ▲                 ▲               ▲
          │ Queue.put()    │ Queue.put()     │ Queue.put()   │ Queue.put()
┌─────────┴──┐  ┌──────────┴─┐  ┌───────────┴──┐  ┌────────┴──────────┐
│  DUMMY     │  │  POMODORO  │  │  CALENDAR    │  │  NOTIFICATION     │
│  WIDGET    │  │  WIDGET    │  │  WIDGET      │  │  INTERCEPTOR      │
│  PROCESS   │  │  PROCESS   │  │  PROCESS     │  │  WIDGET PROCESS   │
│            │  │            │  │              │  │                   │
│ WidgetBase │  │ WidgetBase │  │ WidgetBase   │  │ WidgetBase        │
│ (contract) │  │            │  │              │  │ + UserNotification│
│            │  │ timer loop │  │ datetime loop│  │   Listener (WinRT)│
└────────────┘  └────────────┘  └──────────────┘  └───────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Lives In |
|-----------|---------------|----------|
| **HostWindow** | Owns the physical Display 3 QWidget; applies WindowStaysOnTopHint + FramelessWindowHint; enforces 1920x515 geometry at target screen origin | Host process |
| **Compositor** | Receives FrameData messages from QueueDrainTimer; calls QPainter to blit each widget's rendered region into its assigned slot; triggers update() | Host process |
| **QueueDrainTimer** | A QTimer firing every 50 ms; drains all widget queues non-blocking (queue.get_nowait in a loop); converts raw dicts to FrameData and hands to Compositor | Host process |
| **ProcessManager** | Spawns, monitors, and terminates widget multiprocessing.Process instances; maps widget_id → (Process, Queue pair); restarts crashed workers | Host process |
| **ConfigLoader / Watcher** | Parses config.json on startup; installs QFileSystemWatcher on the file path; emits a config_changed signal on write; feeds ProcessManager with layout and per-widget settings | Host process |
| **ClipCursor enforcer** | Calls win32api.ClipCursor() with the Display 3 RECT on startup; re-applies on WM_DISPLAYCHANGE | Host process (Win32 layer) |
| **WidgetBase** | Abstract base class / protocol that every widget process must implement; defines the run() entry point and the outbound queue contract | Shared module |
| **Dummy Widget** | Minimal WidgetBase implementation; pushes a static colored rectangle; used to validate the full host pipeline | Widget process |
| **Pomodoro Widget** | Owns Pomodoro state machine (WORK / SHORT_BREAK / LONG_BREAK); pushes countdown frame data every second | Widget process |
| **Calendar Widget** | Polls datetime.now() every second; formats and pushes styled date/time FrameData | Widget process |
| **Notification Interceptor** | Calls UserNotificationListener.get_current() via winrt-Windows.UI.Notifications.Management; polls or subscribes to notification_changed events; pushes notification summaries as FrameData; does NOT suppress OS notifications (read-only in Python — see Pitfalls) | Widget process |
| **ControlPanel** | Separate PyQt6 QMainWindow on a primary monitor; reads config.json; presents layout editor and per-widget config forms; writes config.json on save; does not connect directly to host process | Control panel process |

## Recommended Project Structure

```
MonitorControl/
├── host/
│   ├── main.py                 # Entry point — QApplication, HostWindow, ProcessManager
│   ├── window.py               # HostWindow (borderless, always-on-top, Display 3)
│   ├── compositor.py           # Compositor — QPainter slot layout renderer
│   ├── queue_drain.py          # QueueDrainTimer — polls all widget queues
│   ├── process_manager.py      # ProcessManager — spawn/stop/restart widgets
│   ├── config_loader.py        # ConfigLoader + QFileSystemWatcher integration
│   └── win32_utils.py          # ClipCursor, EnumDisplayMonitors, SetWindowPos wrappers
│
├── widgets/
│   ├── base.py                 # WidgetBase abstract class + IPC message schema
│   ├── dummy/
│   │   └── widget.py           # Dummy widget (pipeline validation)
│   ├── pomodoro/
│   │   └── widget.py           # Pomodoro timer widget
│   ├── calendar/
│   │   └── widget.py           # Calendar / datetime widget
│   └── notifications/
│       └── widget.py           # Windows notification interceptor widget
│
├── control_panel/
│   ├── main.py                 # Entry point for control panel process
│   ├── panel.py                # ControlPanel QMainWindow
│   └── config_editor.py        # Per-widget config forms
│
├── shared/
│   └── message_schema.py       # FrameData and IPC message dataclasses (shared import)
│
├── config.json                 # Runtime config (layout + per-widget settings)
└── launch.py                   # Optional: spawns both host and control panel
```

### Structure Rationale

- **host/:** The single Python process that owns the Qt event loop and the display. Isolated so the host can be started without control panel.
- **widgets/:** Each widget is a subdirectory so it can grow to include assets, sub-modules, and tests without polluting the namespace.
- **widgets/base.py:** The contract between host and widget lives here. Changing the schema means touching one file; all widgets inherit the change.
- **control_panel/:** Separate top-level package so it can be launched independently. Nothing in control_panel/ imports from host/.
- **shared/:** Holds only the IPC message schema (pure dataclasses, no Qt, no win32). Both host and widget processes can import it without pulling in heavy dependencies.

## Architectural Patterns

### Pattern 1: Queue-Drain-on-Timer (host side)

**What:** A QTimer fires every N ms in the Qt main thread. The handler drains all widget queues using non-blocking `queue.get_nowait()` inside a try/except. Any new FrameData updates the compositor's state dict; a single `update()` call is issued after the drain loop finishes so Qt coalesces repaints.

**When to use:** Always — this is the only way to move data from multiprocessing queues into the Qt event loop without blocking the event loop or spawning additional threads.

**Trade-offs:** 50 ms polling introduces up to 50 ms display latency (acceptable for a utility bar). Shorter intervals (16 ms) are safe but increase CPU overhead; longer intervals (200 ms) are fine for low-frequency widgets (calendar). A tiered polling interval per widget type can be added later.

**Example:**
```python
# host/queue_drain.py
from PyQt6.QtCore import QTimer
import queue

class QueueDrainTimer:
    def __init__(self, process_manager, compositor, interval_ms=50):
        self._pm = process_manager
        self._compositor = compositor
        self._timer = QTimer()
        self._timer.setInterval(interval_ms)
        self._timer.timeout.connect(self._drain)
        self._timer.start()

    def _drain(self):
        updated = False
        for widget_id, q in self._pm.queues.items():
            try:
                while True:
                    msg = q.get_nowait()
                    self._compositor.update_frame(widget_id, msg)
                    updated = True
            except queue.Empty:
                pass
        if updated:
            self._compositor.schedule_repaint()
```

### Pattern 2: Slot-Based Compositor (host side)

**What:** The host window is divided into named rectangular slots whose geometry is read from config.json. The Compositor holds a dict of `{widget_id: FrameData}`. On each `paintEvent`, it iterates slots in config order, asking each widget's FrameData to paint itself into the assigned QRect via QPainter. Slots that have no live widget paint a placeholder.

**When to use:** Essential — this is what allows "widgets can be added or swapped without modifying host code". The host only knows about slots and FrameData; it does not import widget code.

**Trade-offs:** Widget output must be serializable through a multiprocessing.Queue (no Qt objects, no QPainter state). Widgets express their UI as primitive draw commands or pre-rendered pixel buffers (bytes). Pre-rendered bytes (QImage-compatible raw RGBA) is simpler and avoids reinventing a draw command protocol.

**Example:**
```python
# shared/message_schema.py
from dataclasses import dataclass, field

@dataclass
class FrameData:
    widget_id: str
    width: int
    height: int
    rgba_bytes: bytes        # raw RGBA32, width*height*4 bytes
    timestamp: float = 0.0

# host/compositor.py — paintEvent excerpt
def paintEvent(self, event):
    painter = QPainter(self)
    for slot in self._config.slots:
        frame = self._frames.get(slot.widget_id)
        if frame:
            img = QImage(frame.rgba_bytes, frame.width, frame.height,
                         QImage.Format.Format_RGBA8888)
            painter.drawImage(slot.rect, img)
        else:
            painter.fillRect(slot.rect, QColor("#1a1a1a"))
    painter.end()
```

### Pattern 3: WidgetBase Contract (widget side)

**What:** An abstract base class that every widget process must subclass. It defines: `run(out_queue)` as the entry point called by ProcessManager; `on_config_update(cfg)` for hot-reload when config changes; and the obligation to push only picklable objects (FrameData or plain dicts) onto `out_queue`. The widget process never imports Qt.

**When to use:** Always — enforcing this boundary means widget crashes cannot corrupt the host process and widgets can be developed and tested independently.

**Trade-offs:** Widgets must render their own frames (e.g., using PIL/Pillow or Cairo for off-screen drawing) before pushing bytes. This adds a dependency, but Pillow is small and available everywhere. Alternatively, widgets can push structured data dicts and let the host render them — simpler for text-only widgets, complex for custom graphics.

**Recommendation:** Use the pre-rendered bytes approach for Pomodoro and Calendar (they have custom graphics); use structured data dicts for the Dummy widget (simpler to validate).

```python
# widgets/base.py
from abc import ABC, abstractmethod
import multiprocessing

class WidgetBase(ABC):
    def __init__(self, widget_id: str, config: dict,
                 out_queue: multiprocessing.Queue):
        self.widget_id = widget_id
        self.config = config
        self.out_queue = out_queue

    @abstractmethod
    def run(self) -> None:
        """Main loop. Runs in a subprocess. Push FrameData to self.out_queue."""

    def on_config_update(self, new_config: dict) -> None:
        """Called when config.json changes. Default: replace config dict."""
        self.config = new_config
```

## Data Flow

### Widget Update Flow (steady state)

```
Widget process internal loop
    │
    ├── compute new state (timer tick, datetime, notification poll)
    │
    ├── render to off-screen buffer (Pillow ImageDraw or plain bytes)
    │
    └── queue.put(FrameData(widget_id, w, h, rgba_bytes))
                        │
                        │  (pickle + pipe, ~50 ms latency)
                        ▼
              QueueDrainTimer (QTimer, Qt main thread)
                        │
                        ├── queue.get_nowait() loop
                        │
                        └── compositor.update_frame(widget_id, frame_data)
                                        │
                                        └── self._frames[widget_id] = frame_data
                                            self.update()  ── triggers paintEvent
                                                    │
                                                    ▼
                                            QPainter.drawImage(slot.rect, img)
                                                    │
                                                    ▼
                                            Display 3 (1920x515 physical pixels)
```

### Config Change Flow

```
User edits layout/config in ControlPanel
    │
    └── writes config.json
                │
                ▼
    QFileSystemWatcher.fileChanged signal (host process)
                │
                ▼
    ConfigLoader.reload()
                │
                ├── diff old vs new layout
                │
                ├── ProcessManager.stop_widget(removed_ids)
                │
                ├── ProcessManager.start_widget(added_ids)
                │
                └── Compositor.update_slots(new_layout)
```

### Process Lifecycle Flow

```
Host startup
    │
    ├── ConfigLoader.load(config.json)
    │
    ├── HostWindow.show() → Display 3
    │
    ├── win32_utils.apply_clip_cursor(display3_rect)
    │
    ├── ProcessManager.start_all(config.widgets)
    │       │
    │       └── for each widget:
    │               out_queue = multiprocessing.Queue()
    │               proc = multiprocessing.Process(target=widget.run)
    │               proc.start()
    │
    └── QueueDrainTimer.start(interval=50ms)
```

### Key Data Flows

1. **Steady-state rendering:** Widget process → Queue → QueueDrainTimer → Compositor → QPainter → screen. One-way push; host never sends draw requests to widgets.
2. **Config hot-reload:** ControlPanel writes config.json → QFileSystemWatcher fires → ConfigLoader reloads → ProcessManager diffs → dead/new processes managed → Compositor slot map updated.
3. **Notification capture:** WinRT UserNotificationListener polls Action Center in the notification widget's subprocess → pushes notification text as FrameData → rendered in notification slot. No suppression of OS toasts (see Pitfalls).
4. **Cursor lockout:** win32api.ClipCursor() called once on host startup with Display 3 RECT. Re-applied on WM_DISPLAYCHANGE in case monitor layout changes.

## Scaling Considerations

This is a single-machine desktop application. "Scale" means number of simultaneous widget processes and frame update frequency.

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 1–4 widgets (target) | Current architecture — one process per widget, single queue, 50 ms drain timer. No changes needed. |
| 5–12 widgets | Increase drain timer to 16 ms (60 fps equivalent) if visual latency is noticeable. Consider per-widget QTimer intervals matched to each widget's natural update rate. |
| 12+ widgets | Pool drain into a single aggregator thread that forwards to the Qt main thread via a thread-safe flag rather than polling all N queues each tick. Unlikely to be needed. |

### Scaling Priorities

1. **First bottleneck:** Queue drain loop iterating many idle queues. Fix: add a dirty-flag set per widget so the drain loop skips queues with no new data.
2. **Second bottleneck:** Compositor repainting entire 1920x515 surface on every frame update. Fix: dirty-rect tracking — only repaint the slot(s) that received new FrameData. Qt's update(QRect) supports this natively.

## Anti-Patterns

### Anti-Pattern 1: Passing Qt Objects Through Queues

**What people do:** Put QPixmap, QImage, QPainter, or Qt signals into multiprocessing.Queue.

**Why it's wrong:** Qt objects are not picklable. multiprocessing.Queue serializes via pickle. Passing Qt objects will raise PicklingError at runtime. Qt objects also belong to a specific thread/event-loop and must not cross process boundaries.

**Do this instead:** Widgets render to raw bytes (RGBA pixel buffer via Pillow or struct.pack) before calling queue.put(). The host reconstructs a QImage from the bytes. Only plain Python data structures (dataclasses, dicts, ints, bytes) travel through the queue.

### Anti-Pattern 2: Blocking the Qt Event Loop on Queue Reads

**What people do:** Call queue.get() (blocking) inside a paintEvent, a QThread, or a slot connected to a signal.

**Why it's wrong:** Any blocking call in the Qt main thread freezes the UI. The event loop cannot process input events, paint requests, or timer signals until the block returns.

**Do this instead:** Always use queue.get_nowait() inside the QTimer drain handler. Catch queue.Empty and return immediately. The QTimer fires again in 50 ms regardless.

### Anti-Pattern 3: Widget Processes Importing PyQt6

**What people do:** Import PyQt6 in widget subprocess code to use QImage for off-screen rendering or QFont for text metrics.

**Why it's wrong:** PyQt6 requires a running QApplication. Spawning a QApplication in a subprocess on Windows with the spawn start method causes crashes or silent failures because Qt initializes display connections that conflict with the host's Qt context.

**Do this instead:** Widget processes use only non-Qt rendering (Pillow, Cairo, or pure numpy). Qt lives exclusively in the host process and the control panel process.

### Anti-Pattern 4: Hardcoding Monitor Index Instead of Matching by Geometry

**What people do:** Use `QApplication.screens()[2]` (index 2) as "Display 3".

**Why it's wrong:** Monitor enumeration order is not guaranteed stable across reboots, driver updates, or sleep/wake cycles. Index 2 today may be a different physical monitor tomorrow.

**Do this instead:** Match the target monitor by geometry (size + position) from config.json: iterate `QApplication.screens()`, find the one whose `geometry()` matches `1920x515` at the configured (x, y) origin. Fall back gracefully if not found.

### Anti-Pattern 5: Control Panel Process Writing Config While Host Holds a File Lock

**What people do:** Have both control panel and host open config.json simultaneously with write handles.

**Why it's wrong:** File locking contention on Windows causes IOError or silently corrupt JSON writes.

**Do this instead:** Control panel is the sole writer; host is the sole reader. Control panel writes atomically (write to config.tmp, then os.replace to config.json). QFileSystemWatcher triggers only after the rename completes, so the host always reads a complete file.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Windows Action Center (notifications) | WinRT via `winrt-Windows.UI.Notifications.Management`; `UserNotificationListener.get_current()` in widget subprocess | Requires user consent (notification access permission). Read-only — cannot suppress individual OS toasts from Python. Confidence: MEDIUM |
| Win32 API (cursor, window placement) | ctypes + `win32api`/`win32con` (pywin32) via `win32_utils.py` | ClipCursor, SetWindowPos, EnumDisplayMonitors. Confidence: HIGH |
| Windows Focus Assist / Do Not Disturb | No programmatic Python API for suppression; read-only via registry polling or WNS APIs | If suppression is a hard requirement, see PITFALLS.md — may require a Windows service or privileged hook |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Host ↔ Widget process | `multiprocessing.Queue` one-way push (widget → host). Plain dicts / dataclasses only. | No reverse channel in v1. Config updates reach widgets via process restart or a second queue per widget. |
| Host ↔ ControlPanel | `config.json` file on disk (asynchronous, file-mediated). No direct socket or queue. | Decoupled by design; control panel can be closed/reopened without affecting host. |
| ConfigLoader → ProcessManager | In-process Python function calls / Qt signals. `config_changed` signal carries new config dict. | Same process; no serialization needed. |
| QueueDrainTimer → Compositor | In-process function call (`update_frame`). | Same thread (Qt main thread); no locking needed. |
| WidgetBase → WidgetImpl | Python inheritance. | Base class in `shared/`; implementation in `widgets/<name>/`. No cross-process dependency. |

## Sources

- PyQt6 / PySide6 multiprocessing queue integration: [Qt Forum — How to make Qt signals work with Python's multiprocessing](https://forum.qt.io/topic/114428/how-to-make-qt-signals-work-using-python-s-multiprocessing-interface)
- QTimer drain pattern: [Overcoming GUI Freezes in PyQt — Medium](https://foongminwong.medium.com/overcoming-gui-freezes-in-pyqt-from-threading-multiprocessing-to-zeromq-qprocess-9cac8101077e)
- QFileSystemWatcher: [Qt for Python official docs](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QFileSystemWatcher.html)
- QScreen multi-monitor: [QScreen Class — Qt 6 docs](https://doc.qt.io/qt-6/qscreen.html)
- Windows notification listener (WinRT): [winrt-Windows.UI.Notifications.Management — PyPI](https://pypi.org/project/winrt-Windows.UI.Notifications.Management/)
- Windows notification architecture: [Microsoft Learn — Notification listener](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener)
- ClipCursor / multi-monitor positioning: [Microsoft Learn — Positioning Objects on Multiple Display Monitors](https://learn.microsoft.com/en-us/windows/win32/gdi/positioning-objects-on-multiple-display-monitors)
- Python multiprocessing IPC: [Python docs — multiprocessing](https://docs.python.org/3/library/multiprocessing.html)

---
*Architecture research for: Python desktop widget bar (MonitorControl)*
*Researched: 2026-03-26*
