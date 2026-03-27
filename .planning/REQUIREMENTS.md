# Requirements: MonitorControl

**Defined:** 2026-03-26
**Core Value:** Keep productivity tooling off the primary monitors — widgets run persistently in a dedicated display the cursor cannot enter, requiring zero window management from the user.

## v1 Requirements

Requirements for initial release. Each maps to exactly one roadmap phase.

### Host Window

- [x] **HOST-01**: Host app claims Display 3 as a borderless, always-on-top PyQt6 window at 1920x515, identified by physical pixel dimensions (not screen index), positioned at the correct virtual desktop origin
- [x] **HOST-02**: Host window flags (FramelessWindowHint, WindowStaysOnTopHint, Tool) are set in a single call before `show()` so the window never appears in the taskbar and stays on top after Alt+Tab and after a fullscreen app launches
- [x] **HOST-03**: Host composites widget slots via QPainter in a single `paintEvent`; no per-widget top-level windows exist; rendering is flicker-free with no visible tearing
- [x] **HOST-04**: Windows `ClipCursor()` is applied at startup to block the cursor from entering Display 3, and is automatically re-applied after session lock/unlock, sleep/wake, and WM_DISPLAYCHANGE events
- [x] **HOST-05**: All host entry points are guarded with `if __name__ == "__main__":` so no recursive subprocess spawning occurs on Windows spawn start method

### IPC Pipeline

- [x] **IPC-01**: Widget subprocesses push frame data to the host exclusively via `multiprocessing.Queue` using non-blocking `put(block=False)`; they never import PyQt6
- [x] **IPC-02**: A `QueueDrainTimer` fires every 50 ms in the Qt main thread, draining all widget queues via `get_nowait()`, without blocking the event loop
- [x] **IPC-03**: `ProcessManager` spawns, monitors, and terminates widget processes; it drains each widget's queue fully before calling `process.join()` on stop, with a `proc.kill()` fallback after a 5-second timeout
- [x] **IPC-04**: A dummy widget (static colored rectangle pushed via queue) validates the complete host pipeline end-to-end before any real widget is built

### Config System

- [x] **CFG-01**: `config.json` defines the display layout (slot names, geometries) and per-widget settings; it is the single source of truth read by the host on startup
- [x] **CFG-02**: `QFileSystemWatcher` monitors `config.json`; after each `fileChanged` event the path is re-added to the watcher (to survive atomic file replacement) and the reload is debounced by 100 ms
- [x] **CFG-03**: Config hot-reload diffs old vs new config and reconciles running widgets (stop removed, start added, send CONFIG_UPDATE to changed) without restarting the host process or tearing down the bar window

### Control Panel

- [x] **CTRL-01**: A separate PyQt6 `QMainWindow` process provides the only user-facing configuration surface (cursor lockout makes in-bar interaction impossible)
- [x] **CTRL-02**: The control panel reads and writes `config.json` atomically (write to temp file, then `os.replace`) and is the sole writer of that file
- [x] **CTRL-03**: The control panel exposes widget layout configuration and per-widget settings (Pomodoro durations, clock format); changes are saved to config.json and picked up by the host's file watcher

### Pomodoro Widget

- [x] **POMO-01**: Pomodoro widget runs as an isolated subprocess implementing `WidgetBase`; it renders to RGBA bytes via Pillow and pushes `FrameData` to the host queue
- [x] **POMO-02**: Pomodoro implements a full state machine: IDLE → WORK → SHORT_BREAK → LONG_BREAK → WORK, with auto-advance at countdown zero and cycle counting for long-break promotion
- [x] **POMO-03**: Pomodoro displays the current phase label (Focus / Short Break / Long Break) and a MM:SS countdown, updated every second
- [x] **POMO-04**: Pomodoro responds to control signals (start, pause, reset) sent from the host/control panel via a second inbound queue
- [x] **POMO-05**: Work duration, short break duration, long break duration, and cycles-before-long-break are all configurable via `config.json` and applied on CONFIG_UPDATE without restarting the widget process

### Calendar Widget

- [x] **CAL-01**: Calendar widget runs as an isolated subprocess implementing `WidgetBase`; it renders the current local time and date to RGBA bytes via Pillow and pushes `FrameData` at a 1-second interval
- [x] **CAL-02**: Calendar displays day of week, full date (locale-aware format), and time in either 12h or 24h format as configured in `config.json`
- [x] **CAL-03**: Clock format (12h/24h) is configurable via the control panel and applied on CONFIG_UPDATE without restarting the widget process

### Notification Interceptor

- [x] **NOTF-01**: Before spawning the notification widget, the host calls `UserNotificationListener.RequestAccessAsync()` from the Qt main thread (the only STA-compatible thread) to obtain user consent for notification access
- [x] **NOTF-02**: The notification widget subprocess calls only `GetAccessStatus()` (never `RequestAccessAsync()`); if status is not ALLOWED it pushes a "permission required" placeholder frame instead of silently showing an empty slot
- [x] **NOTF-03**: The notification widget polls or subscribes to `UserNotificationListener` using the modular `winrt-Windows.UI.Notifications.Management==3.2.1` package (not the archived `winsdk`); it surfaces notification title, body, and app name in the bar slot
- [x] **NOTF-04**: Auto-dismiss to idle bell icon after configurable timeout (default 30s); v1 does NOT call RemoveNotification — bar clears to idle, Action Center entry remains (per CONTEXT.md locked decision)
- [x] **NOTF-05**: The notification widget displays the most recent notification; when no notifications are present the slot shows an idle bell icon; v1 shows one notification at a time (queue of multiple toasts is a v1.x feature)

---

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Polish and Quality of Life

- **PLSH-01**: Pomodoro plays an audio cue (short WAV/OGG bundled with the widget) at each phase transition
- **PLSH-02**: When a widget process dies unexpectedly, the host detects the crash via `is_alive()` polling in the drain timer and renders a visual "crashed" placeholder in the slot; the control panel exposes a restart button for the crashed widget
- **PLSH-03**: Notification widget shows a scrollable queue of multiple simultaneous toasts (not just the most recent)
- **PLSH-04**: Calendar widget has a configurable seconds display toggle (default off to avoid unnecessary repaints)

### Extended Widgets

- **EXT-01**: System resource widgets (CPU, RAM, GPU usage) — high polling cost; deferred until plugin framework is proven stable in daily use
- **EXT-02**: Configurable display selection (not hardcoded to Display 3) — simplification deferred until v1 display logic is validated
- **EXT-03**: Additional widget types (weather, media player control, notes)

---

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Notification pre-display suppression | No supported Windows API exists to intercept a third-party app's toast before display; `SuppressPopup` is sender-side only. v1 shows toasts in the bar *in addition to* the system toast, not instead of it. Confirmed by Microsoft docs. |
| External calendar integration (Google, Outlook, ICS) | OAuth flows, token refresh, rate limits, and network dependency are large scope; explicitly deferred in PROJECT.md; date/time display only for v1 |
| In-bar widget configuration UI | ClipCursor() prevents the cursor from entering Display 3; any in-bar interaction is architecturally impossible; all config goes through the control panel |
| Live drag-and-drop widget layout | Cursor cannot enter Display 3; layout is defined in config.json and edited via the control panel |
| Per-widget top-level Qt windows | Causes Z-order collisions and defeats the unified compositing model; widgets push RGBA data, the host renders everything |
| GPU-accelerated compositing | Standard QPainter is sufficient at 1920x515; adding OpenGL/Vulkan compositing has no user-facing benefit at this resolution |
| Widget sandboxing beyond process boundaries | OS-level sandboxing (AppContainer, seccomp) adds major complexity with no payoff for a single-user local tool; process isolation already provides crash containment |
| Non-Windows platforms | ClipCursor(), WTS session notifications, WinRT notification APIs, and multi-monitor assumptions are all Windows-specific; cross-platform support requires rearchitecting core subsystems |
| winsdk package | Archived October 2024; do not use; replacement is the modular winrt-* packages at 3.2.1 |

---

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| HOST-01 | Phase 1 | Complete |
| HOST-02 | Phase 1 | Complete |
| HOST-03 | Phase 1 | Complete |
| HOST-04 | Phase 1 | Complete |
| HOST-05 | Phase 1 | Complete |
| IPC-01 | Phase 1 | Complete |
| IPC-02 | Phase 1 | Complete |
| IPC-03 | Phase 1 | Complete |
| IPC-04 | Phase 1 | Complete |
| CFG-01 | Phase 2 | Complete |
| CFG-02 | Phase 2 | Complete |
| CFG-03 | Phase 2 | Complete |
| CTRL-01 | Phase 2 | Complete |
| CTRL-02 | Phase 2 | Complete |
| CTRL-03 | Phase 2 | Complete |
| POMO-01 | Phase 3 | Complete |
| POMO-02 | Phase 3 | Complete |
| POMO-03 | Phase 3 | Complete |
| POMO-04 | Phase 3 | Complete |
| POMO-05 | Phase 3 | Complete |
| CAL-01 | Phase 3 | Complete |
| CAL-02 | Phase 3 | Complete |
| CAL-03 | Phase 3 | Complete |
| NOTF-01 | Phase 4 | Complete |
| NOTF-02 | Phase 4 | Complete |
| NOTF-03 | Phase 4 | Complete |
| NOTF-04 | Phase 4 | Complete |
| NOTF-05 | Phase 4 | Complete |

**Coverage:**
- v1 requirements: 28 total
- Mapped to phases: 28
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-26*
*Last updated: 2026-03-26 after initial definition*
