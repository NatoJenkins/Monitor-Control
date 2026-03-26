# Pitfalls Research

**Domain:** Python/PyQt6 desktop widget bar — Windows, borderless always-on-top window, multiprocessing IPC, Win32 APIs
**Researched:** 2026-03-26
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

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Full-display repaint on every FrameData message | CPU usage climbs as more widgets are added; repaint jitter visible | Use `self.update(slot_rect)` (dirty rect) instead of `self.update()` (full repaint) | With 4+ widgets all updating at 1 Hz, full repaints add measurable CPU overhead on integrated graphics |
| Pickle overhead on large byte payloads | Each frame goes through pickle + unpickle; QueueDrainTimer shows latency creep | Keep widget slot dimensions small; use `bytes` directly (fast pickle protocol); consider `memoryview` for zero-copy | Breaks at ~1 MB per frame per widget; ~200 KB is safe for 4 widgets at 50 ms intervals |
| Queue drain iterating all queues even if idle | Minor CPU spin at 50 ms even when no widget has new data | Add per-widget `dirty` flag; skip `get_nowait()` loop if flag is clear | Becomes measurable at 8+ widgets; at 4 widgets it is negligible |
| `process.is_alive()` polling in a tight loop for crash detection | CPU overhead; timer interference | Check `is_alive()` inside the QueueDrainTimer tick (50 ms); do not create a separate polling loop | Not a scaling issue — a design issue |

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

---

## Sources

- [Microsoft Learn — ClipCursor function](https://learn.microsoft.com/en-us/windows/win32/api/winuser/nf-winuser-clipcursor) — WINSTA_WRITEATTRIBUTES requirement, NULL releases clip — HIGH confidence
- [Microsoft Learn — WM_DISPLAYCHANGE](https://learn.microsoft.com/en-us/windows/win32/gdi/wm-displaychange) — fired on resolution/topology change — HIGH confidence
- [Microsoft Learn — WM_WTSSESSION_CHANGE](https://learn.microsoft.com/en-us/windows/win32/termserv/wm-wtssession-change) — session lock/unlock notification — HIGH confidence
- [Microsoft Learn — Notification Listener](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener) — RequestAccessAsync must be UI thread; GetAccessStatus for subsequent checks; silent fail on denied — HIGH confidence
- [Qt Docs — QFileSystemWatcher](https://doc.qt.io/qt-6/qfilesystemwatcher.html) — stops watching on rename/remove; recommended re-add pattern — HIGH confidence
- [Python Docs — multiprocessing Queue cancel_join_thread](https://docs.python.org/3/library/multiprocessing.html) — join deadlock warning, `cancel_join_thread` caveat, spawn/`__main__` guard requirement — HIGH confidence
- [Python Bug tracker #29797 — Queue deadlock](https://bugs.python.org/issue29797) — confirmed deadlock on full pipe — HIGH confidence
- [Python Bug tracker #41714 — Queue deadlock](https://bugs.python.org/issue41714) — background feeder thread blocked on full pipe — HIGH confidence
- [Qt Forum — FramelessWindowHint + showMaximized bug in Qt6 (Feb 2025)](https://forum.qt.io/topic/161170/framelesswindowhint-showmaximized-bug-in-qt6) — flags set after show cause duplicated state change events — MEDIUM confidence
- [Qt Forum — Additional windows not opening on correct monitor](https://forum.qt.io/topic/140827/additional-windows-not-opening-on-correct-monitor) — screen enumeration and placement issues — MEDIUM confidence
- [Qt Docs — High DPI](https://doc.qt.io/qt-6/highdpi.html) — geometry() returns logical pixels; devicePixelRatio for physical conversion — HIGH confidence
- [Microsoft Learn — Positioning Objects on Multiple Display Monitors](https://learn.microsoft.com/en-us/windows/win32/gdi/positioning-objects-on-multiple-display-monitors) — virtual desktop coordinate model — HIGH confidence
- [pythonspeed.com — Why your multiprocessing Pool is stuck](https://pythonspeed.com/articles/python-multiprocessing/) — spawn, pipe buffer, zombie causes — MEDIUM confidence
- [pywinrt — python-winsdk issue #16](https://github.com/pywinrt/python-winsdk/issues/16) — NotificationChanged listener error in subprocesses — MEDIUM confidence
- [Super Fast Python — multiprocessing spawn RuntimeError](https://superfastpython.com/multiprocessing-spawn-runtimeerror/) — `if __name__ == "__main__"` requirement — HIGH confidence
- [pythonforthelab.com — Differences between multiprocessing on Windows and Linux](https://pythonforthelab.com/blog/differences-between-multiprocessing-windows-and-linux/) — spawn vs fork behavior on Windows — MEDIUM confidence

---
*Pitfalls research for: MonitorControl — Python/PyQt6 widget bar, Windows, 1920x515 dedicated display*
*Researched: 2026-03-26*
