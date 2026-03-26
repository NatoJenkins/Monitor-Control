# Stack Research

**Domain:** Python desktop widget/dashboard framework — Windows, dedicated secondary display
**Researched:** 2026-03-26
**Confidence:** HIGH (core stack), MEDIUM (notification interception), LOW (notification suppression)

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.12.x | Runtime | Mature LTS release; pywin32 311 and PyQt6 6.10.x are both validated against it. Python 3.13 is the newest release but 3.12 has broader ecosystem validation for Windows GUI work as of early 2026. |
| PyQt6 | 6.10.2 | Host display window, control panel UI, all rendering | Only Python GUI framework that exposes the full Qt6 rendering pipeline (`QPainter`, `QPixmap`, compositing) without a separate runtime install. `QScreen` API handles multi-monitor geometry correctly. GPL license acceptable for a personal tool; commercial license available if needed. |
| pywin32 | 311 | Windows API access — win32api, win32gui, win32con, COM | Required for Windows message hooks, COM automation, and higher-level Win32 wrappers. Provides `win32api.ClipCursor()` directly without raw ctypes struct wrangling. Also needed if WMI queries or shell integration are added later. |
| watchdog | 6.0.0 | File system event monitoring for config.json hot-reload | Uses `ReadDirectoryChangesW` with I/O completion ports on Windows — this is the correct native backend, not polling. Callback-based; integrates cleanly with a QThread wrapper. |
| winrt-runtime + winrt-Windows.UI.Notifications.Management | 3.2.1 | Read and dismiss Windows toast notifications from other apps | Official Python projection of WinRT APIs, maintained by the pywinrt project. The only supported Python path to `UserNotificationListener`. Provides `GetNotificationsAsync`, `RemoveNotification`, and the `NotificationChanged` event. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| winrt-Windows.Foundation | 3.2.1 | WinRT async plumbing (`IAsyncOperation`) | Required alongside any winrt-Windows.* package; handles async method calls from synchronous Python context |
| winrt-Windows.ApplicationModel | 3.2.1 | `AppInfo` access on `UserNotification` objects | Needed to read the originating app's display name and icon from a captured notification |
| ctypes (stdlib) | built-in | Direct Win32 calls where pywin32 is overkill | `ClipCursor` can be called via `ctypes.windll.user32.ClipCursor` with a `ctypes.wintypes.RECT`; no extra install needed. Use ctypes for one-off Win32 calls, pywin32 for anything requiring COM or complex Win32 message handling. |
| multiprocessing (stdlib) | built-in | `Queue` for host-widget IPC | Mandated by project constraints. `multiprocessing.Queue` is process-safe and pickle-based. Widget processes push state dicts or draw data; the host consumes from a dedicated QThread. |
| json (stdlib) | built-in | config.json read/write | No dependency needed; watchdog triggers the reload, json.load() parses it. |
| dataclasses (stdlib) | built-in | Typed config and message schemas | Use `@dataclass` for queue message payloads to enforce shape at the widget boundary without adding a schema library. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| venv | Isolated Python environment | `python -m venv .venv` at repo root; activate before all pip operations |
| pip | Package installation | Use `pip install -r requirements.txt`; pin versions with `pip freeze` after initial install |
| Qt Designer (via pyqt6-tools) | Visual layout for control panel | `pip install pyqt6-tools` installs `designer.exe`; optional but useful for control panel layout work |
| pyqt6-tools | Qt Designer + pyrcc6 for the control panel | Version should match installed PyQt6 minor version |

---

## Installation

```bash
# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# Core framework
pip install PyQt6==6.10.2
pip install pywin32==311
pip install watchdog==6.0.0

# WinRT notification packages (install all required namespaces)
pip install winrt-runtime==3.2.1
pip install "winrt-Windows.UI.Notifications.Management==3.2.1"
pip install "winrt-Windows.Foundation==3.2.1"
pip install "winrt-Windows.ApplicationModel==3.2.1"

# Optional dev tooling
pip install pyqt6-tools
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| PyQt6 6.10.2 | PySide6 6.10.2 | PySide6 is the Qt Company's official binding and uses LGPL, which is more permissive. Choose PySide6 if the project ever needs to be commercially distributed without purchasing a PyQt6 commercial license. API is ~95% identical; migration cost is low. |
| PyQt6 | tkinter | Never for this project — tkinter has no compositing pipeline, no proper multi-monitor screen enumeration via QScreen, and no native Windows-style styling. |
| PyQt6 | Dear PyGui / ImGui | Consider only if the host ever needs GPU-accelerated rendering at high refresh rates. Not appropriate here: no windowing model for borderless always-on-top window management, and multi-monitor geometry is manual. |
| pywin32 (win32api.ClipCursor) | ctypes.windll.user32.ClipCursor | Use raw ctypes if you want zero dependencies for the cursor lock. The ctypes approach requires manually defining `RECT` as a ctypes Structure; pywin32 wraps this cleanly. For a project already depending on pywin32 for other Win32 work, use pywin32. |
| watchdog | QFileSystemWatcher (Qt built-in) | `QFileSystemWatcher` is usable and avoids the extra dependency. However, watchdog gives a richer event API (modified/created/deleted/moved) and better Windows backend. Use `QFileSystemWatcher` only if you want to eliminate the watchdog dependency entirely. |
| winrt-Windows.UI.Notifications.Management | winsdk | Do not use `winsdk`. It was archived October 2024. The replacement is the modular per-namespace `winrt-*` packages from the pywinrt project. |
| Python 3.12 | Python 3.13 | Python 3.13 is production-ready and supported by PyQt6 6.10.x and pywin32 311. Choose 3.13 if the team wants the latest GIL-optional features or performance improvements. 3.12 is recommended for slightly broader tool ecosystem compatibility. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `winsdk` (monolithic) | Archived October 2024; no longer maintained. Import paths differ from the replacement. | Modular `winrt-*` packages from pywinrt (winrt-runtime, winrt-Windows.UI.Notifications.Management, etc.) |
| `plyer` for notifications | Sends notifications; cannot read or remove existing ones. API surface is too thin for this use case. | `winrt-Windows.UI.Notifications.Management` |
| `win10toast` / `win11toast` | These are notification senders, not listeners. Actively misleading for this use case. | `winrt-Windows.UI.Notifications.Management` for listening; `winrt-Windows.UI.Notifications` for sending |
| `QTimer` for queue polling in the host | Polling the multiprocessing.Queue from the main event loop timer can cause UI stutter under load. | Dedicated `QThread` subclass that blocks on `queue.get()` and emits a Qt signal; the host slot updates the canvas safely. |
| `threading.Thread` for queue drain | Non-Qt threads cannot touch Qt objects. A raw thread draining a queue and calling widget methods directly will segfault or produce undefined behavior. | `QThread` with signal emission only; all Qt operations happen in slots on the main thread. |
| Shared memory (`multiprocessing.shared_memory`) | Not supported by the IPC constraint and introduces complex synchronization. Raw pixel buffers in shared memory are fast but the constraint explicitly mandates queues. | `multiprocessing.Queue` with serialized payload dicts or numpy arrays if raw frame data is ever needed. |
| `pywin32-ctypes` | This is a reimplementation of only a small pywin32 subset using ctypes/cffi; it lacks win32gui, win32api, and COM support needed here. | Full `pywin32` package. |

---

## Stack Patterns by Variant

**Notification widget: reading and surfacing notifications**

The `UserNotificationListener` API reads notifications that have already been shown in the Windows notification center. It cannot intercept or suppress a notification before it appears on screen. This is a hard Windows API constraint — the listener fires after the OS has already displayed the toast.

Design implication: the notification widget surfaces notifications in the utility bar by polling/event-driven reading from `UserNotificationListener`, and calls `RemoveNotification(id)` to dismiss them from the Action Center. It does not suppress the initial on-screen toast popup.

If pre-display suppression is required, the only known approach is programmatically enabling "Focus Assist / Do Not Disturb" via undocumented registry keys or the Windows Settings app, which is fragile and not recommended. This capability should be flagged as a likely phase-specific research item.

**If you want to dismiss toasts from Action Center after they appear:**
- Use `winrt.windows.ui.notifications.management.UserNotificationListener`
- Call `RequestAccessAsync()` once from the UI thread; user must grant permission in Windows Settings → Notifications → Notification access
- Subscribe to `NotificationChanged` event or poll `GetNotificationsAsync(NotificationKinds.Toast)` on a timer
- Call `RemoveNotification(notif.Id)` to dismiss

**If you want pre-display suppression (not currently feasible cleanly):**
- The Windows API does not expose a supported hook to intercept another app's toast before display
- The only partial workaround is enabling Focus Assist / Do Not Disturb mode system-wide via the registry (undocumented path, Windows version sensitive)
- Flag this for phase research; the MVP notification widget should be scoped to post-display surfacing and dismissal only

**Host window targeting Display 3:**

```python
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

screens = QApplication.screens()
# Find target screen by geometry (1920x515 strip positioned below primaries)
target = next(
    (s for s in screens if s.geometry().height() == 515),
    screens[-1]  # fallback to last screen
)
window.move(target.geometry().topLeft())
window.resize(1920, 515)
window.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
window.showFullScreen()
```

Use `QApplication.screens()` not the deprecated `QDesktopWidget`. Enumerate by geometry to identify Display 3 reliably.

**ClipCursor with ctypes (preferred over pywin32 for this single call):**

```python
import ctypes
from ctypes import wintypes

# Define the exclusion rect (everything except Display 3)
# Display 3 geometry must be known at startup; invert it to define the allowed zone
user32 = ctypes.windll.user32

class RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]

def lock_cursor_away_from_display3(allowed_rect: RECT):
    user32.ClipCursor(ctypes.byref(allowed_rect))

def unlock_cursor():
    user32.ClipCursor(None)
```

Note: ClipCursor only supports a single rectangle. If Display 3 is not at the edge of the virtual desktop but is positioned below the primaries (as described), the allowed rect can be set to the bounding box of Display 1 + Display 2 only. This works correctly as long as the three monitors don't share overlapping X or Y ranges that would accidentally block part of a primary.

**QThread queue monitor pattern:**

```python
from PyQt6.QtCore import QThread, pyqtSignal
import queue

class QueueMonitorThread(QThread):
    message_received = pyqtSignal(dict)

    def __init__(self, q: multiprocessing.Queue):
        super().__init__()
        self._queue = q
        self._running = True

    def run(self):
        while self._running:
            try:
                msg = self._queue.get(timeout=0.1)
                self.message_received.emit(msg)
            except queue.Empty:
                continue

    def stop(self):
        self._running = False
        self.wait()
```

Connect `message_received` to a slot on the host widget canvas to update the display safely from the main thread.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| PyQt6 6.10.2 | Python 3.9–3.14 | Confirmed via PyPI metadata; 3.12 recommended for stability |
| pywin32 311 | Python 3.8–3.14, Windows x64/x86/ARM64 | July 2025 release; binary-only via pip (no exe installer since build 306) |
| watchdog 6.0.0 | Python 3.9+ | Released Nov 2024; uses ReadDirectoryChangesW on Windows (no polling) |
| winrt-Windows.UI.Notifications.Management 3.2.1 | Python 3.9–3.14, Windows x86/x64/ARM64 | June 2025 release; requires winrt-runtime of same version |
| winrt-runtime 3.2.1 | Python 3.9–3.14 | Must match version of all other winrt-* packages installed |
| PyQt6 6.10.2 + pywin32 311 | No known conflicts | These operate independently; no shared DLL surface |
| watchdog 6.0.0 + PyQt6 | No known conflicts | watchdog Observer runs on its own thread; use QueueMonitorThread or a signal bridge to push events to Qt |

---

## Sources

- [PyPI — PyQt6](https://pypi.org/project/PyQt6/) — version 6.10.2 confirmed (Jan 8, 2026 release date) — HIGH confidence
- [PyPI — pywin32](https://pypi.org/project/pywin32/) — version 311 confirmed (Jul 14, 2025) — HIGH confidence
- [PyPI — watchdog](https://pypi.org/project/watchdog/) — version 6.0.0, ReadDirectoryChangesW backend confirmed — HIGH confidence
- [PyPI — winrt-Windows.UI.Notifications.Management](https://pypi.org/project/winrt-Windows.UI.Notifications.Management/) — version 3.2.1 (Jun 6, 2025) — HIGH confidence
- [GitHub — pywinrt/python-winsdk (archived)](https://github.com/pywinrt/python-winsdk) — confirms winsdk deprecated Oct 2024, replaced by modular winrt-* — HIGH confidence
- [Microsoft Learn — Notification Listener](https://learn.microsoft.com/en-us/windows/apps/design/shell/tiles-and-notifications/notification-listener) — confirms UserNotificationListener reads/removes after display; cannot suppress before display — HIGH confidence
- [Microsoft Learn — ClipCursor](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clipcursor) — rectangle-only constraint confirmed — HIGH confidence
- [pythonguis.com — PyQt6 Multithreading with QThreadPool](https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/) — QThread queue monitor pattern — MEDIUM confidence (community source, consistent with Qt docs)
- WebSearch results for multi-monitor QScreen enumeration — MEDIUM confidence (community forums, consistent with Qt6 docs pattern)
- Notification suppression via Focus Assist registry — LOW confidence (no official documented API; avoid)

---

*Stack research for: MonitorControl — Python/PyQt6 desktop widget framework, Windows, 1920x515 secondary display*
*Researched: 2026-03-26*
