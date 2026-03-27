# Pitfalls Research

**Domain:** Python/PyQt6 desktop widget bar — Windows, borderless always-on-top window, multiprocessing IPC, Win32 APIs
**Researched:** 2026-03-26 (v1.0) | 2026-03-27 (v1.1 supplement: PyInstaller + autostart)
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

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-display repaint on every FrameData message | CPU usage climbs as more widgets are added; repaint jitter visible | Use `self.update(slot_rect)` (dirty rect) instead of `self.update()` (full repaint) | With 4+ widgets all updating at 1 Hz, full repaints add measurable CPU overhead on integrated graphics |
| Pickle overhead on large byte payloads | Each frame goes through pickle + unpickle; QueueDrainTimer shows latency creep | Keep widget slot dimensions small; use `bytes` directly (fast pickle protocol); consider `memoryview` for zero-copy | Breaks at ~1 MB per frame per widget; ~200 KB is safe for 4 widgets at 50 ms intervals |
| Queue drain iterating all queues even if idle | Minor CPU spin at 50 ms even when no widget has new data | Add per-widget `dirty` flag; skip `get_nowait()` loop if flag is clear | Becomes measurable at 8+ widgets; at 4 widgets it is negligible |
| `process.is_alive()` polling in a tight loop for crash detection | CPU overhead; timer interference | Check `is_alive()` inside the QueueDrainTimer tick (50 ms); do not create a separate polling loop | Not a scaling issue — a design issue |
| `--onefile` PyInstaller build temp-extraction delay | 2–10 second startup delay at every login | Use `--onedir`; no extraction step at runtime | Every launch — not a scale issue; a design issue |

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

---

*Pitfalls research for: MonitorControl — Python/PyQt6 widget bar, Windows, 1920x515 dedicated display*
*v1.0 researched: 2026-03-26*
*v1.1 supplement researched: 2026-03-27 (PyInstaller packaging + Windows autostart)*
