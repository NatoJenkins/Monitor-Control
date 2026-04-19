# Phase 4: Notification Interceptor - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Read Windows toast notifications from the Action Center via WinRT (`winrt-Windows.UI.Notifications.Management==3.2.1`), surface the most recent notification in the notification slot (x=1280, 640×515) with title/body/app name/timestamp, and auto-clear from the bar after a configurable timeout. Host requests WinRT permission from the Qt main thread before the widget subprocess is spawned. Notification pre-display suppression is confirmed out of scope — v1 surfaces toasts in the bar in addition to the system toast, not instead of it.

</domain>

<decisions>
## Implementation Decisions

### Dismiss / Auto-dismiss
- Auto-dismiss on a timer: bar clears to idle after 30 seconds (configurable), but the notification stays in the Windows Action Center — `RemoveNotification(id)` is NOT called on auto-dismiss
- Each new incoming notification resets the timer to a fresh 30 seconds
- No control panel "Dismiss" button — auto-dismiss is the only mechanism in v1
- Timeout is configurable in the control panel Notification tab (default 30s)

### Notification Card Layout
- Centered card: content centered both vertically and horizontally in the slot — consistent with Pomodoro and Calendar centering pattern
- Text hierarchy (top to bottom, all centered): **app name** (small, muted) → **title** (medium) → **body** (small) → **arrival timestamp** (small, muted)
- Long body text: wrap up to 3 lines, then truncate with `…`
- Idle state (no notifications): bell icon centered, no text — slot is visually identifiable as the notification area without any active notification

### Notification Metadata
- Display: app name, title, body, arrival timestamp (HH:MM) — no app icon
- App icon (WinRT `AppInfo.AppLogoUri`) is skipped for v1 — async URI fetch adds complexity and failure surface
- Timestamp: arrival time from WinRT `UserNotification.CreationTime`, formatted HH:MM, shown in small muted color

### Control Panel — Notification Tab
- **Auto-dismiss timeout**: spinbox (seconds), default 30, range configurable by Claude
- **Font selector**: same three-option dropdown as Pomodoro/Calendar (Inter, Digital-7, Share Tech Mono)
- **App blocklist**: QListWidget with Add (+) and Remove (-) buttons; each blocked app name is a separate list entry; blocking is by display app name string match
- Blocklist model: **blocklist (opt-out)** — all apps shown by default; user adds apps to block (e.g. "Microsoft Edge", "Windows Update")
- Blocked app names stored in `config.json` under notification widget settings as a list

### config.json Extensions
Phase 4 adds a notification widget entry:
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

### WinRT Spike (Plan 04-01 — before full widget build)
The spike must validate before the widget is built:
1. `asyncio.run()` with a WinRT coroutine works from a `multiprocessing.Process(spawn)` subprocess
2. `GetAccessStatus()` returns ALLOWED in the subprocess after `RequestAccessAsync()` ran in the host Qt main thread
3. Polling vs `NotificationChanged` event subscription — determine which is more reliable in a spawn subprocess context

### Claude's Discretion
- Exact font sizes for app name / title / body / timestamp layers
- Bell icon implementation (Pillow draw or bundled SVG rasterized)
- Tick interval for polling `GetNotificationsAsync()` (if polling wins over events in spike)
- Spinner/loading frame during `asyncio` initialization in the subprocess
- Test strategy for WinRT async spike

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 4 requirements
- `.planning/REQUIREMENTS.md` §Notification Interceptor — NOTF-01 through NOTF-05; the exact acceptance criteria this phase must satisfy
- `.planning/ROADMAP.md` §Phase 4 — spike requirements, plan breakdown (04-01 spike, 04-02 full widget), success criteria

### Widget contract and IPC
- `widgets/base.py` — WidgetBase ABC: `run()`, `out_queue`, `in_queue`, `poll_config_update()`; notification widget extends this
- `widgets/dummy/widget.py` — Reference frame-push loop (block=False, queue.Full guard)
- `shared/message_schema.py` — FrameData, ConfigUpdateMessage; add nothing new here for Phase 4 (no ControlSignal needed — no inbound commands from host to notification widget in v1)

### Host integration
- `host/main.py` — `register_widget_type` calls and QFileSystemWatcher command watcher setup; add `register_widget_type("notification", run_notification_widget)` here
- `host/config_loader.py` — WIDGET_REGISTRY, reconcile logic; new widget type registered before ConfigLoader construction

### Control panel extension
- `control_panel/main_window.py` — Existing tab structure; add Notification tab alongside Pomodoro and Calendar tabs
- `control_panel/config_io.py` — `atomic_write_config` pattern; sole config writer

### WinRT package
- `requirements.txt` (or equivalent) — must pin `winrt-Windows.UI.Notifications.Management==3.2.1` and `winrt-runtime==3.2.1`; `winsdk` package must NOT be present (archived October 2024)

### Key architectural constraints
- Widget processes MUST NOT import PyQt6 — Pillow is the off-screen renderer
- All `queue.put()` calls MUST be `block=False` with `queue.Full` guard
- `RequestAccessAsync()` MUST be called from the Qt main thread (host), never from the widget subprocess — subprocess calls `GetAccessStatus()` only
- If `GetAccessStatus()` is not ALLOWED, widget pushes a "permission required" placeholder frame (NOTF-02)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WidgetBase` (`widgets/base.py`): notification widget extends this; provides `widget_id`, `config`, `out_queue`, `in_queue`, `poll_config_update()`
- `FrameData` (`shared/message_schema.py`): the push format — no changes needed
- `ConfigUpdateMessage` (`shared/message_schema.py`): used for font/timeout/blocklist config updates to running widget
- `atomic_write_config` (`control_panel/config_io.py`): use for all config writes from the Notification tab
- Bundled TTF fonts (`widgets/pomodoro/` or `widgets/calendar/`): Inter, Digital-7, Share Tech Mono already available — reference same font paths

### Established Patterns
- Frame push loop: `while True: put(block=False) / except queue.Full: pass / time.sleep(interval)` — match DummyWidget/Pomodoro/Calendar pattern
- Config update handling: `poll_config_update()` in the run loop → apply new config dict (font, timeout, blocklist) on return
- Widget registration: `register_widget_type("notification", run_notification_widget)` called in `host/main.py` before ConfigLoader
- Subprocess entry point: module-level `run_notification_widget(widget_id, config, out_q, in_q)` function
- Permission request: `RequestAccessAsync()` in `host/main.py` before `config_loader.apply_config()` (Qt main thread only)

### Integration Points
- `host/main.py`: add `register_widget_type("notification", ...)` call; add `UserNotificationListener.RequestAccessAsync()` call before widget startup
- `config.json`: add notification widget entry at `x=1280` (slot already reserved from Phase 3)
- `control_panel/main_window.py`: add Notification tab with timeout spinbox, font selector, blocklist QListWidget

</code_context>

<specifics>
## Specific Ideas

- Centered card layout consistent with Pomodoro/Calendar — same centering math already established in Pillow rendering
- Bell icon for idle state — simple, immediately communicates "this is the notifications area"
- Blocklist via QListWidget + Add/Remove buttons — same widget pattern as a "list config" surface; more explicit than a comma-separated field

</specifics>

<deferred>
## Deferred Ideas

- Notification pre-display suppression — confirmed impossible via any supported Windows API; explicitly out of scope in REQUIREMENTS.md
- Multiple simultaneous toasts (scrollable queue) — tracked as PLSH-03 (v2)
- Explicit "Dismiss from bar" control — not needed since auto-dismiss handles it; could be added in v1.x if user wants manual control
- App allowlist mode (opt-in) — deferred; blocklist (opt-out) covers most use cases without setup friction

</deferred>

---

*Phase: 04-notification-interceptor*
*Context gathered: 2026-03-26*
