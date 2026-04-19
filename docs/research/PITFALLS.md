# Pitfalls Research

**Domain:** Python/PyQt6 desktop widget bar — Windows, borderless always-on-top window, multiprocessing IPC, Win32 APIs
**Researched:** 2026-03-26 (v1.0) | 2026-03-27 (v1.1 supplement: PyInstaller + autostart) | 2026-03-27 (v1.2 supplement: configurable colors)
**Confidence:** HIGH (multiprocessing, Qt window flags, QFileSystemWatcher) | MEDIUM (ClipCursor reset scenarios, WinRT async threading) | LOW (notification suppression)

---

## Critical Pitfalls

### Pitfall 1: Window Flags Must Be Set Before `show()` — Runtime Changes Cause Flicker or No Effect

**Severity:** BLOCKER

**What goes wrong:**
Calling `setWindowFlags()` on a window that is already visible causes Qt to hide the window and requires a subsequent `show()` call to make it reappear. If `WindowStaysOnTopHint` or `FramelessWindowHint` is set after `show()` without the hide/show cycle, the flags may appear to apply but the window silently loses always-on-top state in practice (especially after focus changes). The wrong order — `FramelessWindowHint` first, then `WindowStaysOnTopHint` — is a documented issue that produces a borderless window that does not stay on top.

**Why it happens:**
Qt's window system abstraction internally destroys and recreates the native HWND when window flags change after the window is realized. Without the `hide()` + `show()` cycle, the native window handle is in an inconsistent state. On Windows, the required combined flags `WS_POPUP | WS_EX_TOPMOST` are set atomically during the native window creation triggered by `show()`, not by flag accumulation calls.

**How to avoid:**
Set ALL window flags in a single `setWindowFlags()` call before the first `show()`:
```python
window.setWindowFlags(
    Qt.WindowType.FramelessWindowHint |
    Qt.WindowType.WindowStaysOnTopHint |
    Qt.WindowType.Tool  # prevents taskbar entry
)
window.show()
```
Never call `setWindowFlags()` on a visible window. If flags must change at runtime, always wrap with `window.hide()` before and `window.show()` after.

**Warning signs:**
- Window appears in the Windows taskbar despite `Tool` flag
- Another fullscreen application appears on top of the host window
- Window visible but positioned on wrong monitor after first show

**Phase to address:** Phase 1 — Host window implementation. This must be validated on target hardware before any widget development begins.

---

### Pitfall 2: Windows `spawn` Start Method Requires `if __name__ == "__main__"` Guard — Missing Guard Causes Recursive Process Spawning

**Severity:** BLOCKER

**What goes wrong:**
On Windows, Python's `multiprocessing` module defaults to the `spawn` start method. Every new child process starts a fresh Python interpreter that imports the parent's `__main__` module. Without an `if __name__ == "__main__":` guard in `host/main.py`, the import triggers ProcessManager.start_all() again in the child, which spawns more children, cascading until the system runs out of handles or memory.

**Why it happens:**
Unlike Linux `fork`, `spawn` cannot inherit the parent's memory state — it must re-execute the module to reconstruct the environment needed to unpickle the target function. Python uses the `__name__ == "__main__"` idiom as the documented fence to prevent top-level startup code from re-running in children.

**How to avoid:**
Every entry point that creates `multiprocessing.Process` objects must be guarded:
```python
# host/main.py
if __name__ == "__main__":
    app = QApplication(sys.argv)
    manager = ProcessManager(config)
    manager.start_all()
    sys.exit(app.exec())
```
The `WidgetBase.run()` entry point is called by the child process; it does NOT need the guard because it is invoked via `multiprocessing.Process(target=widget.run)`, not as a `__main__` re-entry. Only the top-level host entry and any top-level launch script need the guard.

**Warning signs:**
- CPU usage spikes immediately on host startup
- Multiple Python processes visible in Task Manager that were not expected
- `RuntimeError: An attempt has been made to start a new process before the current process has finished its bootstrapping phase`

**Phase to address:** Phase 1 — ProcessManager scaffolding. The `if __name__ == "__main__":` guard is the first thing to validate in the dummy widget integration test.

---

### Pitfall 3: `multiprocessing.Queue.put()` + `process.join()` Deadlock When Queue Buffer Is Full

**Severity:** BLOCKER

**What goes wrong:**
`multiprocessing.Queue` uses an OS pipe as its underlying transport. If a widget process puts items faster than the host drains them, the pipe buffer (~64 KB on Windows) fills up. The widget's `queue.put()` call blocks waiting for pipe space. If the host then calls `process.join()` (e.g., during shutdown or restart triggered by config reload), `join()` blocks waiting for the widget process to exit. The widget cannot exit because it is stuck in `put()`. Result: permanent deadlock — neither side makes progress.

**Why it happens:**
`multiprocessing.Queue.put()` is not always non-blocking. Without `block=False` or a timeout, it blocks indefinitely on a full pipe. The hidden feeder thread in `multiprocessing.Queue` flushes pickled items to the pipe in the background; if that thread is blocked, the process cannot exit even when its `run()` returns.

**How to avoid:**
Three complementary mitigations are all required:
1. Use `queue.put(msg, block=False)` in widget processes and drop frames on `queue.Full` (the host's 50 ms drain is faster than 1 Hz calendar updates, so drops are rare in normal operation).
2. During shutdown, drain the queue fully before calling `process.join()`:
   ```python
   def stop_widget(self, widget_id):
       proc, q = self._widgets[widget_id]
       proc.terminate()
       # Drain any pending items so the feeder thread can exit
       while True:
           try:
               q.get_nowait()
           except queue.Empty:
               break
       proc.join(timeout=5)
       if proc.is_alive():
           proc.kill()
   ```
3. Call `q.cancel_join_thread()` on the child side before exiting to allow the child to exit without waiting for the feeder thread (acceptable when the parent handles the drain). Note: `cancel_join_thread()` may lose buffered items — use it only in shutdown paths, not in steady-state.

**Warning signs:**
- Host hangs during config reload when a widget is stopped
- `process.join()` never returns at shutdown
- Partial config reloads where some widgets start but others don't

**Phase to address:** Phase 1 — ProcessManager. The drain-before-join pattern must be in place before any config hot-reload is tested.

---

### Pitfall 4: `QFileSystemWatcher` Stops Watching After Atomic File Replace

**Severity:** HIGH

**What goes wrong:**
`QFileSystemWatcher` watches a specific inode (file descriptor handle). When config.json is saved atomically (write to `config.tmp`, then `os.replace("config.tmp", "config.json")`), the original inode is deleted and the watcher's file handle becomes stale. Qt emits `fileChanged()` once — because the file was removed — and then stops watching. All subsequent config saves go undetected, silently breaking hot-reload.

**Why it happens:**
The Qt docs explicitly state: "QFileSystemWatcher stops monitoring files once they have been renamed or removed from disk." The control panel uses atomic replace (as it should, per ARCHITECTURE.md) to avoid partial writes. These two facts are in direct conflict unless a re-add step is included.

**How to avoid:**
In the `fileChanged` slot, always check whether the path is still being watched and re-add it if not:
```python
def _on_file_changed(self, path: str):
    # Re-add if atomic replace removed the watched inode
    if path not in self._watcher.files():
        if os.path.exists(path):
            self._watcher.addPath(path)
    self._reload_config(path)
```
Also debounce the reload by at least 100 ms: editors and Python's `os.replace` may emit two change events in rapid succession (file deleted + new file appeared). A `QTimer.singleShot(100, self._reload_config)` prevents double-reloads.

**Warning signs:**
- First config save after startup triggers hot-reload correctly; all subsequent saves do not
- Manually touching config.json triggers reload; saving via control panel does not

**Phase to address:** Phase 2 — Config watcher implementation. Write a test that saves config.json atomically twice and verifies two reload signals are received.

---

### Pitfall 5: `ClipCursor()` Is Reset by Every Input Desktop Switch — Sleep, Lock Screen, UAC Prompt

**Severity:** HIGH

**What goes wrong:**
`ClipCursor()` operates on the current input desktop (the interactive desktop `Winsta0\Default`). When the operating system switches input desktops — which happens on session lock (`Win+L`), sleep/wake, UAC elevation prompts, or Secure Desktop activation — the cursor clip rectangle is **automatically cleared** by Windows. After the user unlocks or returns from sleep, the cursor is free to enter Display 3.

The MS docs state the calling process must have `WINSTA_WRITEATTRIBUTES` access; this access exists only on the interactive desktop. When the session transitions to the Winlogon desktop (lock screen) or Secure Desktop (UAC), the clip is gone.

**Why it happens:**
`ClipCursor` is intentionally scoped to the current input desktop state. Windows clears it to ensure security features (UAC, lock screen) are not obstructed. There is no persistence mechanism in the Win32 API.

**How to avoid:**
Hook `WM_WTSSESSION_CHANGE` (session state) and `WM_DISPLAYCHANGE` messages from the host's window procedure to detect unlock/resume events, then re-apply ClipCursor:
```python
# In host/win32_utils.py — override nativeEvent to intercept Win32 messages
from PyQt6.QtCore import QAbstractNativeEventFilter
import win32con

class Win32EventFilter(QAbstractNativeEventFilter):
    def __init__(self, clip_fn):
        super().__init__()
        self._clip = clip_fn

    def nativeEventFilter(self, event_type, message):
        msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
        if msg.message in (win32con.WM_DISPLAYCHANGE,):
            self._clip()  # re-apply ClipCursor
        return False, 0
```
Register for WTS session notifications using `WTSRegisterSessionNotification` via pywin32 and re-apply ClipCursor in the WM_WTSSESSION_CHANGE handler for `WTS_SESSION_UNLOCK`. Additionally, set a 5-second one-shot QTimer on application focus gain (`QApplication.focusChanged`) as a belt-and-suspenders fallback.

**Warning signs:**
- Cursor enters Display 3 after waking from sleep
- Cursor enters Display 3 after pressing `Win+L` and unlocking
- UAC dialog appears and cursor is unrestricted afterward

**Phase to address:** Phase 1 — ClipCursor implementation. Re-application on wake/unlock must be implemented as a first-class feature, not a later hardening pass.

---

### Pitfall 6: QScreen Geometry Returns Logical (DPI-Scaled) Pixels, Not Physical Pixels on High-DPI Systems

**Severity:** HIGH

**What goes wrong:**
`QScreen.geometry()` returns device-independent (logical) pixels scaled by the monitor's DPI factor. On a monitor at 150% scaling, a 1920x515 physical pixel display reports `geometry()` as approximately 1280x343. If the host window is positioned using this logical size, it renders at 1280x343, leaving a black strip and failing to fill the display. Alternatively, `window.resize(1920, 515)` specifies logical pixels and Qt internally scales, which may produce a window that overflows its physical bounds on the wrong edge.

**Why it happens:**
Qt 6 defaults to Per-Monitor DPI Awareness v2, which means each screen reports its logical coordinate space independently. `QScreen.geometry()` is always in logical coordinates. Physical dimensions are available via `QScreen.physicalSize()` (mm) combined with `QScreen.physicalDotsPerInch()`, but the most direct path is to check `QScreen.devicePixelRatio()` and multiply.

The target display in this project is a 1920x515 strip — unusual dimensions. It may run at 100% DPI scaling. But the primary monitors above it may be at 125% or 150%, causing Qt's virtual desktop coordinate system to report fractional/unexpected geometry for Display 3's origin point.

**How to avoid:**
Identify Display 3 by its physical pixel dimensions, not logical:
```python
target = None
for screen in QApplication.screens():
    # physicalSize() returns mm; use devicePixelRatio to get physical pixels
    logical_geo = screen.geometry()
    dpr = screen.devicePixelRatio()
    phys_w = int(logical_geo.width() * dpr)
    phys_h = int(logical_geo.height() * dpr)
    if phys_w == 1920 and phys_h == 515:
        target = screen
        break
```
Then position the window at the logical origin of that screen, and use `showFullScreen()` (not `resize()`) to let Qt fill the screen naturally:
```python
if target:
    window.setScreen(target)
    window.move(target.geometry().topLeft())
    window.showFullScreen()
```
Store the known physical dimensions in config.json so they can be overridden if the display setup changes.

**Warning signs:**
- Host window does not cover full Display 3; black strip visible at edge
- Host window overflows onto an adjacent monitor
- `QScreen.geometry().width()` reports something other than 1920

**Phase to address:** Phase 1 — Host window. Must be tested on the actual hardware with real DPI values, not a simulator.

---

### Pitfall 7: WinRT `RequestAccessAsync` Must Be Called From a UI Thread — Subprocess Has No UI Thread

**Severity:** HIGH

**What goes wrong:**
The WinRT `UserNotificationListener.RequestAccessAsync()` call requires invocation from a UI thread (a Single-Threaded Apartment, STA, initialized for COM). The notification widget runs in a subprocess that has no QApplication and no STA-initialized thread. Calling `RequestAccessAsync` from a plain Python thread in the subprocess raises `RuntimeError` or returns silently with no permission dialog shown to the user.

**Why it happens:**
WinRT notification access is a user-consent operation that Windows requires to be presented as a visible OS dialog. The OS dialog pump needs an STA COM apartment. Python's asyncio event loop is not automatically COM-apartment-aware. A subprocess started by `multiprocessing.Process(spawn)` initializes as an MTA (Multi-Threaded Apartment) by default.

**How to avoid:**
The permission grant must happen **once** from the host process (which has a running Qt event loop on the main thread, which is STA-compatible on Windows). The notification widget subprocess should only access the listener after permission is granted, and it should call `GetAccessStatus()` — not `RequestAccessAsync()` — to confirm the persisted permission:

```python
# In host: perform the one-time access request
import asyncio
from winrt.windows.ui.notifications.management import (
    UserNotificationListener, UserNotificationListenerAccessStatus
)

async def request_notification_access():
    listener = UserNotificationListener.current
    status = await listener.request_access_async()
    return status == UserNotificationListenerAccessStatus.ALLOWED

# Run from the host main thread before spawning the notification widget
allowed = asyncio.run(request_notification_access())

# In the notification widget subprocess:
from winrt.windows.ui.notifications.management import (
    UserNotificationListener, UserNotificationListenerAccessStatus
)
listener = UserNotificationListener.current
status = listener.get_access_status()
if status != UserNotificationListenerAccessStatus.ALLOWED:
    # Push an error frame, do not attempt to get notifications
    ...
```

**Warning signs:**
- `RequestAccessAsync()` returns but no Windows permission dialog ever appears
- Notification widget subprocess produces empty notification lists indefinitely
- `RuntimeError: access is denied` or `COMError` in subprocess logs

**Phase to address:** Phase 4 — Notification widget. The access grant step must be its own host-side setup task, documented in the onboarding / first-run flow.

---

## v1.1 Supplement: PyInstaller Packaging and Autostart Pitfalls

*Added 2026-03-27. Addresses the new v1.1 scope: standalone .exe via PyInstaller and Windows login autostart.*
*Confidence: HIGH (PyInstaller docs + official multiprocessing docs) | MEDIUM (winrt hidden imports, Task Scheduler GUI interaction) | LOW (winrt-specific PyInstaller hooks)*

---

### Pitfall 8: `multiprocessing.freeze_support()` Missing or Called in Wrong Order — Frozen .exe Spawns Infinite Recursive Processes

**Severity:** BLOCKER

**What goes wrong:**
In a frozen PyInstaller executable, `sys.executable` points to the `.exe` itself, not to `python.exe`. When multiprocessing spawns a worker process, it re-invokes the same `.exe`. Without `multiprocessing.freeze_support()`, the bootloader cannot distinguish a worker-spawn re-entry from a normal startup, so the `.exe` starts fresh each time, which in turn spawns more workers — an exponential process explosion that exhausts handles within seconds. The application appears to crash immediately on launch.

**Why it happens:**
PyInstaller ships a custom override of `freeze_support()` that inspects `sys.argv` for the worker-process marker arguments injected by Python's multiprocessing infrastructure. When those arguments are present, `freeze_support()` diverts execution to the worker bootstrap path and returns normally. Without the call, execution always reaches `main()`, which calls `ProcessManager.start_widget()`, spawning yet more copies.

**How to avoid:**
`freeze_support()` must be called at the very top of the `if __name__ == "__main__":` block, before any multiprocessing usage and critically before `set_start_method()`:

```python
# host/main.py
if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()          # FIRST — before any other multiprocessing call
    multiprocessing.set_start_method("spawn") # SECOND
    main()
```

**Critical ordering note:** `set_start_method()` must come after `freeze_support()`. Calling `set_start_method()` before `freeze_support()` initializes the multiprocessing context, and a subsequent `set_start_method()` raises `RuntimeError: context has already been set`. Confirm the order in the spec/entry point every time the startup sequence changes.

**Warning signs:**
- Task Manager shows dozens of `.exe` processes within 1–2 seconds of launch
- Host `.exe` window never appears; appears to crash immediately
- CPU pegged at 100% immediately after launch
- No error dialog; process exits silently

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Validate by running the built `.exe` once and immediately checking process count in Task Manager before any widget loads.

---

### Pitfall 9: `config.json` Path Resolves to Temp Directory in `--onefile` Build — All Config Reads and Writes Fail Silently

**Severity:** BLOCKER

**What goes wrong:**
`host/main.py` currently opens `"config.json"` as a relative path: `ConfigLoader("config.json", ...)`. In development this resolves relative to the working directory (the project root). In a `--onefile` PyInstaller build, `os.getcwd()` is wherever the `.exe` was launched from — and in a Task Scheduler autostart, that is typically `C:\Windows\System32` or the user's `%USERPROFILE%`. The `config.json` is not there; the open fails with `FileNotFoundError` and the host starts with no widgets and no config.

The same issue affects `control_panel/__main__.py` which passes `config_path="config.json"` and every `os.path.join(config_dir, ...)` call that derives the Pomodoro command file path.

**Why it happens:**
Relative paths resolve from `os.getcwd()`, not from the script's location. In development the IDE and shell both set cwd to the project root. When Windows launches an `.exe` from the registry `Run` key or Task Scheduler (without an explicit `Start In` directory), cwd is system-defined and almost never the directory containing the `.exe`.

**How to avoid:**
Use the executable's location — not `sys._MEIPASS` (which is the temp unpack dir) — as the anchor for user-data files that live beside the `.exe`:

```python
import sys, os

def _exe_dir() -> str:
    """Return the directory containing the running executable (or script in dev)."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

CONFIG_PATH = os.path.join(_exe_dir(), "config.json")
```

Apply this pattern to every path that is a user-editable side-car file (config.json, pomodoro_command.json, any future user data). Bundled read-only assets (fonts, images) that are embedded in the package should use `sys._MEIPASS` instead:

```python
def _bundled_asset(relative_path: str) -> str:
    """Resolve a path to a file bundled inside the executable."""
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, relative_path)
```

**Warning signs:**
- `.exe` launches but no widgets appear; console (if enabled) shows `FileNotFoundError: config.json`
- Works fine from project directory with `python -m host` but fails when `.exe` is double-clicked from Desktop
- Config changes in the control panel `.exe` are not picked up by the host

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Fix path resolution before building the first `.exe`; test by double-clicking from a location other than the project root.

---

### Pitfall 10: `console=False` Causes `sys.stdout is None` — Every `print(..., flush=True)` Call Crashes the Frozen App

**Severity:** HIGH

**What goes wrong:**
The host uses `print(..., flush=True)` extensively for diagnostic output (ConfigLoader, Win32MessageFilter, ClipCursor reapplication, notification access). With `console=False` in the PyInstaller spec (required to suppress the terminal window), `sys.stdout` and `sys.stderr` are set to `None`. Any call to `print()` or `sys.stdout.flush()` raises `AttributeError: 'NoneType' object has no attribute 'write'`. The crash happens immediately — before the Qt event loop starts — if `print()` is called during startup initialization.

**Why it happens:**
PyInstaller's windowed (no-console) build uses the Windows subsystem (`/SUBSYSTEM:WINDOWS`), exactly like `pythonw.exe`. Windows allocates no console and provides no stdin/stdout/stderr handles. Python sets `sys.stdout = None` in this mode. This is by design and matches `pythonw.exe` behavior.

**How to avoid:**
Add a stdout/stderr null-guard at the very top of the entry point, before any print calls or imports that print:

```python
# host/main.py — first lines after imports
import sys, os
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
```

For production builds, replace diagnostic `print()` calls with a logging setup that writes to a file beside the `.exe` so problems can be diagnosed after the fact:

```python
import logging
log_path = os.path.join(_exe_dir(), "monitorcontrol.log")
logging.basicConfig(
    filename=log_path,
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
```

**Warning signs:**
- `.exe` with `console=True` works; `.exe` with `console=False` crashes immediately with no visible error
- Testing with `pythonw.exe host/main.py` reproduces the crash before building the `.exe`
- Error only appears when console output is attempted during startup; app may run silently after (if print is only during init)

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Test with `console=True` first to see startup output, then switch to `console=False` only after a stdout guard is in place.

---

### Pitfall 11: pywin32 DLLs Not Found in Frozen Build — `ImportError: DLL load failed while importing win32api`

**Severity:** HIGH

**What goes wrong:**
pywin32 (311) stores its extension modules (`win32api.pyd`, `win32con.pyd`, `win32gui.pyd`) and the shared `pywintypes311.dll` in non-standard locations inside the Python installation (`Lib/site-packages/win32/` and `pywin32_system32/`). PyInstaller's static analysis misses these because they are loaded via a custom post-install hook, not through normal `import` chains. The built `.exe` raises `ImportError: DLL load failed while importing win32api` or `Could not import pywintypes` at runtime.

**Why it happens:**
PyInstaller collects modules by tracing imports. pywin32's DLLs are loaded through a combination of `sys.path` manipulation and `LoadLibrary` calls in `pywintypes`'s `__init__`, which static analysis does not trace. The `pywin32_postinstall.py` script registers the DLL path in the Windows registry during install; at runtime the standard Python build finds them via this registry entry, but the frozen app has no such registration.

**How to avoid:**
Explicitly collect pywin32 binaries in the `.spec` file. The `pyinstaller-hooks-contrib` package (shipped with modern PyInstaller) includes hooks for pywin32 that handle most of this automatically, but verify the hook version covers pywin32 311:

```python
# In .spec file
from PyInstaller.utils.hooks import collect_dynamic_libs

binaries = collect_dynamic_libs("win32")
```

Also ensure `pywin32-ctypes` is installed in the build environment — PyInstaller itself uses it internally and will warn if absent. If `pywintypes311.dll` still fails to load, add it explicitly:

```python
binaries = [
    ("path/to/site-packages/pywin32_system32/pywintypes311.dll", "."),
]
```

**Warning signs:**
- Build completes without error but `.exe` fails immediately with DLL import error
- Error message references `pywintypes`, `win32api`, or `win32con`
- Running `pyinstaller --debug=imports` reveals pywin32 DLLs not collected

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Verify pywin32 imports work in the built `.exe` before adding winrt or other dependencies.

---

### Pitfall 12: winrt-* Packages Are Namespace Packages — PyInstaller Misses All Submodule Imports Without Explicit Collection

**Severity:** HIGH

**What goes wrong:**
The six `winrt-*` packages (winrt-runtime, winrt-Windows.UI.Notifications.Management, etc.) use Python's namespace package mechanism: the top-level `winrt` namespace is shared across all six packages. PyInstaller's import tracer handles namespace packages poorly — it may collect the `winrt` namespace stub but miss the extension modules (`_winrt.pyd`, `winrt/windows/ui/notifications/_winrt_Windows_UI_Notifications.pyd`, etc.) because they are not reachable via static `import` analysis from deferred import calls inside the notification widget.

Additionally, the notification widget uses deferred imports (`from winrt.windows.ui.notifications.management import ...` inside `_get_winrt_listener()`) which PyInstaller's static analyzer does not trace at all.

**Why it happens:**
PyInstaller traces `import` statements at module load time. Imports inside methods (deferred imports) are invisible to static analysis. Namespace package sub-modules split across multiple installed packages require PyInstaller to enumerate each package's `__path__` separately; without community hooks for these specific packages, this enumeration does not happen automatically.

**How to avoid:**
Write a custom hook or add explicit hidden imports in the `.spec` file. There are no known community hooks for `winrt-*` 3.2.1 in `pyinstaller-hooks-contrib` as of 2026. Use `collect_submodules()` for each winrt package and add the `.pyd` extension binaries explicitly:

```python
# In .spec file Analysis block
from PyInstaller.utils.hooks import collect_submodules, collect_dynamic_libs

hiddenimports = [
    *collect_submodules("winrt"),
]
binaries = [
    *collect_dynamic_libs("winrt"),
]
```

Alternatively, move all winrt imports to module-level in `notification/widget.py` (top of file, not inside methods). This makes them visible to PyInstaller's static analysis and eliminates the need for manual hidden import declarations.

**Warning signs:**
- Build succeeds but notification widget subprocess crashes with `ModuleNotFoundError: No module named 'winrt.windows'`
- Works in development (`python -m host`) but fails in `.exe`
- `pyinstaller --debug=imports` output shows `winrt` top-level collected but no submodules

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Test the notification widget end-to-end in the built `.exe` before shipping; it is the most likely to have hidden import gaps.

---

### Pitfall 13: Task Scheduler "Run Whether User Is Logged On or Not" Makes GUI Invisible — Host Window Never Appears

**Severity:** BLOCKER (if used; avoidable by choosing the right option)

**What goes wrong:**
Task Scheduler offers two logon modes. "Run whether user is logged on or not" runs the task in a non-interactive session. Any GUI window the process creates is invisible — it exists in a session 0 desktop that no user can see. The host would start successfully (no crash), ClipCursor would apply, all widget processes would spawn, but the window would never be visible. The display would show whatever was on Display 3 before (nothing, or a previous frame).

**Why it happens:**
Windows runs background services in Session 0, which has no interactive desktop. "Run whether user is logged on or not" does not guarantee Session 0 but it does not guarantee interactive session access either; on Windows 11, it consistently produces a non-interactive context for newly registered tasks. "Run only when user is logged on" runs the task in the user's own interactive session (Session 1+), where GUI windows are visible.

**How to avoid:**
Always configure the Task Scheduler task with "Run only when user is logged on" for any task that creates visible windows. In schtasks command-line terms:

```bat
schtasks /Create /TN "MonitorControl Host" /TR "\"C:\path\to\host.exe\"" ^
  /SC ONLOGON /RL HIGHEST /F
```

Do NOT add `/RU SYSTEM` — this forces Session 0. Use the user's own account (omit `/RU` or explicitly pass `/RU "<username>"`).

Additionally, set the Start In directory explicitly so `config.json` resolves correctly (belt-and-suspenders alongside the `_exe_dir()` pattern):

```bat
schtasks /Create /TN "MonitorControl Host" /TR "\"C:\path\to\host.exe\"" ^
  /SC ONLOGON /RL HIGHEST /SD "C:\path\to\" /F
```

**Warning signs:**
- Task reports "Last Run Result: 0x0" (success) but window never appears
- Host process is visible in Task Manager but Display 3 remains dark
- Switching task to "Run only when user is logged on" fixes it

**Phase to address:** Phase 2 of v1.1 (autostart implementation). Validate by creating the task, logging out, and logging back in — not just running the task manually from Task Scheduler UI.

---

### Pitfall 14: Registry Run Key vs Task Scheduler — UAC and Elevation Behavior Differs Significantly

**Severity:** MEDIUM

**What goes wrong:**
The registry `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` key is simpler to set programmatically (one `winreg.SetValueEx` call) but has two problems for this project:

1. **No working directory control.** Registry Run entries do not support a "Start In" field. The process starts with `cwd` set to whatever Windows decides (usually `C:\Windows\System32` on Win11). Without the `_exe_dir()` pattern (Pitfall 9), config.json will not be found.

2. **Cannot run with elevated privileges without a UAC prompt.** `ClipCursor()` requires `WINSTA_WRITEATTRIBUTES` but does not require elevation — it works fine as a standard user. However, if any future feature requires elevation (e.g., a Windows service interaction), the registry Run key approach cannot be used without triggering a UAC prompt at every login. Task Scheduler with `RL HIGHEST` is the correct path for elevatable autostart.

**Why it happens:**
The registry Run key is essentially a shortcut — Windows `userinit.exe` executes each value as a command string with no metadata for cwd, elevation, or session constraints. Task Scheduler is a full scheduling engine with explicit fields for all of these.

**How to avoid:**
Use Task Scheduler for autostart, not the registry Run key. The control panel's autostart toggle should call `schtasks` (via `subprocess`) or use the Windows Task Scheduler COM API (via pywin32's `win32com.client`) to create/delete the task. Do not use the registry Run key for this project. The registry approach is acceptable only for non-GUI background scripts that have no path dependencies and require no elevation.

**Warning signs:**
- Registry Run autostart works when double-clicking the `.exe` but fails when launched at login (different cwd)
- Future elevation requirement breaks the registry approach at the worst possible time

**Phase to address:** Phase 2 of v1.1 (autostart implementation). Make the decision between Task Scheduler and registry Run key explicit in the phase spec and document the rationale.

---

### Pitfall 15: `--onefile` Extracts to `%TEMP%\_MEIxxxxxx` — Antivirus Quarantines or Blocks Extraction

**Severity:** MEDIUM

**What goes wrong:**
PyInstaller `--onefile` builds unpack all bundled files to a temporary directory under `%TEMP%` at every launch. On Windows 11 with Defender or third-party AV, this extraction pattern (a self-modifying executable writing DLLs to temp) triggers heuristic scanning. The most common symptom is a 2–10 second delay at startup while AV scans extracted files. In aggressive AV configurations, the extracted `.pyd` files or DLLs are quarantined mid-extraction and the app crashes with `ImportError` or silent exit.

**Why it happens:**
Self-extracting executables that unpack native code into `%TEMP%` match the behavioral profile of many malware dropper patterns. Windows Defender's real-time protection scans every file written to `%TEMP%`.

**How to avoid:**
Use `--onedir` (the default) instead of `--onefile`. A `--onedir` build produces a folder with an `.exe` and all dependencies alongside it. There is no temp-extraction step, no AV trigger, and startup is faster. For a single-user desktop tool that is installed once, `--onedir` is strictly preferable to `--onefile`. Distribute as a zip archive or simple installer rather than a self-extracting single file.

If `--onefile` is required (it is not for this project), sign the executable with a code-signing certificate and add a Defender exclusion. Do not rely on exclusion as a shipping solution.

**Warning signs:**
- `.exe` runs in development environment but not on a freshly provisioned machine
- Startup takes 5+ seconds with no visible progress
- Defender quarantine log shows `.pyd` or `.dll` files removed from `%TEMP%\_MEI*`

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Choose `--onedir` in the spec file from the start; do not build `--onefile` unless there is a specific distribution requirement for it.

---

### Pitfall 16: Multiprocessing Worker Subprocess in Frozen App Inherits Modified DLL Search Path — pywin32 DLLs Not Found in Child

**Severity:** MEDIUM

**What goes wrong:**
PyInstaller's bootloader calls `SetDllDirectoryW` to prioritize bundled DLLs over system DLLs. This modified DLL search path is inherited by all child processes spawned via `multiprocessing.Process`. If the child imports pywin32 (e.g., a future widget that uses win32api), the DLL resolution order may find the wrong `pywintypes311.dll` — or no DLL at all if pywin32 system DLLs were not bundled — causing `ImportError` in the child. The parent can import pywin32 fine while the child fails.

**Why it happens:**
Windows `CreateProcess` inherits the parent's DLL search path by default. PyInstaller deliberately sets `SetDllDirectoryW` to an empty string (`""`) or a bundle-specific path to prevent system DLL conflicts. This helps the parent but can strand children that depend on DLLs registered in the system path but not in the bundle.

**How to avoid:**
In the frozen-app-aware entry of each subprocess target function, reset the DLL directory before any imports that touch pywin32:

```python
# In each widget's run_*_widget() function, before other imports
import sys
if getattr(sys, "frozen", False):
    import ctypes
    ctypes.windll.kernel32.SetDllDirectoryW(None)
```

Current widget processes (pomodoro, calendar, notification) use Pillow and winrt — both of which have their own DLL loading requirements. This reset should be harmless for Pillow and may be necessary for winrt's own `.pyd` extensions.

**Warning signs:**
- Widget subprocesses crash with `ImportError` immediately on spawn
- Error references DLL load failure, not module-not-found
- Parent process (host) runs correctly but a specific widget subprocess always fails

**Phase to address:** Phase 1 of v1.1 (PyInstaller packaging). Add the DLL reset to all widget subprocess entry points during the packaging phase and verify each widget subprocess starts successfully in the built `.exe`.

---

## v1.2 Supplement: Configurable Color System Pitfalls

*Added 2026-03-27. Addresses the v1.2 scope: moving background ownership to host, per-widget color config, HSL color picker widget in control panel, colorsys conversions, zero-visual-change upgrade guarantee.*
*Confidence: HIGH (Python colorsys docs, Qt QColor docs, Pillow ImageColor source) | MEDIUM (QPainter transparent compositing behavior, swatch repaint pattern) | LOW (edge-case color picker DPI behavior)*

---

### Pitfall 17: `colorsys.hls_to_rgb()` Argument Order Is H-L-S, Not H-S-L — Saturation and Lightness Are Swapped

**Severity:** HIGH

**What goes wrong:**
The developer writes a color conversion expecting HSL (Hue-Saturation-Lightness) convention and calls `colorsys.hls_to_rgb(hue, saturation, lightness)`. Python's `colorsys` module uses **HLS** ordering: `hls_to_rgb(h, l, s)` — lightness is the second argument, saturation is the third. Passing them reversed produces colors that look wildly wrong: a high-saturation vivid red becomes a muted pastel; a low-saturation gray becomes a fully saturated color. The confusion is compounded because the function name `hls_to_rgb` does not spell out the argument order.

**Why it happens:**
The industry-standard "HSL" order (Hue, Saturation, Lightness) used by CSS, most color pickers, and Qt's own `QColor.fromHslF()` puts saturation before lightness. Python's `colorsys` module uses the opposite HLS convention inherited from older color science literature. The function signature `hls_to_rgb(h, l, s)` is documented but the name alone is ambiguous to anyone who learned HSL from CSS or web tooling.

**How to avoid:**
Always name the arguments explicitly at call sites or use a wrapper function:
```python
import colorsys

def hsl_to_rgb_tuple(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
    """Convert HSL (CSS convention) to RGB. All inputs 0.0-1.0, outputs 0-255."""
    r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)  # NOTE: l before s
    return (round(r * 255), round(g * 255), round(b * 255))
```
Name the wrapper after the CSS convention (HSL) so callers never interact with the HLS order directly. Never call `colorsys.hls_to_rgb` at inline call sites with positional arguments — always use the wrapper.

**Warning signs:**
- Color picker swatch shows a muted color when the saturation slider is at maximum
- Picking a gray (saturation = 0) produces an unexpected vivid color
- Unit test `hsl_to_rgb(0.0, 1.0, 0.5)` (pure red) returns something other than `(255, 0, 0)`

**Phase to address:** v1.2 Phase 1 — ColorPickerWidget implementation. Write a unit test with known HSL → RGB values (pure red, pure green, pure blue, gray) before any picker UI is built.

---

### Pitfall 18: `colorsys` All-Inputs-Are-0–1 — Passing Integer 0–255 RGB or Integer 0–360 Hue Produces Silent Wrong Output

**Severity:** HIGH

**What goes wrong:**
`colorsys.hls_to_rgb()` and `colorsys.rgb_to_hls()` expect all inputs in the range `[0.0, 1.0]`. If a developer passes an integer hue in the range 0–360 (as used by CSS and QSlider values), or integer RGB values in 0–255, the function does not raise an error — it returns values outside `[0.0, 1.0]` silently. Downstream code that passes these unclamped floats to Pillow's `Image.new()` as an RGBA tuple gets clamped or wrapped to unexpected colors.

**Why it happens:**
`colorsys` performs no input validation. Passing `hue=180` (degrees) when 0–1 is expected gives `hls_to_rgb(180, l, s)` which computes a hue wrapping at 180×6 = 1080 full rotations and lands back at hue=0 (red). The result is wrong but not obviously so. QSlider returns integer values (0–359 for hue, 0–100 for percent intensity) that must be normalized before passing to colorsys.

**How to avoid:**
Normalize at the boundary where QSlider values enter the color math:
```python
# QSlider range: hue 0..359, intensity 0..100
hue_norm = hue_slider.value() / 359.0
intensity_norm = intensity_slider.value() / 100.0
```
Always keep the normalized 0–1 floats internal to the color math layer; convert to 0–255 integers only at the final step when constructing a Pillow RGBA tuple or a hex string. Never mix conventions in the same function.

**Warning signs:**
- Color swatch is always red or always white regardless of slider position
- `colorsys.hls_to_rgb()` returns values greater than 1.0 or less than 0.0
- QSlider value is used directly in a colorsys call without division

**Phase to address:** v1.2 Phase 1 — ColorPickerWidget. Add an assertion or explicit normalization at every point where slider integer values cross into color math.

---

### Pitfall 19: `QColor.fromHslF()` Hue for Achromatic Colors Is -1, Not 0 — Storing or Round-Tripping via Hex Loses Achromatic

**Severity:** MEDIUM

**What goes wrong:**
When a user sets saturation to 0 (a gray), Qt's `QColor.hslHueF()` returns `-1` to indicate "no hue" (achromatic). If the ColorPickerWidget reads back a stored `#808080` hex value via `QColor` and calls `hslHueF()` to restore the hue slider position, it gets `-1`. Passing `-1` to the hue slider as a position value (or to colorsys) produces an out-of-range crash or places the slider at the minimum. The user's hue preference is lost after any round-trip through gray.

**Why it happens:**
The achromatic hue convention (`-1` in Qt, undefined in CSS) is a mathematical reality: when saturation is zero, all hues map to the same gray and hue is undefined. Qt documents this behavior but it is easy to miss. The problem only manifests for grays — the entire color range with saturation = 0.

**How to avoid:**
Track the hue slider's last-set value separately from the displayed color value. Do not read back the hue from a derived hex string:
```python
class ColorPickerWidget(QWidget):
    def __init__(self, ...):
        self._hue = 0.0       # 0.0..1.0 — persists even when saturation=0
        self._intensity = 0.5  # 0.0..1.0

    def _set_from_hex(self, hex_str: str) -> None:
        color = QColor(hex_str)
        hue = color.hslHueF()
        if hue >= 0.0:  # only update hue if the color is not achromatic
            self._hue = hue
        self._intensity = color.lightnessF()
        # Do NOT update _hue when hue == -1; keep last-known hue
```
This is the same pattern used by all professional color pickers: the hue ring stays at its last position when the user drags saturation to zero.

**Warning signs:**
- Dragging saturation to 0, then back up, always snaps hue to the leftmost position
- Setting a gray via hex input loses the previous hue
- Unit test: set hue to 0.5 (cyan), reduce saturation to 0, increase saturation — hue should still be 0.5

**Phase to address:** v1.2 Phase 1 — ColorPickerWidget. Test round-trip through zero-saturation explicitly before integration.

---

### Pitfall 20: `ImageColor.getrgb()` Raises `ValueError` on Invalid Hex — Uncaught Exception Crashes Widget Subprocess

**Severity:** HIGH

**What goes wrong:**
The Pomodoro widget calls `ImageColor.getrgb(hex_color)` to parse accent colors from config. If the user typed a malformed hex string into the color field (e.g., `"#ff44"`, `"#gg0000"`, `"red"` without quotes, or an empty string), `ImageColor.getrgb()` raises `ValueError`. In a widget subprocess, this exception propagates out of `render_frame()`, terminates `run()`, and kills the subprocess. The host compositor marks the slot as crashed (dark red fill) and the widget disappears from the bar. The only recovery is a config change or host restart.

**Why it happens:**
`ImageColor.getrgb()` validates color strings strictly. Any string not matching a known color name, 3/4/6/8-digit hex, or CSS color function raises `ValueError`. The control panel's hex QLineEdit has no format validation, so invalid strings can reach config.json. When the widget subprocess receives this config via `ConfigUpdateMessage`, it calls `getrgb()` during the next render and crashes.

**How to avoid:**
Validate and normalize hex colors at two points:
1. In the control panel before saving to config — reject invalid inputs at the UI layer with a visual indicator.
2. In the widget's `_apply_config()` with a safe fallback:
```python
def _safe_hex_color(self, value: str, fallback: str) -> str:
    """Return value if it is a valid Pillow color string, else fallback."""
    try:
        from PIL import ImageColor
        ImageColor.getrgb(value)
        return value
    except (ValueError, AttributeError):
        return fallback
```
Call `_safe_hex_color()` whenever applying color settings from config. The widget subprocess must never crash from a bad color value — it should silently use the fallback.

**Warning signs:**
- Pomodoro widget slot turns dark red after editing accent color in control panel
- Widget subprocess disappears from bar immediately after a config save with a new color
- `ValueError: unknown color specifier` in widget subprocess logs

**Phase to address:** v1.2 Phase 2 — Pomodoro color picker integration. Add `_safe_hex_color()` to PomodoroWidget before replacing hex QLineEdit fields with ColorPickerWidget.

---

### Pitfall 21: Widget Background Color Ownership Transfer — Widget Renders Opaque Background, Host Also Fills Background — Double-Fill Causes Color Conflict

**Severity:** HIGH

**What goes wrong:**
Currently widgets render with a hardcoded opaque `bg_color` (e.g., `Image.new("RGBA", (W, H), (26, 26, 46, 255))`). The host `paintEvent` fills the entire window with `#000000` before compositing widget frames. When `bg_color` is moved to the host (BG-01), if widget code still fills with its own background color, the user-configured `bg_color` set in the host is overwritten by the widget's fill on every frame. The bar appears to use the widget's hardcoded color, not the user's chosen color.

**Why it happens:**
The natural migration path is: (1) add `bg_color` to host, (2) test. If the widget's `Image.new("RGBA", ...)` still uses an opaque color tuple as its background, the widget's fill covers the host's fill completely. The widget's rgba_bytes contain fully opaque pixels that `painter.drawImage()` composites with `SourceOver` — which for alpha=255 pixels simply replaces whatever is below.

**How to avoid:**
When migrating background ownership to the host, make widget backgrounds **transparent** simultaneously:
```python
# Widget: change opaque background to transparent
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))  # fully transparent

# Host paintEvent: fill with user-configured color
bg = QColor(self._bg_color)  # from config
painter.fillRect(self.rect(), bg)
self.compositor.paint(painter)  # composites widget frames on top
```
Treat this as a single atomic change: widgets go transparent at the same commit that host gains the configurable fill. Do not make one without the other.

**Warning signs:**
- Changing `bg_color` in the control panel has no visible effect on the bar
- The bar color appears to be the widget's hardcoded color, not the configured one
- The bar changes color when all widgets are stopped but not when they are running

**Phase to address:** v1.2 Phase 1 — Background ownership migration. The transparency switch and host color fill must be done in the same phase, not sequentially. Write a test that verifies a configured `bg_color` of `#ff0000` produces a red bar when no widgets are running.

---

### Pitfall 22: Transparent Widget Frame Composited Over Old Frame — Previous Frame Content Bleeds Through on Repaint

**Severity:** MEDIUM

**What goes wrong:**
After widgets switch to transparent backgrounds, the host's `paintEvent` fills the background with the configured `bg_color` before calling `compositor.paint()`. This is correct. However, if the Compositor's `painter.drawImage()` uses the default `CompositionMode_SourceOver` and the widget frame contains partially transparent pixels (alpha < 255) at some edges due to antialiased text, those pixels blend with the background correctly on the first paint. On subsequent paints, if the background fill does not cover the entire window each time, stale pixel content can persist at the edges of widget frames.

**Why it happens:**
Qt's `paintEvent` is not guaranteed to clear the widget's backing store before calling the handler. If `Qt::WA_OpaquePaintEvent` is not set and the widget does not fill its entire rect, leftover pixels from previous frames remain. The background `fillRect(self.rect(), bg)` must be the first operation and must cover the full window rect every time.

**How to avoid:**
Ensure the background fill always covers the full rect, every paint:
```python
def paintEvent(self, event):
    painter = QPainter(self)
    # Always fill full rect first, not just event.rect()
    painter.fillRect(self.rect(), QColor(self._bg_color))
    self.compositor.paint(painter)
    painter.end()
```
Do not optimize to `event.rect()` (the dirty rect) for the background fill — the background must always be complete to prevent bleed-through from previous frames. The compositor's widget frame drawing can restrict to the slot rect, but the background must be full-window.

**Warning signs:**
- Faint ghost of previous widget content visible at slot edges after bg_color changes
- Widget antialiased text edges show artifacts when bg_color is changed to a contrasting color
- Artifacts appear only after the first color change, not at startup

**Phase to address:** v1.2 Phase 1 — Background ownership migration. Add `WA_OpaquePaintEvent` to the host window and always fill `self.rect()` (not `event.rect()`) as the first operation in `paintEvent`.

---

### Pitfall 23: `config.json` Missing Top-Level `bg_color` Key — Existing Configs Without the Key Crash on Upgrade

**Severity:** HIGH

**What goes wrong:**
The host's `paintEvent` is updated to read `bg_color` from config: `self._bg_color = config["bg_color"]`. An existing `config.json` from v1.1 does not have this key. When the host loads this config on upgrade, it raises `KeyError: 'bg_color'` and fails to start, or `paintEvent` raises `KeyError` on the first paint and crashes the host. The user is left with a broken bar that worked fine before upgrading.

**Why it happens:**
Adding a new required top-level config key without a default-fallback is a breaking config schema change. The config has no versioning field. The control panel writes complete configs when the user saves, but existing config files on disk will not be updated until the user opens the control panel and saves.

**How to avoid:**
Always use `.get()` with the exact hardcoded default that matches the prior behavior:
```python
# In host, when reading bg_color
self._bg_color = config.get("bg_color", "#000000")  # default matches prior paintEvent fill
```
The default `"#000000"` is identical to the `QColor("#000000")` that the current `paintEvent` hardcodes. This guarantees zero visual change on upgrade even if the user never opens the control panel.

Apply the same pattern to all new widget-level color keys:
```python
# In CalendarWidget.__init__, reading new time_color
settings = config.get("settings", {})
self._time_color = _parse_color(settings.get("time_color", "#ffffff"))  # matches hardcoded (255,255,255,255)
self._date_color = _parse_color(settings.get("date_color", "#dcdcdc"))  # matches hardcoded (220,220,220,255)
```
**Do not** use `config["bg_color"]` — bracket access for any key that may be absent in an existing config.

**Warning signs:**
- Host fails to start after adding a new config key, but works fine when config.json is deleted and recreated
- `KeyError` in host logs at startup or in `paintEvent`
- Unit test: load a v1.1 config (without new keys) into the new host — host must start and display correctly

**Phase to address:** v1.2 Phase 1 — Background ownership migration. Establish the `.get()` with exact defaults pattern as a non-negotiable rule before writing any config-reading code for new color keys.

---

### Pitfall 24: Default Colors Must Exactly Match Hardcoded Values — Off-by-One Causes Visible Change on Upgrade

**Severity:** MEDIUM

**What goes wrong:**
The developer sets `bg_color` default to `"#1a1a1a"` in the new config code, but the prior `paintEvent` hardcoded `QColor("#000000")` (pure black). Or: calendar widget's `time_color` default is set to `(255, 255, 255, 255)` but the prior `_text_color` used for dates was actually `(220, 220, 220, 255)` and the developer confused the two. Any mismatch causes a perceptible color change when the user upgrades without ever touching the color settings.

The existing code has:
- `HostWindow.paintEvent`: `QColor("#000000")` — background
- `CalendarWidget._bg_color`: `(26, 26, 46, 255)` — `#1a1a2e`
- `CalendarWidget._text_color`: `(220, 220, 220, 255)` — date text
- `CalendarWidget._time_color`: `(255, 255, 255, 255)` — time text
- `PomodoroWidget._bg_color`: `(26, 26, 46, 255)` — `#1a1a2e`
- `PomodoroWidget._work_color`: `"#ff4444"` (from config default, not hardcoded in `__init__`)

**Why it happens:**
The developer copies defaults from memory or from the spec rather than from the actual code. Widget backgrounds are `#1a1a2e` but the host background is `#000000` — these are different colors. If the widget background ownership moves to the host but the default is set to `#1a1a2e` rather than `#000000`, the bar background color changes from black to dark blue-black on upgrade.

**How to avoid:**
Before writing any default value, read the exact value from the source code:
```
Host paintEvent:       #000000  → bg_color default
CalendarWidget bg:     #1a1a2e  → this moves to transparent; host bg_color controls the bar
CalendarWidget time:   #ffffff  → time_color default
CalendarWidget date:   #dcdcdc  → date_color default
PomodoroWidget bg:     #1a1a2e  → same; moves to transparent
PomodoroWidget label:  #c8c8c8  → (200,200,200,255); not configurable in v1.2
```

Note: widgets currently render their own `bg_color` fill (`#1a1a2e` dark blue). This is the color users see as the "background." The host's `#000000` fill only shows in gaps between widgets. When background ownership moves to host, the correct default for `bg_color` is `#1a1a2e` (the widget bg color), not `#000000`. The black host fill was always hidden under the widget fills.

**Warning signs:**
- The bar looks slightly different after upgrading before the user changes anything
- A specific region of the bar changes color on upgrade
- Regression test: render the bar with new code + default config; pixel-diff against v1.1 render — diff should be zero

**Phase to address:** v1.2 Phase 1 — Background ownership migration. Audit every color value in the existing code and produce an exact defaults table before writing a single line of new color-handling code.

---

### Pitfall 25: ColorPickerWidget `update()` Not Called After Slider Value Changes — Swatch Does Not Repaint

**Severity:** MEDIUM

**What goes wrong:**
The color swatch in `ColorPickerWidget` is a QWidget subclass with a custom `paintEvent`. The developer connects the slider's `valueChanged` signal to a method that updates the internal color state but forgets to call `self._swatch.update()` (or `self.update()` if the swatch is the widget itself). The swatch shows the initial color and never changes as the user moves the sliders, even though the internal state is being updated correctly.

**Why it happens:**
Qt does not repaint custom widgets automatically when internal data changes — only when the widget's backing store is invalidated via `update()` or `repaint()`. The `paintEvent` is only called when Qt determines the widget needs repainting (e.g., resize, expose, explicit `update()` call). A slot that changes `self._color` and returns without calling `update()` will leave the swatch visually stale.

**How to avoid:**
Always call `self.update()` at the end of any slot that modifies visible state:
```python
def _on_slider_changed(self) -> None:
    hue = self._hue_slider.value() / 359.0
    intensity = self._intensity_slider.value() / 100.0
    self._current_color = _hsl_to_qcolor(hue, intensity)
    self._swatch.update()  # schedule repaint of the swatch widget
    self.colorChanged.emit(self._current_color.name())
```
Use `update()` (deferred, coalesced by Qt) not `repaint()` (immediate, bypasses coalescing). Using `repaint()` in a tight signal loop causes excessive repaints.

**Warning signs:**
- Moving sliders emits the `colorChanged` signal (verifiable with a print) but swatch stays the same color
- Swatch updates only when the window is resized or another window overlaps it
- `paintEvent` on the swatch is called 0 times after slider moves (add a counter to verify)

**Phase to address:** v1.2 Phase 1 — ColorPickerWidget. Include a smoke test: connect slider, move it, verify swatch shows new color without triggering any external repaint.

---

### Pitfall 26: Hex Input Field and Sliders Out of Sync — One Path Updates, Other Doesn't

**Severity:** MEDIUM

**What goes wrong:**
`ColorPickerWidget` has two input paths: sliders and a hex QLineEdit. If the developer only connects `_on_slider_changed → update hex field` and `_on_hex_changed → update sliders`, but forgets to re-update the swatch after a hex change, the swatch stays at the slider color. Or: the hex → slider update path uses `setValue()` which triggers `valueChanged`, which triggers `_on_slider_changed`, which overwrites the hex field again, causing an infinite signal loop.

**Why it happens:**
Two-way bindings between sliders and a text field require careful signal blocking. Qt's `blockSignals(True)` pattern exists for this reason but is easy to forget. Without it, changing the hex field calls a slot that sets slider values, which emit `valueChanged`, which call `_on_slider_changed`, which update the hex field, and so on.

**How to avoid:**
Use `blockSignals()` when programmatically updating a widget to break the feedback loop:
```python
def _set_sliders_from_color(self, color: QColor) -> None:
    """Update sliders from a color value without triggering recursive signals."""
    self._hue_slider.blockSignals(True)
    self._intensity_slider.blockSignals(True)
    hue = color.hslHueF()
    if hue >= 0.0:
        self._hue_slider.setValue(round(hue * 359))
    self._intensity_slider.setValue(round(color.lightnessF() * 100))
    self._hue_slider.blockSignals(False)
    self._intensity_slider.blockSignals(False)
    self._swatch.update()
```
Apply `blockSignals()` symmetrically: when hex updates sliders, block slider signals; when sliders update hex, block hex textChanged signal.

**Warning signs:**
- RecursionError or rapid infinite loop on any slider movement
- Typing a hex value causes the sliders to flicker repeatedly
- Hex field value reverts to a previous value after typing

**Phase to address:** v1.2 Phase 1 — ColorPickerWidget. Test hex→slider and slider→hex update paths explicitly; verify no signal loop with a counter on each slot.

---

### Pitfall 27: Hot-Reload Delivers `bg_color` Only to Host — But Host Does Not Read It From `ConfigUpdateMessage`

**Severity:** HIGH

**What goes wrong:**
The existing hot-reload reconcile path in `ConfigLoader._reconcile()` sends `ConfigUpdateMessage` only to widget processes for changed widget configs. Top-level config keys like `bg_color` are not forwarded to any widget. The host itself is not a widget and has no in_queue. When the user changes `bg_color` in the control panel and saves, the config is hot-reloaded, widget configs are reconciled, but the host's `_bg_color` attribute is never updated. The bar continues showing the old background color until the host is restarted.

**Why it happens:**
The current reconcile logic only processes `config["widgets"]`, not top-level keys. The host compositor reads config at startup via `ConfigLoader.load()` and then reacts to widget-level changes via `_reconcile()`. There is no mechanism for the host to be notified of top-level config changes. Adding `after_reload` callback exists but is currently used only for `reapply_clip` — it is not used to push new config values to the host window.

**How to avoid:**
Use the existing `after_reload` callback in `ConfigLoader` to deliver updated top-level config to the host window:
```python
# In host/main.py
def on_config_reload():
    new_cfg = config_loader.current_config
    window.apply_host_config(new_cfg)  # updates bg_color, etc.
    reapply_clip()

config_loader = ConfigLoader(str(_cfg), pm, window.compositor, after_reload=on_config_reload)
```
```python
# In host/window.py
def apply_host_config(self, config: dict) -> None:
    self._bg_color = config.get("bg_color", "#1a1a2e")
    self.update()  # schedule repaint with new background color
```

**Warning signs:**
- Changing `bg_color` in control panel and saving has no visible effect on the bar
- Restarting the host after a `bg_color` change shows the new color (confirms config is saved correctly, but live reload is broken)
- Widget configs update live but `bg_color` does not

**Phase to address:** v1.2 Phase 1 — Background ownership migration. Wire the `after_reload` callback to call `window.apply_host_config()` in the same phase that adds `bg_color` reading to the host.

---

### Pitfall 28: PyInstaller-Packaged Control Panel Does Not Include New ColorPickerWidget Module

**Severity:** MEDIUM

**What goes wrong:**
`ColorPickerWidget` is added as `control_panel/color_picker.py`. The PyInstaller spec for the control panel does not explicitly list this new module. If the module is imported at the top level of `main_window.py`, PyInstaller's static analysis picks it up. However, if it is imported inside a method (deferred import) or conditionally, the static analysis misses it and the built `.exe` fails with `ModuleNotFoundError: No module named 'control_panel.color_picker'`.

**Why it happens:**
PyInstaller relies on static import analysis. Deferred imports inside methods or conditional imports based on runtime state are not traced. Adding a new module to the `control_panel` package is safe if the import is at module level, but risky if it is inside `_build_pomodoro_tab()` or similar.

**How to avoid:**
Always import `ColorPickerWidget` at the top of `main_window.py`, not inside `_build_*_tab()` methods:
```python
# control_panel/main_window.py — TOP of file
from control_panel.color_picker import ColorPickerWidget
```
After any packaging change, run the full end-to-end smoke test on the built `.exe`: open the Pomodoro tab, verify the color pickers appear, change a color, save, verify the host reflects the change. Do not ship without this test.

**Warning signs:**
- Control panel `.exe` crashes when opening the Pomodoro or Calendar tab
- Error log shows `ModuleNotFoundError` for `color_picker`
- Works in development (`python -m control_panel`) but fails in built `.exe`

**Phase to address:** v1.2 Phase 3 — Control panel integration + packaging rebuild. Rebuild the `.exe` after adding ColorPickerWidget and run the smoke test before marking the phase complete.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Hardcode `screens()[2]` as Display 3 index | Faster initial setup | Breaks silently after sleep/wake, driver update, or reboot that reorders monitor enumeration | Never — match by geometry from day one |
| Use `queue.put()` (blocking) in widget | Simpler widget code — no exception handling | Causes widget to hang if host drain falls behind; deadlock risk at shutdown | Never — always use `put(block=False)` with `queue.Full` guard |
| Skip `cancel_join_thread()` on widget exit | Ensures all data is flushed | Widget process never exits cleanly if queue has unconsumed items; shutdown hangs | Never in shutdown paths; acceptable in steady state (queue is continuously drained) |
| Omit re-add after `fileChanged` | Simpler ConfigLoader | Hot-reload silently stops working after first atomic save; goes unnoticed until tested | Never — this is a one-line fix with no downside |
| Use `QTimer` polling instead of `QThread` for queue drain | Less complexity | Blocks Qt event loop on each drain cycle if queue is not empty; visible UI stutter on large FrameData payloads | Acceptable only for the dummy widget prototype; must be replaced before Pomodoro widget |
| Import PyQt6 in widget subprocess | Convenient for off-screen rendering with Qt tools | QApplication initialized in subprocess conflicts with host Qt context on Windows (spawn); crashes or silent rendering failures | Never — use Pillow for off-screen rendering in widget processes |
| Single `ClipCursor()` call at startup with no recovery | Simple to implement | Cursor enters Display 3 after any session event; permanent usability regression | Never — ClipCursor recovery is a first-class feature of this project's core value proposition |
| Use registry Run key for autostart instead of Task Scheduler | One `winreg` call; no schtasks dependency | No "Start In" support; no elevation path; cwd is system-defined at login | Never for this project — Task Scheduler is the correct mechanism |
| Use `--onefile` PyInstaller build | Single distributable file | AV quarantine risk; slow startup; complex multiprocessing temp-path issues | Never for this project — `--onedir` is strictly better for single-user desktop tools |
| Relative path `"config.json"` in frozen exe | Works in development | Config not found when launched from Task Scheduler or non-project-root directory | Never in production — use `_exe_dir()` pattern from v1.1 onward |
| Call `colorsys.hls_to_rgb()` at inline call sites with positional args | Saves a wrapper function | H-L-S vs H-S-L confusion causes silent wrong colors; impossible to catch without unit tests | Never — always use a named wrapper |
| Set new config key defaults to "sensible" values instead of exact prior hardcoded values | Easier to reason about | Visible color change on upgrade for users who never opened the settings panel | Never — always match the exact prior hardcoded value byte-for-byte |
| Read `config["bg_color"]` with bracket access | Slightly less typing | KeyError crash on any existing config.json that predates the key | Never — always use `.get()` with the exact default |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `multiprocessing.Queue` + `process.join()` | Calling `join()` before draining the queue | Always drain the queue (or call `cancel_join_thread()` on child) before `join()` |
| `QFileSystemWatcher` + atomic config save | Not re-adding the path after `fileChanged` fires | Check `watcher.files().contains(path)` in the slot; call `addPath()` if missing |
| WinRT `UserNotificationListener` | Calling `RequestAccessAsync()` from the notification widget subprocess | Call `RequestAccessAsync()` once from the host (Qt main thread); check `GetAccessStatus()` in the subprocess |
| `ClipCursor` + session events | Calling `ClipCursor()` only at startup | Re-apply on `WM_DISPLAYCHANGE`, `WTS_SESSION_UNLOCK`, and focus-gained events |
| PyQt6 window flags | Setting `WindowStaysOnTopHint` separately from `FramelessWindowHint`, or after `show()` | Set all flags in one call before `show()`; order: `FramelessWindowHint | WindowStaysOnTopHint | Tool` |
| `winrt` async in a subprocess | Calling WinRT coroutines with `asyncio.run()` on a thread that has no STA apartment | Initialize a dedicated asyncio loop in the notification widget thread; verify apartment type is compatible |
| Widget pushing large RGBA bytes via Queue | Sending a 1920x515 RGBA frame per second (1920×515×4 = ~3.8 MB/frame) | Widgets own small regions (e.g., 300x515); frame size is bounded by slot size, not full display. Validate slot dimensions keep per-frame payload under ~200 KB |
| PyInstaller + multiprocessing spawn | Missing `freeze_support()` or calling it after `set_start_method()` | `freeze_support()` first, then `set_start_method("spawn")`, inside `if __name__ == "__main__":` |
| PyInstaller + pywin32 | DLLs not found in frozen build | Use `collect_dynamic_libs("win32")` in `.spec`; verify `pywin32-ctypes` is installed in build env |
| PyInstaller + winrt namespace packages | Deferred imports not traced by static analysis | Move winrt imports to module level OR use `collect_submodules("winrt")` + `collect_dynamic_libs("winrt")` in `.spec` |
| Task Scheduler autostart + GUI | "Run whether user is logged on or not" makes window invisible | Always use "Run only when user is logged on" for any task that creates visible windows |
| Task Scheduler autostart + cwd | Relying on cwd being the project/exe directory | Set `Start In` in task AND use `_exe_dir()` pattern in code — belt-and-suspenders |
| `colorsys.hls_to_rgb` + CSS HSL convention | Passing saturation as second argument (HSL order) | Always use a wrapper that takes `(hue, saturation, lightness)` and calls `hls_to_rgb(h, l, s)` internally |
| `colorsys` + QSlider integer values | Passing QSlider int (0–359) directly to colorsys | Normalize at the boundary: `hue / 359.0` before passing to colorsys |
| `bg_color` hot-reload | New top-level config key not delivered to host window | Wire `after_reload` callback to call `window.apply_host_config(current_config)` |
| Widget transparent background + host fill | Widget still renders opaque background after BG-01 migration | Make widget background switch and host color fill atomic; test with widget stopped and running |
| `QColor.hslHueF()` for gray | Returns -1 for achromatic colors; breaks slider restore | Track hue separately; only update from `hslHueF()` when result is >= 0 |
| New `control_panel/color_picker.py` + PyInstaller | Deferred import misses the module | Import `ColorPickerWidget` at top of `main_window.py`; rebuild `.exe` and smoke test the tab |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-display repaint on every FrameData message | CPU usage climbs as more widgets are added; repaint jitter visible | Use `self.update(slot_rect)` (dirty rect) instead of `self.update()` (full repaint) | With 4+ widgets all updating at 1 Hz, full repaints add measurable CPU overhead on integrated graphics |
| Pickle overhead on large byte payloads | Each frame goes through pickle + unpickle; QueueDrainTimer shows latency creep | Keep widget slot dimensions small; use `bytes` directly (fast pickle protocol); consider `memoryview` for zero-copy | Breaks at ~1 MB per frame per widget; ~200 KB is safe for 4 widgets at 50 ms intervals |
| Queue drain iterating all queues even if idle | Minor CPU spin at 50 ms even when no widget has new data | Add per-widget `dirty` flag; skip `get_nowait()` loop if flag is clear | Becomes measurable at 8+ widgets; at 4 widgets it is negligible |
| `process.is_alive()` polling in a tight loop for crash detection | CPU overhead; timer interference | Check `is_alive()` inside the QueueDrainTimer tick (50 ms); do not create a separate polling loop | Not a scaling issue — a design issue |
| `--onefile` PyInstaller build temp-extraction delay | 2–10 second startup delay at every login | Use `--onedir`; no extraction step at runtime | Every launch — not a scale issue; a design issue |
| ColorPickerWidget `valueChanged` emitting per-pixel drag | Saves config on every slider tick; triggers full hot-reload on every drag tick | Debounce: only emit `colorChanged` and write config on `sliderReleased`, not `valueChanged` | Not a scale issue — a design issue; immediate at any usage |

---

## Windows-Specific Warnings

These issues are Windows-only and distinct from general Python pitfalls.

| Issue | Root Cause | Mitigation |
|-------|------------|------------|
| ClipCursor cleared on session lock/wake/UAC | Windows intentionally resets cursor clip on input desktop switch | Subscribe to WTS session notifications; re-apply on unlock/resume |
| Monitor enumeration order not guaranteed after reboot | Qt's `screens()` inserts primary screen first; others shift. Driver updates can reorder | Match by geometry (physical pixels + position), never by index |
| `setWindowFlags()` on visible window hides it | Native HWND must be recreated; Qt's behavior is documented but surprising | Set all flags before `show()`; never change flags on a live window |
| WM_DISPLAYCHANGE fires multiple times during reconnection | Display topology changes trigger one message per resolution step | Debounce re-apply logic with a 500 ms QTimer; do not re-apply on every individual message |
| ClipCursor requires `WINSTA_WRITEATTRIBUTES` | Required for interactive desktop access; normal user session has it; Windows service / non-interactive session does not | Ensure host runs as an interactive user process, never as a Windows service |
| pywinrt STA apartment requirement | WinRT COM calls require STA initialization; Python's default main thread is STA-compatible; subprocess threads may be MTA | Perform all WinRT access-grant calls from the host's main thread; do not call `RequestAccessAsync` from any subprocess |
| Task Scheduler Session 0 isolation | "Run whether user is logged on or not" on Win11 creates a non-interactive session where GUI windows are invisible | Use "Run only when user is logged on" for all GUI tasks |
| Registry Run key no cwd control | Windows launches Run key programs from system cwd, not exe dir | Use Task Scheduler with "Start In" field, and use `_exe_dir()` in code |
| pywin32 DLL path not registered in frozen app | pywin32 post-install registers DLL path in registry; frozen app has no such registration | Explicitly bundle pywin32 DLLs via `collect_dynamic_libs` in PyInstaller spec |
| Antivirus blocking `--onefile` temp extraction | Self-extracting to `%TEMP%` matches malware dropper heuristics | Use `--onedir` build; avoid `--onefile` for any app shipping native DLLs |

---

## "Looks Done But Isn't" Checklist

- [ ] **ClipCursor enforcement:** Works at startup — verify cursor cannot re-enter Display 3 after `Win+L` unlock and after sleep/wake resume.
- [ ] **Hot-reload:** First config save triggers reload correctly — verify second and third saves also trigger (QFileSystemWatcher re-add after atomic replace).
- [ ] **Always-on-top persistence:** Host window stays on top after a fullscreen application is launched, Alt+Tab'd away, and then closed.
- [ ] **Multiprocessing guard:** Verify no extra Python processes appear in Task Manager when host starts (spawn-bomb check).
- [ ] **Widget crash recovery:** Kill a widget process externally (Task Manager) — verify host detects exit via `is_alive()` in drain timer and respawns.
- [ ] **Shutdown clean exit:** Close host — verify all widget processes terminate within 5 seconds and do not remain in Task Manager as zombies.
- [ ] **Notification permission:** `GetAccessStatus()` returns `ALLOWED` before the notification widget is spawned; if not `ALLOWED`, widget pushes a "permission required" frame rather than silently showing empty.
- [ ] **DPI-correct placement:** Host window exactly fills Display 3 (no black strip, no overflow) on the target machine at its actual DPI setting.
- [ ] **Queue full resilience:** Pause the QueueDrainTimer for 5 seconds artificially while a widget runs — verify widget does not deadlock on `put()` (requires `block=False`).
- [ ] **PyInstaller freeze_support:** Built `.exe` spawns exactly the expected number of processes — no process explosion — verified immediately on first launch.
- [ ] **Config path in frozen exe:** Built `.exe` launched from Desktop (not project root) loads config.json successfully and all widgets appear.
- [ ] **console=False crash check:** Built `.exe` with `console=False` starts without crash — verify by checking for `AttributeError` related to `sys.stdout` in log file.
- [ ] **pywin32 DLLs bundled:** Built `.exe` calls `ClipCursor` and `WTSRegisterSessionNotification` successfully (win32api, win32ts accessible in frozen app).
- [ ] **winrt in frozen exe:** Notification widget subprocess starts and polls WinRT without `ModuleNotFoundError` — verified in built `.exe`.
- [ ] **Task Scheduler interactive session:** Autostart task uses "Run only when user is logged on" — verified by logging out and back in, confirming host window appears on Display 3.
- [ ] **Task Scheduler cwd:** `config.json` is found and loaded when host is launched by Task Scheduler (not manually launched from project directory).
- [ ] **Zero visual change on upgrade:** Load a v1.1 config.json (no new color keys) with the v1.2 host and control panel — bar must look identical to v1.1.
- [ ] **bg_color hot-reload:** Change `bg_color` in control panel, save — bar background updates immediately without restarting the host.
- [ ] **Widget transparent background:** After BG-01 migration, widget renders on transparent background — verify by stopping all widgets and confirming only the host bg_color is visible.
- [ ] **Invalid hex fallback:** Enter `"#gg0000"` in a color field, save — widget continues running (does not crash), shows fallback color.
- [ ] **ColorPickerWidget swatch updates:** Move hue slider — swatch color changes immediately with no repaint trigger needed.
- [ ] **Achromatic hue preservation:** In ColorPickerWidget: set hue to cyan, drag saturation to 0 (gray), drag saturation back up — hue returns to cyan, not to red.
- [ ] **HLS argument order unit test:** `hsl_to_rgb_wrapper(0.0, 1.0, 0.5)` returns `(255, 0, 0)` — pure red.
- [ ] **PyInstaller control panel smoke test after rebuild:** Open Pomodoro tab in built `.exe` — ColorPickerWidget appears; open Calendar tab — color pickers appear. No `ModuleNotFoundError`.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Spawn bomb (missing `if __name__ == "__main__"`) | LOW — code change | Add guard, kill all leaked Python processes, restart host |
| QFileSystemWatcher stopped watching | LOW — code change + test | Add re-add logic in `fileChanged` slot; smoke-test with two saves |
| Always-on-top lost at runtime | LOW — code change | Move all flag-setting before `show()`; validate with fullscreen app test |
| ClipCursor not re-applied after wake | MEDIUM — requires Win32 message subscription | Add `WTSRegisterSessionNotification` + WM handler; test by locking/unlocking manually |
| Queue deadlock at shutdown | MEDIUM — requires shutdown sequence change | Add drain-before-join loop; add `cancel_join_thread()` on child side |
| Widget process zombies after crash | MEDIUM — requires lifecycle changes | Add `is_alive()` check in drain timer; add `proc.join(timeout=1); proc.kill()` in stop path |
| WinRT permission dialog never appeared | HIGH — user must manually grant in Windows Settings | Document first-run setup step: Settings → System → Notifications → Notification access → enable for MonitorControl |
| DPI geometry wrong on target hardware | HIGH — requires device testing to diagnose | Switch window placement to use `physicalSize` × `devicePixelRatio`; use `showFullScreen()` instead of `resize()` |
| `freeze_support()` missing in frozen exe | LOW — one-line fix + rebuild | Add `multiprocessing.freeze_support()` as first call in `if __name__ == "__main__":` block; rebuild |
| Config not found in frozen exe (wrong cwd) | LOW — pattern fix + rebuild | Replace all relative config paths with `_exe_dir()`-anchored paths; rebuild and test from non-project-root location |
| `sys.stdout is None` crash in noconsole build | LOW — guard + rebuild | Add null guard for `sys.stdout`/`sys.stderr`; add file-based logging; rebuild with `console=False` |
| pywin32 DLLs missing in frozen exe | MEDIUM — spec file edit + rebuild | Add `collect_dynamic_libs("win32")` to spec; verify `pywin32-ctypes` installed; rebuild |
| winrt submodules missing in frozen exe | MEDIUM — spec file + possible code restructure | Add `collect_submodules("winrt")` + `collect_dynamic_libs("winrt")` to spec; move deferred imports to module level; rebuild |
| Task Scheduler window invisible (Session 0) | LOW — task reconfiguration | Delete and recreate task with "Run only when user is logged on"; test by actual logoff/login cycle |
| HLS argument order swap (colorsys) | LOW — code fix + unit test | Add wrapper function with correct HSL ordering; add unit test with known values; fix call sites |
| colorsys receives out-of-range QSlider int | LOW — add normalization | Add division at the boundary where slider values enter color math; add range assertions |
| Widget subprocess crashes on bad hex color | LOW — add safe fallback | Add `_safe_hex_color()` guard in `_apply_config()`; validate in control panel UI layer too |
| bg_color not updating on hot-reload | LOW — wire after_reload callback | Add `window.apply_host_config()` call in the `after_reload` lambda; test by changing bg_color and saving |
| Visible color change on upgrade (wrong defaults) | MEDIUM — requires audit + rebuild | Audit all hardcoded color values in existing code; reset defaults to exact matches; rebuild and test with v1.1 config |
| ColorPickerWidget module missing from frozen exe | LOW — import fix + rebuild | Move import to module level; rebuild control panel `.exe`; smoke test all tabs |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| `if __name__ == "__main__"` missing | Phase 1: ProcessManager scaffolding | Launch host; confirm expected process count in Task Manager |
| Window flags order / set-after-show | Phase 1: Host window | Confirm `WindowStaysOnTopHint` holds after Alt+Tab |
| DPI-scaled geometry wrong | Phase 1: Host window | Visually confirm window fills Display 3 with no gaps |
| ClipCursor reset on session events | Phase 1: ClipCursor implementation | Lock screen, unlock, verify cursor still blocked from Display 3 |
| Queue deadlock on join | Phase 1: ProcessManager (stop logic) | Stop a widget via config change; confirm no hang |
| QFileSystemWatcher stops after atomic save | Phase 2: Config hot-reload | Save config twice; confirm both trigger reload |
| WinRT permission must come from host thread | Phase 4: Notification widget | Run first-time setup; confirm OS dialog appears |
| Widget process zombies | Phase 1: ProcessManager crash recovery | Kill widget externally; confirm host respawns and old process is reaped |
| Large pixel payload performance | Phase 1: Dummy widget (baseline) | Measure queue latency with 300x515 RGBA payload at 20 Hz |
| `freeze_support()` missing / wrong order | v1.1 Phase 1: PyInstaller packaging | Launch built `.exe`; confirm process count in Task Manager is normal |
| Config relative path wrong in frozen exe | v1.1 Phase 1: PyInstaller packaging | Launch `.exe` from Desktop; confirm widgets load from config.json |
| `sys.stdout is None` noconsole crash | v1.1 Phase 1: PyInstaller packaging | Build with `console=False`; check log file for startup errors |
| pywin32 DLLs not bundled | v1.1 Phase 1: PyInstaller packaging | Verify ClipCursor and WTS registration work in frozen `.exe` |
| winrt submodules missing | v1.1 Phase 1: PyInstaller packaging | Verify notification widget polls WinRT successfully in frozen `.exe` |
| Task Scheduler Session 0 (invisible window) | v1.1 Phase 2: Autostart implementation | Full logoff/login cycle; confirm window appears on Display 3 |
| Task Scheduler cwd wrong | v1.1 Phase 2: Autostart implementation | Confirm config loads from Task Scheduler launch (not manual launch) |
| Registry Run key vs Task Scheduler choice | v1.1 Phase 2: Autostart implementation | Document in phase spec; use Task Scheduler exclusively |
| HLS argument order swap | v1.2 Phase 1: ColorPickerWidget | Unit test: `hsl_to_rgb(0.0, 1.0, 0.5)` == `(255, 0, 0)` |
| colorsys out-of-range QSlider int | v1.2 Phase 1: ColorPickerWidget | Unit test: slider value 0..359 normalized before colorsys call |
| Widget subprocess crashes on bad hex | v1.2 Phase 2: Pomodoro color integration | Enter invalid hex in control panel; confirm widget does not crash |
| bg_color ownership transfer — double fill | v1.2 Phase 1: Background migration | Stop all widgets; confirm bar shows host bg_color only |
| Transparent widget bleeds previous frame | v1.2 Phase 1: Background migration | Change bg_color; confirm no ghost artifacts at widget edges |
| Missing `bg_color` key on old config | v1.2 Phase 1: Background migration | Load v1.1 config.json; confirm host starts without KeyError |
| Wrong default colors cause visual change | v1.2 Phase 1: Background migration | Pixel-diff v1.2 default render vs v1.1 render; diff must be zero |
| bg_color not hot-reloaded | v1.2 Phase 1: Background migration | Change bg_color in control panel; confirm bar updates live |
| QColor achromatic hue -1 | v1.2 Phase 1: ColorPickerWidget | Round-trip gray through ColorPickerWidget; restore saturation; hue preserved |
| Swatch not repainted after slider change | v1.2 Phase 1: ColorPickerWidget | Move slider; verify swatch color changes without external repaint |
| Signal loop in two-way hex/slider binding | v1.2 Phase 1: ColorPickerWidget | Type hex value; confirm no recursion and sliders update once |
| ColorPickerWidget missing from frozen exe | v1.2 Phase 3: Control panel rebuild | Open Pomodoro/Calendar tabs in built `.exe`; confirm pickers render |

---

## Sources

**v1.0 Sources (HIGH confidence):**
- [Microsoft Learn — ClipCursor function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clipcursor) — WINSTA_WRITEATTRIBUTES requirement, NULL releases clip
- [Microsoft Learn — WM_DISPLAYCHANGE](https://learn.microsoft.com/en-us/windows/win32/gdi/wm-displaychange) — fired on resolution/topology change
- [Microsoft Learn — WM_WTSSESSION_CHANGE](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change) — session lock/unlock notification
- [Microsoft Learn — Notification Listener](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener) — RequestAccessAsync must be UI thread; GetAccessStatus for subsequent checks; silent fail on denied
- [Qt Docs — QFileSystemWatcher](https://doc.qt.io/qt-6/qfilesystemwatcher.html) — stops watching on rename/remove; recommended re-add pattern
- [Python Docs — multiprocessing Queue cancel_join_thread](https://docs.python.org/3/library/multiprocessing.html) — join deadlock warning, `cancel_join_thread` caveat, spawn/`__main__` guard requirement
- [Python Bug tracker #29797 — Queue deadlock](https://bugs.python.org/issue29797) — confirmed deadlock on full pipe
- [Python Bug tracker #41714 — Queue deadlock](https://bugs.python.org/issue41714) — background feeder thread blocked on full pipe
- [Qt Forum — FramelessWindowHint + showMaximized bug in Qt6 (Feb 2025)](https://forum.qt.io/topic/161170/framelesswindowhint-showmaximized-bug-in-qt6) — flags set after show cause duplicated state change events — MEDIUM confidence
- [Qt Docs — High DPI](https://doc.qt.io/qt-6/highdpi.html) — geometry() returns logical pixels; devicePixelRatio for physical conversion
- [Microsoft Learn — Positioning Objects on Multiple Display Monitors](https://learn.microsoft.com/en-us/windows/win32/gdi/positioning-objects-on-multiple-display-monitors) — virtual desktop coordinate model
- [Super Fast Python — multiprocessing spawn RuntimeError](https://superfastpython.com/multiprocessing-spawn-runtimeerror/) — `if __name__ == "__main__"` requirement

**v1.1 Sources (MEDIUM/HIGH confidence):**
- [PyInstaller Common Issues and Pitfalls — 6.19.0](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) — freeze_support requirement on all platforms; sys.stdout=None in windowed mode; SetDllDirectoryW inheritance — HIGH confidence
- [PyInstaller Recipe — Multiprocessing](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing) — freeze_support placement; worker subprocess detection — HIGH confidence
- [PyInstaller — Run-time Information](https://pyinstaller.org/en/stable/runtime-information.html) — sys._MEIPASS, sys.frozen, onefile temp dir location — HIGH confidence
- [CPython issue #140814 — freeze_support and set_start_method ordering](https://github.com/python/cpython/issues/140814) — set_start_method must precede freeze_support; RuntimeError on wrong order — HIGH confidence
- [PyInstaller issue #8543 — pywintypes import failure](https://github.com/pyinstaller/pyinstaller/issues/8543) — Could not import pywintypes or win32api — MEDIUM confidence
- [PyInstaller issue #4818 — win32api DLL load failed](https://github.com/pyinstaller/pyinstaller/issues/4818) — DLL load failed importing win32api; pywin32 system32 path not found — MEDIUM confidence
- [PyInstaller Changelog 6.9.0](https://pyinstaller.org/en/v6.9.0/CHANGES.html) — bootloader shared MEIPASS for same-exe worker spawns — HIGH confidence
- [PyInstaller issue #3692 — noconsole CMD window flash](https://github.com/pyinstaller/pyinstaller/issues/3692) — subprocess spawning under noconsole mode — MEDIUM confidence
- [Microsoft Learn — schtasks create](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create) — /SC ONLOGON, /RL HIGHEST, /RU parameter behavior — HIGH confidence
- [Microsoft Q&A — Task Scheduler Run whether user is logged on or not](https://learn.microsoft.com/en-us/answers/questions/2188387/task-scheduler-does-not-work-with-the-option-run-w) — non-interactive session, GUI invisible — HIGH confidence
- [Windows Forum — Show App UI at Logon with Task Scheduler](https://windowsforum.com/threads/show-app-ui-at-logon-with-windows-11-task-scheduler.392418/) — "Run only when user is logged on" required for visible windows — MEDIUM confidence
- [Microsoft Learn — Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys) — Run key behavior, no cwd control — HIGH confidence
- [pythonguis.com — Packaging PyQt6 applications with PyInstaller](https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/) — data files, console=False, hidden imports warnings — MEDIUM confidence
- [pyinstaller-hooks-contrib — PyPI](https://pypi.org/project/pyinstaller-hooks-contrib/) — community hooks status for pywin32 and other packages — MEDIUM confidence

**v1.2 Sources (HIGH/MEDIUM confidence):**
- [Python Docs — colorsys module](https://docs.python.org/3/library/colorsys.html) — HLS argument order `hls_to_rgb(h, l, s)`; all values 0.0–1.0; no input validation — HIGH confidence
- [Qt Docs — QColor::fromHslF](https://doc.qt.io/qt-6/qcolor.html#fromHslF) — hue -1 for achromatic colors; hue normalization for out-of-range values — HIGH confidence
- [Qt Docs — QColor](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QColor.html) — HSL vs HSV distinction; hslHueF() returns -1 for achromatic — HIGH confidence
- [Pillow Docs — ImageColor module](https://pillow.readthedocs.io/en/stable/reference/ImageColor.html) — getrgb() raises ValueError on invalid color string — HIGH confidence
- [Qt Docs — QWidget::update()](https://doc.qt.io/qt-6/qwidget.html#update) — schedule repaint; does not force immediate repaint; use instead of repaint() — HIGH confidence
- [Qt Forum — fillRect with transparency leaves artifacts](https://forum.qt.io/topic/115051/why-does-qpainter-fillrect-with-transparency-leave-artifacts) — CompositionMode_Source vs SourceOver behavior — MEDIUM confidence
- [Qt Docs — QAbstractSlider](https://doc.qt.io/qt-6/qabstractslider.html) — valueChanged emits during drag if tracking enabled; sliderReleased for end-of-drag — HIGH confidence
- [Qt Docs — QWidget painting](https://doc.qt.io/qt-6/qwidget.html#paintEvent) — paintEvent only called on update() or repaint(); does not auto-fire on data change — HIGH confidence

---

*Pitfalls research for: MonitorControl — Python/PyQt6 widget bar, Windows, 1920x515 dedicated display*
*v1.0 researched: 2026-03-26*
*v1.1 supplement researched: 2026-03-27 (PyInstaller packaging + Windows autostart)*
*v1.2 supplement researched: 2026-03-27 (configurable color system)*
