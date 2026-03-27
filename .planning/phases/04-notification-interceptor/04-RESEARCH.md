# Phase 4: Notification Interceptor - Research

**Researched:** 2026-03-26
**Domain:** WinRT UserNotificationListener, Python asyncio/subprocess integration, Pillow rendering, PyQt6 control panel extension
**Confidence:** MEDIUM — WinRT async/subprocess behavior requires the mandatory spike to confirm; polling API and permission model are HIGH confidence from official docs

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Dismiss / Auto-dismiss**
- Auto-dismiss on a timer: bar clears to idle after 30 seconds (configurable), but the notification stays in the Windows Action Center — `RemoveNotification(id)` is NOT called on auto-dismiss
- Each new incoming notification resets the timer to a fresh 30 seconds
- No control panel "Dismiss" button — auto-dismiss is the only mechanism in v1
- Timeout is configurable in the control panel Notification tab (default 30s)

**Notification Card Layout**
- Centered card: content centered both vertically and horizontally in the slot — consistent with Pomodoro and Calendar centering pattern
- Text hierarchy (top to bottom, all centered): app name (small, muted) → title (medium) → body (small) → arrival timestamp (small, muted)
- Long body text: wrap up to 3 lines, then truncate with `…`
- Idle state (no notifications): bell icon centered, no text — slot is visually identifiable as the notification area without any active notification

**Notification Metadata**
- Display: app name, title, body, arrival timestamp (HH:MM) — no app icon
- App icon (WinRT `AppInfo.AppLogoUri`) is skipped for v1 — async URI fetch adds complexity and failure surface
- Timestamp: arrival time from WinRT `UserNotification.CreationTime`, formatted HH:MM, shown in small muted color

**Control Panel — Notification Tab**
- Auto-dismiss timeout: spinbox (seconds), default 30, range configurable by Claude
- Font selector: same three-option dropdown as Pomodoro/Calendar (Inter, Digital-7, Share Tech Mono)
- App blocklist: QListWidget with Add (+) and Remove (-) buttons; each blocked app name is a separate list entry; blocking is by display app name string match
- Blocklist model: blocklist (opt-out) — all apps shown by default; user adds apps to block
- Blocked app names stored in `config.json` under notification widget settings as a list

**config.json Extension**
```json
{
  "id": "notification",
  "type": "notification",
  "x": 1280,
  "y": 0,
  "width": 640,
  "height": 515,
  "settings": {
    "font": "Inter",
    "auto_dismiss_seconds": 30,
    "blocked_apps": []
  }
}
```

**WinRT Spike (Plan 04-01 — before full widget build)**
1. `asyncio.run()` with a WinRT coroutine works from a `multiprocessing.Process(spawn)` subprocess
2. `GetAccessStatus()` returns ALLOWED in the subprocess after `RequestAccessAsync()` ran in the host Qt main thread
3. Polling vs `NotificationChanged` event subscription — determine which is more reliable in a spawn subprocess context

### Claude's Discretion
- Exact font sizes for app name / title / body / timestamp layers
- Bell icon implementation (Pillow draw or bundled SVG rasterized)
- Tick interval for polling `GetNotificationsAsync()` (if polling wins over events in spike)
- Spinner/loading frame during `asyncio` initialization in the subprocess
- Test strategy for WinRT async spike

### Deferred Ideas (OUT OF SCOPE)
- Notification pre-display suppression — confirmed impossible via any supported Windows API; explicitly out of scope
- Multiple simultaneous toasts (scrollable queue) — tracked as PLSH-03 (v2)
- Explicit "Dismiss from bar" control — not needed since auto-dismiss handles it
- App allowlist mode (opt-in) — deferred; blocklist (opt-out) covers most use cases
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| NOTF-01 | Host calls `UserNotificationListener.RequestAccessAsync()` from Qt main thread before spawning notification widget | STA/UI-thread requirement confirmed by Microsoft docs; Python asyncio.run() pattern from pywinrt README; must precede `config_loader.apply_config()` in host/main.py |
| NOTF-02 | Widget subprocess calls only `GetAccessStatus()` (never `RequestAccessAsync()`); pushes "permission required" placeholder frame if not ALLOWED | `GetAccessStatus()` is synchronous (no await needed); status enum values confirmed: ALLOWED / DENIED / UNSPECIFIED; placeholder frame follows existing FrameData push pattern |
| NOTF-03 | Widget polls/subscribes via `winrt-Windows.UI.Notifications.Management==3.2.1`; surfaces title, body, app name | Package confirmed current at 3.2.1 (released June 2025); polling `GetNotificationsAsync()` is the reliable path; event subscription has known failures in non-Store Python; spike validates subprocess compatibility |
| NOTF-04 | Dismiss calls `RemoveNotification(id)` removing from Action Center | Synchronous method; confirmed in official API docs; CONTEXT.md clarifies auto-dismiss does NOT call RemoveNotification — this requirement maps to a future dismiss path if added, but CONTEXT.md says no dismiss button in v1. See note below. |
| NOTF-05 | Most recent notification shown; idle state when none; one notification at a time (v1) | Polling returns full list; widget tracks current notification ID to detect changes; idle = bell icon |

**NOTF-04 note:** CONTEXT.md states "No control panel 'Dismiss' button — auto-dismiss is the only mechanism in v1" and auto-dismiss does NOT call `RemoveNotification`. However REQUIREMENTS.md NOTF-04 says "User can dismiss a notification from the bar slot; dismissal calls RemoveNotification(id)." The planner must reconcile this conflict: CONTEXT.md supersedes the original requirement text for v1. The implementation should provide the dismiss capability via auto-dismiss only; `RemoveNotification` is available but not wired in v1.
</phase_requirements>

---

## Summary

Phase 4 adds Windows toast notification reading to the bar. The core integration uses `winrt-Windows.UI.Notifications.Management==3.2.1` (the current modular pywinrt package, released June 2025) to access `UserNotificationListener`. The critical architectural constraint is that `RequestAccessAsync()` must run from the Qt main thread in the host before the widget subprocess is spawned — the subprocess may not have the STA apartment context required for that call.

The notification widget itself follows the established WidgetBase/Pillow pattern (no PyQt6 imports, non-blocking queue puts, ConfigUpdateMessage hot-reload). The widget polls `GetNotificationsAsync(NotificationKinds.TOAST)` on a timer to fetch the latest notification, renders it as a centered four-layer card (app name → title → body → timestamp), and auto-dismisses by clearing the display after a configurable timeout.

The most significant open risk is the subprocess asyncio/WinRT compatibility: a dedicated spike (plan 04-01) must confirm that `asyncio.run()` works in a spawned subprocess and that `GetAccessStatus()` reliably sees the permission granted by the host. Community reports indicate event subscription (`add_notification_changed`) has reliability issues on non-Microsoft-Store Python installations; polling `GetNotificationsAsync()` is the safer primary strategy.

**Primary recommendation:** Complete the spike first (plan 04-01). If `asyncio.run()` in a spawn subprocess works and `GetAccessStatus()` reflects host-granted permission, proceed with polling at a 2-second interval. Use the established CalendarWidget pattern as the structural template for the notification widget.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| winrt-Windows.UI.Notifications.Management | 3.2.1 | WinRT UserNotificationListener API | Confirmed locked by CONTEXT.md; modular replacement for archived winsdk |
| winrt-runtime | 3.2.1 | WinRT async coroutine support, IAsyncOperation bridging | Required peer dependency; must pin to same minor version |
| Pillow | (existing) | Off-screen RGBA rendering in widget subprocess | Established pattern from Pomodoro/Calendar; no PyQt6 in widget |
| asyncio (stdlib) | Python 3.9+ | Runs WinRT async coroutines | Built-in; `asyncio.run()` is the entry point for each poll cycle |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyQt6 | 6.10.2 | Host-side `RequestAccessAsync()` call + control panel Notification tab | Host main.py and control_panel only; never in widget subprocess |
| multiprocessing (stdlib) | — | Spawn subprocess entry point | Existing IPC infrastructure; no changes needed |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Polling `GetNotificationsAsync()` | `NotificationChanged` event | Event subscription has documented reliability issues on non-Store Python; polling at 2s interval is simpler and battle-tested |
| `asyncio.run()` per poll cycle | Persistent async event loop in subprocess thread | Persistent loop complicates subprocess shutdown; asyncio.run() is self-contained per invocation and handles cleanup automatically |
| Pillow bell icon drawn programmatically | Bundled SVG rasterized via cairosvg | cairosvg adds a heavy C dependency; Pillow polygon draw is simpler and already in-process |

**Installation (additions to requirements.txt):**
```bash
pip install "winrt-Windows.UI.Notifications.Management==3.2.1" "winrt-runtime==3.2.1"
```

**Version verification (confirmed 2026-03-26):**
- `winrt-Windows.UI.Notifications.Management`: latest is 3.2.1 (released June 6, 2025) — matches pinned version
- `winrt-runtime`: 3.2.1 — must pin to exact same minor as the namespace package

---

## Architecture Patterns

### Recommended Project Structure
```
widgets/
└── notification/
    ├── __init__.py
    ├── widget.py           # NotificationWidget(WidgetBase) + run_notification_widget()
    └── fonts/              # symlink or copy from calendar/fonts/ — same three TTFs
tests/
├── test_notification_widget.py    # unit tests (spike results inform what to test)
└── spike_winrt_subprocess.py      # 04-01 standalone validation script (not a pytest test)
```

### Pattern 1: Host-Side RequestAccessAsync (NOTF-01)
**What:** `RequestAccessAsync()` called in `host/main.py` before `config_loader.apply_config()`, from the Qt main thread. Uses `asyncio.run()` to await the coroutine.
**When to use:** Once at startup, before any widget subprocess is spawned.
**Example:**
```python
# host/main.py — after Qt event filter setup, before config_loader.apply_config()
# Source: Microsoft Docs — UserNotificationListener.RequestAccessAsync
import asyncio
from winrt.windows.ui.notifications.management import (
    UserNotificationListener,
    UserNotificationListenerAccessStatus,
)

async def _request_notification_access():
    listener = UserNotificationListener.current
    status = await listener.request_access_async()
    return status

status = asyncio.run(_request_notification_access())
if status == UserNotificationListenerAccessStatus.ALLOWED:
    print("[Host] Notification access granted", flush=True)
elif status == UserNotificationListenerAccessStatus.DENIED:
    print("[Host] Notification access denied — widget will show placeholder", flush=True)
# UNSPECIFIED = user dismissed dialog; will be asked again next run
```
**Critical:** This must run in the Qt main thread. `asyncio.run()` blocks until the coroutine completes. The Qt event loop has not yet started (this runs before `app.exec()`), so blocking here is safe.

### Pattern 2: Widget Subprocess Poll Loop (NOTF-02, NOTF-03, NOTF-05)
**What:** Subprocess calls `GetAccessStatus()` (synchronous) first. If ALLOWED, polls `GetNotificationsAsync()` with `asyncio.run()` on a timer.
**When to use:** Steady-state widget run loop.
**Example:**
```python
# widgets/notification/widget.py
# Source: Microsoft Docs — UserNotificationListener, pywinrt README patterns
import asyncio
from winrt.windows.ui.notifications.management import (
    UserNotificationListener,
    UserNotificationListenerAccessStatus,
)
from winrt.windows.ui.notifications import NotificationKinds, KnownNotificationBindings

async def _fetch_notifications():
    listener = UserNotificationListener.current
    return await listener.get_notifications_async(NotificationKinds.TOAST)

def get_latest_notification():
    """Returns (app_name, title, body, creation_time) or None."""
    listener = UserNotificationListener.current
    status = listener.get_access_status()
    if status != UserNotificationListenerAccessStatus.ALLOWED:
        return None  # widget renders placeholder

    notifs = asyncio.run(_fetch_notifications())
    if not notifs:
        return None

    # Most recent by CreationTime
    notif = max(notifs, key=lambda n: n.creation_time)
    app_name = notif.app_info.display_info.display_name if notif.app_info else "Unknown"
    title, body = "", ""
    binding = notif.notification.visual.get_binding(KnownNotificationBindings.TOAST_GENERIC)
    if binding:
        elements = binding.get_text_elements()
        if elements:
            title = elements[0].text if len(elements) > 0 else ""
            body = " ".join(e.text for e in elements[1:]) if len(elements) > 1 else ""
    return app_name, title, body, notif.creation_time
```

### Pattern 3: Permission-Required Placeholder Frame (NOTF-02)
**What:** If `GetAccessStatus()` returns anything other than ALLOWED, push a static placeholder frame rather than silently showing an empty slot.
**Example:**
```python
def _render_permission_placeholder(self) -> FrameData:
    W, H = self._width, self._height
    img = Image.new("RGBA", (W, H), self._bg_color)
    draw = ImageDraw.Draw(img)
    font = _load_font(self._font_name, 20)
    msg = "Notification access required"
    sub = "Open Settings > Notifications > Allow apps"
    # Centered stacked text — same math as CalendarWidget
    ...
    return FrameData(widget_id=self.widget_id, width=W, height=H, rgba_bytes=img.tobytes())
```

### Pattern 4: Auto-Dismiss Timer
**What:** Widget tracks `_current_notif_id` and `_display_since`. On each poll, if a new notification arrives, reset `_display_since = time.monotonic()`. If elapsed > `auto_dismiss_seconds`, clear to idle.
**Why:** Pure Python timer, no WinRT involvement, no subprocess complexity.
```python
# Pseudocode — in the run loop
elapsed = time.monotonic() - self._display_since
if elapsed > self._auto_dismiss_seconds:
    self._current_notif = None  # revert to idle/bell frame
```

### Pattern 5: Blocklist Filtering
**What:** After fetching notifications, filter out any notification where `app_name` is in `self._blocked_apps`.
```python
def _is_blocked(self, app_name: str) -> bool:
    return app_name in self._blocked_apps  # exact string match
```
Config update delivers the new blocked_apps list via `ConfigUpdateMessage`; widget applies it immediately.

### Recommended Centering Math for Notification Card (NOTF-05)
```python
# Four-layer stacked vertical centering — identical math to CalendarWidget
layers = [
    (app_name_str, font_small, muted_color),
    (title_str,    font_medium, text_color),
    (body_str,     font_small,  text_color),
    (timestamp_str, font_small, muted_color),
]
gap = 10
total_h = sum(draw.textbbox((0,0), t, font=f)[3] for t, f, _ in layers) + gap * (len(layers)-1)
start_y = (H - total_h) // 2
# Draw each layer, advancing y by text height + gap
```

### Anti-Patterns to Avoid
- **Import PyQt6 in widget subprocess:** Widget subprocess has no Qt context. Import will fail on Windows spawn. Check confirmed by `test_no_pyqt6_import` pattern used in Calendar/Pomodoro tests.
- **Call RequestAccessAsync from widget subprocess:** STA apartment requirement — silent failure, no dialog, no error. Confirmed in Microsoft docs: "must be called from a UI-thread." The Qt main thread is the only valid callsite.
- **block=True in queue.put():** Deadlocks when host queue is full. Follow `block=False` / `except queue.Full: pass` pattern throughout.
- **Calling asyncio.run() inside an already-running event loop:** Only use at top level. Do not nest inside a coroutine. The widget subprocess has no ambient event loop before asyncio.run() is called, so this is safe.
- **Using `UserNotificationListener.get_current()`:** The old python-winsdk API. The 3.2.1 modular package uses `UserNotificationListener.current` (a static property). Verify in spike.
- **add_notification_changed() for event subscription:** Known reliability failure on python.org-installed Python (non-Store). "Element not found" WinError. Use polling instead.
- **Omitting winrt-runtime from requirements.txt:** The namespace package requires the runtime peer. Silent import errors if missing.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| WinRT notification access | Custom COM/ctypes implementation | `winrt-Windows.UI.Notifications.Management==3.2.1` | The COM interop for WinRT is ~thousands of lines; the modular winrt package handles all marshalling, apartment threading, and async bridging |
| Async WinRT method calls | Custom threading + ctypes event loop | `asyncio.run()` + `await` on WinRT IAsyncOperation | pywinrt implements IAsyncOperation as Python awaitables; asyncio.run() is the correct entry point |
| App name resolution | Parsing process names or registry | `notif.app_info.display_info.display_name` | WinRT provides the display name via the notification's AppInfo; registry parsing is fragile and locale-dependent |
| Notification text extraction | XML string parsing | `KnownNotificationBindings.TOAST_GENERIC` + `get_text_elements()` | WinRT binding API handles adaptive notification schemas; raw XML parsing breaks on edge-case templates |
| Timestamp formatting | `time.strftime` on epoch | `notif.creation_time` (`DateTimeOffset`) formatted as `HH:MM` | `creation_time` is the WinRT arrival time; already in local time; just format it |

**Key insight:** The WinRT Python projection handles all COM threading, apartment initialization, and async operation bridging. The only non-negotiable is calling `RequestAccessAsync()` from a thread that has a message pump (Qt main thread).

---

## Common Pitfalls

### Pitfall 1: RequestAccessAsync from Subprocess
**What goes wrong:** Calling `RequestAccessAsync()` in the widget subprocess silently fails — no dialog appears, no error raised, and `GetAccessStatus()` returns UNSPECIFIED or DENIED.
**Why it happens:** `RequestAccessAsync()` requires a STA/UI-thread apartment. The spawn subprocess creates a fresh Python process with no Windows message pump and no COM apartment initialized by Qt.
**How to avoid:** Only call `RequestAccessAsync()` in `host/main.py` before `config_loader.apply_config()`. Subprocess calls only `GetAccessStatus()`.
**Warning signs:** No permission dialog on first run; notification slot stays blank or shows placeholder permanently.

### Pitfall 2: NotificationChanged Event Subscription Failures
**What goes wrong:** `listener.add_notification_changed(handler)` raises `OSError: [WinError -2147023728] Element not found`.
**Why it happens:** Known issue in the pywinrt package on Python installed from python.org (vs Microsoft Store). The underlying COM event infrastructure differs.
**How to avoid:** Use polling (`get_notifications_async()` on a timer) as the primary strategy. The spike (04-01) must validate this explicitly. If the project environment uses python.org Python, polling is mandatory.
**Warning signs:** WinError -2147023728 on `add_notification_changed` call.

### Pitfall 3: asyncio.run() in Spawn Subprocess
**What goes wrong:** asyncio.run() on Windows in a spawn subprocess uses ProactorEventLoop by default. This must be confirmed to work with WinRT IAsyncOperation awaitables.
**Why it happens:** WinRT async operations are implemented as `IAsyncOperation` COM objects that pywinrt wraps as Python awaitables. The exact integration with ProactorEventLoop in a subprocess is minimally documented.
**How to avoid:** Validate in the 04-01 spike with the exact subprocess structure (multiprocessing.Process, spawn method, asyncio.run with a WinRT coroutine).
**Warning signs:** `RuntimeError: This event loop is already running` or silent hang on await.

### Pitfall 4: Stale Notification Display
**What goes wrong:** Widget keeps showing a notification that was already dismissed from Action Center, because the notification was removed but the widget's cached ID still references it.
**Why it happens:** Polling fetches current Action Center contents. If a notification is dismissed from Action Center externally, the next poll will return an empty list or a different notification.
**How to avoid:** On each poll, compare the returned notification list against `_current_notif_id`. If the current ID is no longer in the list, revert to idle state immediately (before the auto-dismiss timer fires).
**Warning signs:** Bell icon never returns after a notification is dismissed from the Action Center manually.

### Pitfall 5: Body Text Overflow
**What goes wrong:** Long notification bodies overflow the card height and push other layers out of the slot.
**Why it happens:** Some apps send multi-paragraph notifications. Pillow `textlength` doesn't wrap automatically.
**How to avoid:** Use `ImageDraw.textbbox()` for width measurement. Implement manual word-wrap: split body into words, accumulate lines until width exceeds slot width, stop after 3 lines and append `…`. The CalendarWidget textbbox centering math is the template.
**Warning signs:** Text runs off the bottom of the slot.

### Pitfall 6: winrt-runtime Version Mismatch
**What goes wrong:** Import errors like `ImportError: cannot import name 'IAsyncOperation' from 'winrt.runtime'` if winrt-runtime is at a different minor version than the namespace package.
**Why it happens:** Modular winrt packages are tightly version-coupled; 3.2.x namespace packages require winrt-runtime==3.2.x.
**How to avoid:** Pin both to `==3.2.1` in requirements.txt. Add a test that imports both at module level to catch this early.
**Warning signs:** Import errors on first run of spike.

### Pitfall 7: winsdk Package Presence
**What goes wrong:** `winsdk` and `winrt-*` packages conflict or shadow each other's module names.
**Why it happens:** `winsdk` (archived October 2024) used the same `winrt` namespace. Both installed simultaneously creates import ambiguity.
**How to avoid:** Never install `winsdk`. Add a test that checks `winsdk` is not importable (or not in the package list). REQUIREMENTS.md explicitly prohibits it.
**Warning signs:** `ModuleNotFoundError` with a different traceback than expected, or unexpected API shapes.

---

## Code Examples

Verified patterns from official sources:

### UserNotificationListener Access Status Values
```python
# Source: Microsoft Docs — UserNotificationListenerAccessStatus
# https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.management.usernotificationlisteneraccessstatus
from winrt.windows.ui.notifications.management import UserNotificationListenerAccessStatus

# Three possible values:
# UserNotificationListenerAccessStatus.ALLOWED   — user granted access
# UserNotificationListenerAccessStatus.DENIED    — user denied; further RequestAccessAsync calls instant-deny
# UserNotificationListenerAccessStatus.UNSPECIFIED — user dismissed dialog; next call re-prompts
```

### Extracting Text from a UserNotification
```python
# Source: Microsoft Docs — Notification listener guide
# https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener
from winrt.windows.ui.notifications import KnownNotificationBindings

binding = notif.notification.visual.get_binding(KnownNotificationBindings.TOAST_GENERIC)
if binding is not None:
    elements = binding.get_text_elements()
    title = elements[0].text if len(elements) > 0 else ""
    body_parts = [e.text for e in elements[1:] if e.text]
    body = " ".join(body_parts)
app_name = notif.app_info.display_info.display_name
creation_time = notif.creation_time  # DateTimeOffset; .to_datetime() or format directly
```

### RemoveNotification
```python
# Source: Microsoft Docs — UserNotificationListener.RemoveNotification
# Synchronous — no await needed
# Note: In v1, auto-dismiss does NOT call this; Action Center entry is kept.
# This is available for future use if an explicit dismiss is added.
listener = UserNotificationListener.current
listener.remove_notification(notif_id)  # Python naming: snake_case
```

### Pillow Bell Icon (Idle State — Claude's Discretion)
```python
# Draw a simple bell shape using polygon — no external dependency
# This is the recommended approach given no SVG rasterizer is in the stack
def _draw_bell_icon(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, color: tuple):
    # Bell body: rounded trapezoid approximated with polygon
    # Bell clapper: small circle below center
    # Implementation details are Claude's discretion
    pass
```

### Notification Widget config.json Entry
```json
{
  "id": "notification",
  "type": "notification",
  "x": 1280,
  "y": 0,
  "width": 640,
  "height": 515,
  "settings": {
    "font": "Inter",
    "auto_dismiss_seconds": 30,
    "blocked_apps": []
  }
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `winsdk` monolithic package | Modular `winrt-*` packages | October 2024 (winsdk archived) | Must use modular packages; winsdk is abandoned and not pip-installable from a live index |
| `UserNotificationListener.get_current()` | `UserNotificationListener.current` (property) | pywinrt 3.x | Old call pattern from python-winsdk 2.x; use property accessor in 3.2.1 |
| Event subscription via `add_notification_changed()` | Polling `get_notifications_async()` | Reliability issue discovered ~2024 | Non-Store Python installations cannot reliably subscribe to events; polling is the resilient pattern |
| Background task registration for notifications | Foreground polling loop in subprocess | N/A for non-UWP Python apps | Python apps are not UWP packages; background task infrastructure is not available; foreground polling is correct |

**Deprecated/outdated:**
- `winsdk` package: archived October 2024; do not install; `winrt-Windows.UI.Notifications.Management==3.2.1` is the direct replacement
- `UserNotificationListener.get_current()`: old python-winsdk method; use `UserNotificationListener.current` in 3.x

---

## Open Questions

1. **asyncio.run() compatibility in spawn subprocess**
   - What we know: asyncio.run() creates a ProactorEventLoop on Windows; WinRT IAsyncOperation objects are wrapped as Python awaitables by pywinrt
   - What's unclear: Whether the ProactorEventLoop in a fresh spawn subprocess correctly initializes the WinRT apartment threading required for UserNotificationListener
   - Recommendation: Spike 04-01 resolves this definitively. If it fails, fallback is to use `winrt.system.initialize_with_window()` or a Thread with an explicit STA apartment via ctypes (complex; avoid if polling works).

2. **GetAccessStatus() visibility from subprocess**
   - What we know: Microsoft docs confirm the permission is user-level, not process-level; it persists across app restarts
   - What's unclear: Whether `GetAccessStatus()` in a fresh spawn subprocess reliably reads the permission granted by a different process (`host/main.py`)
   - Recommendation: Spike 04-01 validates this. Expected to work (permission is per-user system state), but must be confirmed.

3. **NOTF-04 vs CONTEXT.md conflict on dismiss**
   - What we know: REQUIREMENTS.md NOTF-04 says dismiss calls `RemoveNotification(id)`; CONTEXT.md says no dismiss button in v1 and auto-dismiss does NOT call RemoveNotification
   - What's unclear: Is this a spec conflict or is NOTF-04 describing a future path?
   - Recommendation: CONTEXT.md is the authoritative v1 spec. Planner should implement auto-dismiss only; `RemoveNotification` is not called in v1. NOTF-04 acceptance can be marked "deferred to v1.x" or the planner should surface this conflict to the user.

4. **creation_time Python type from WinRT DateTimeOffset**
   - What we know: `UserNotification.creation_time` is a WinRT `DateTimeOffset` type; pywinrt projects it as a Python object
   - What's unclear: Whether it has a `.to_datetime()` method or is directly a `datetime.datetime`; the exact conversion needed for `HH:MM` formatting
   - Recommendation: Spike 04-01 should print `type(notif.creation_time)` and available methods. Fallback: use `str(notif.creation_time)` and parse.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 (currently 89 tests collected) |
| Config file | `pytest.ini` — `testpaths = tests` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| NOTF-01 | `RequestAccessAsync` is called from host, not from widget subprocess | unit (source check) | `python -m pytest tests/test_notification_widget.py::test_no_request_access_async_in_widget -x` | Wave 0 |
| NOTF-01 | Widget source does not import PyQt6 | unit (AST check) | `python -m pytest tests/test_notification_widget.py::test_no_pyqt6_import -x` | Wave 0 |
| NOTF-02 | Widget calls `GetAccessStatus()` before fetching; renders placeholder if not ALLOWED | unit (mock WinRT) | `python -m pytest tests/test_notification_widget.py::test_permission_placeholder_when_denied -x` | Wave 0 |
| NOTF-02 | Placeholder frame has correct dimensions and non-zero content | unit | `python -m pytest tests/test_notification_widget.py::test_placeholder_frame_dimensions -x` | Wave 0 |
| NOTF-03 | Widget surfaces title, body, app name from mocked notification | unit (mock WinRT) | `python -m pytest tests/test_notification_widget.py::test_renders_notification_content -x` | Wave 0 |
| NOTF-03 | Widget renders idle bell frame when no notifications | unit | `python -m pytest tests/test_notification_widget.py::test_idle_state_frame -x` | Wave 0 |
| NOTF-04 | `RemoveNotification` not called on auto-dismiss (v1 spec) | unit | `python -m pytest tests/test_notification_widget.py::test_auto_dismiss_does_not_remove_from_action_center -x` | Wave 0 |
| NOTF-05 | Shows most recent notification (highest creation_time) | unit | `python -m pytest tests/test_notification_widget.py::test_most_recent_notification_selected -x` | Wave 0 |
| NOTF-05 | Auto-dismiss timer clears to idle after `auto_dismiss_seconds` | unit | `python -m pytest tests/test_notification_widget.py::test_auto_dismiss_timer -x` | Wave 0 |
| NOTF-05 | New notification resets dismiss timer | unit | `python -m pytest tests/test_notification_widget.py::test_new_notification_resets_timer -x` | Wave 0 |
| NOTF-05 | Blocklist filters app by name | unit | `python -m pytest tests/test_notification_widget.py::test_blocklist_filters_app -x` | Wave 0 |
| NOTF-03 | Config update (font, timeout, blocklist) applied via ConfigUpdateMessage | unit | `python -m pytest tests/test_notification_widget.py::test_config_update_applied -x` | Wave 0 |
| All | All puts use block=False | unit (AST check) | `python -m pytest tests/test_notification_widget.py::test_nonblocking_put -x` | Wave 0 |
| NOTF-01 | Spike: asyncio.run() works in spawn subprocess with WinRT | manual (spike script) | `python spike_winrt_subprocess.py` | Wave 0 (spike plan 04-01) |

**Note on WinRT mocking:** WinRT API calls must be mocked in unit tests because the test runner may not have notification permission and tests must be runnable without Display 3. Use `unittest.mock.patch` to replace `UserNotificationListener.current` and the async return values. This is the same approach used for win32 mocking in existing tests.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_notification_widget.py` — covers all NOTF-0x requirements above
- [ ] `spike_winrt_subprocess.py` — standalone spike script (not a pytest file; validates asyncio/WinRT/subprocess combo before plan 04-02)
- [ ] `widgets/notification/__init__.py` — empty module init
- [ ] `widgets/notification/widget.py` — NotificationWidget class
- [ ] `widgets/notification/fonts/` — copy or symlink Inter-Regular.ttf and ShareTechMono-Regular.ttf from calendar/fonts/
- [ ] requirements.txt additions: `winrt-Windows.UI.Notifications.Management==3.2.1` and `winrt-runtime==3.2.1`

---

## Sources

### Primary (HIGH confidence)
- [Microsoft Docs — UserNotificationListener Class](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.management.usernotificationlistener?view=winrt-26100) — full API surface (methods, properties, events), threading model, permission states
- [Microsoft Docs — Notification listener guide](https://learn.microsoft.com/en-us/windows/apps/develop/notifications/app-notifications/notification-listener) — end-to-end C# patterns adapted for Python; confirmed RequestAccessAsync/GetAccessStatus semantics, text element extraction, RemoveNotification
- [PyPI — winrt-Windows.UI.Notifications.Management](https://pypi.org/project/winrt-Windows.UI.Notifications.Management/) — confirmed version 3.2.1 (released June 6, 2025), Python 3.9+ requirement, Windows-only

### Secondary (MEDIUM confidence)
- [pywinrt/pywinrt GitHub README](https://github.com/pywinrt/pywinrt) — asyncio.run() pattern, `from winrt.<namespace> import ClassName` import structure, async method naming conventions (snake_case), event handler threading pattern
- [pywinrt/python-winsdk Issue #16](https://github.com/pywinrt/python-winsdk/issues/16) — confirmed `add_notification_changed()` failure on python.org Python; workaround is polling; `UserNotificationListener.current` (property not method) confirmed for 3.x

### Tertiary (LOW confidence — needs spike validation)
- [copyprogramming.com/howto/python-how-to-get-window-notification-with-python] — working code snippet `listener = UserNotificationListener.get_current()` / `await listener.get_notifications_async(NotificationKinds.TOAST)` (note: `get_current()` may be old 2.x API; validate in spike)
- [cx_Freeze issue #2785](https://github.com/marcelotduarte/cx_Freeze/issues/2785) — `add_notification_changed` WinError -2147023728 also manifests on non-Store python.org Python when running as a frozen app; confirms polling preference
- [shawenyao.com Stack Overflow LED article](https://www.shawenyao.com/Stack-Overflow-The-LED/) — confirmed polling pattern as the practical approach for reading notifications in Python

---

## Metadata

**Confidence breakdown:**
- Standard stack (winrt-* packages): HIGH — PyPI page confirms 3.2.1, June 2025; Microsoft docs confirm API surface; package is the locked choice from CONTEXT.md
- Permission model (RequestAccessAsync/GetAccessStatus semantics): HIGH — directly from Microsoft docs; status enum values confirmed
- asyncio/subprocess compatibility: LOW — no authoritative source confirms this combination; the spike exists specifically because it is unvalidated
- NotificationChanged event reliability: MEDIUM — multiple community sources confirm failure on python.org Python; polling is confirmed working by same sources
- API naming (property vs method `current`, snake_case method names): MEDIUM — pywinrt issue thread confirms `.current` property in 3.x; spike must verify exact names
- Architecture patterns (widget structure, font reuse, centering math): HIGH — directly mirrors CalendarWidget which is hardware-verified

**Research date:** 2026-03-26
**Valid until:** 2026-06-26 (stable WinRT docs) / 2026-04-26 (pywinrt 3.2.x — fast-moving package ecosystem)
