# Roadmap: MonitorControl

## Overview

MonitorControl is built in four phases that match the natural dependency chain of its architecture. Phase 1 establishes the host process, the IPC pipeline, and cursor lockout — all five BLOCKER-severity pitfalls live here and must be verified on real hardware before widget development begins. Phase 2 adds the config system and control panel, creating the configuration surface that all widgets depend on. Phase 3 builds the two simpler widgets (Pomodoro and Calendar) to validate the WidgetBase/Pillow/queue pipeline with real content before tackling the hardest integration. Phase 4 delivers the notification interceptor, which requires a dedicated WinRT spike and host-side permission grant before the full widget can be built. The result is a fully operational 1920x515 utility bar that widgets can be added to without modifying host code.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Host Infrastructure + Pipeline** - Host window, cursor lockout, IPC, ProcessManager, dummy widget end-to-end (completed 2026-03-26)
- [ ] **Phase 2: Config System + Control Panel** - config.json schema, hot-reload watcher, control panel process
- [ ] **Phase 3: Pomodoro + Calendar Widgets** - Both real widgets validate the WidgetBase/Pillow/queue pipeline
- [ ] **Phase 4: Notification Interceptor** - WinRT spike, host permission grant, notification widget

## Phase Details

### Phase 1: Host Infrastructure + Pipeline
**Goal**: A stable, verified host process owns Display 3 with cursor lockout enforced; a dummy widget proves the full IPC and render pipeline works on real hardware
**Depends on**: Nothing (first phase)
**Requirements**: HOST-01, HOST-02, HOST-03, HOST-04, HOST-05, IPC-01, IPC-02, IPC-03, IPC-04

**Research risks addressed in this phase:**
- BLOCKER: Window flags must be set before `show()` — all flags in a single call; validated by alt-tab and fullscreen-app tests
- BLOCKER: `if __name__ == "__main__":` guard required — validated by checking process count in Task Manager on startup
- BLOCKER: Queue `put()` + `process.join()` deadlock — drain-before-join pattern required in `ProcessManager.stop_widget()`; validated by stopping a widget via config and confirming no hang
- HIGH: `ClipCursor()` reset on session lock/sleep/wake — WTS session notifications and WM_DISPLAYCHANGE handler required; validated by Win+L unlock and sleep/wake cycle
- HIGH: `QScreen.geometry()` returns logical pixels — Display 3 identified by physical pixels (`logical × devicePixelRatio`); `showFullScreen()` used for placement; validated visually on target hardware

**Success Criteria** (what must be TRUE):
  1. Host window fills Display 3 exactly (no black strip, no overflow onto adjacent monitors) and no host window entry appears in the Windows taskbar
  2. The dummy widget's colored rectangle is visible in its assigned slot on Display 3, updating at the drain timer interval, with no flicker or tearing
  3. The cursor cannot enter Display 3 after startup, after Win+L unlock, and after waking from sleep
  4. Stopping the dummy widget via a config stub causes no hang in `process.join()`; starting the host with no guard produces no extra Python processes in Task Manager
  5. Killing the dummy widget process externally (Task Manager) is detected by the drain timer within one drain cycle; the host does not crash

**Plans**: 3 plans

Plans:
- [x] 01-01-PLAN.md — Host window, display targeting, window flags, DPI-correct placement, project skeleton + test infrastructure
- [x] 01-02-PLAN.md — ClipCursor enforcement with WTS session notification recovery
- [x] 01-03-PLAN.md — ProcessManager, QueueDrainTimer, Compositor, dummy widget end-to-end + hardware verification

### Phase 2: Config System + Control Panel
**Goal**: `config.json` is the single source of truth for layout and widget settings; the host watches it reliably across atomic saves; the control panel is the only configuration surface
**Depends on**: Phase 1
**Requirements**: CFG-01, CFG-02, CFG-03, CTRL-01, CTRL-02, CTRL-03

**Research risks addressed in this phase:**
- HIGH: `QFileSystemWatcher` stops watching after atomic file replace — re-add path in `fileChanged` slot; debounce with 100 ms `QTimer.singleShot`; validated by saving config twice and confirming both trigger reload

**Success Criteria** (what must be TRUE):
  1. Saving config.json from the control panel triggers a hot-reload in the host; saving it a second time also triggers a reload (the QFileSystemWatcher re-add is working)
  2. Adding a widget to config causes the host to spawn a new widget process without restarting; removing a widget causes the process to stop cleanly
  3. Changing per-widget settings in the control panel delivers a CONFIG_UPDATE to the running widget process without killing and respawning it
  4. The control panel is the sole writer of config.json; the host never writes to it; no file corruption occurs when both processes are running

**Plans**: TBD

Plans:
- [ ] 02-01: config.json schema, ConfigLoader, QFileSystemWatcher with re-add and debounce
- [ ] 02-02: Control panel QMainWindow, atomic config write, layout and per-widget config forms

### Phase 3: Pomodoro + Calendar Widgets
**Goal**: Two real, useful widgets are running in the bar, validating the full WidgetBase/Pillow/queue/compositor pipeline with actual content before the hardest integration
**Depends on**: Phase 2
**Requirements**: POMO-01, POMO-02, POMO-03, POMO-04, POMO-05, CAL-01, CAL-02, CAL-03

**Research risks addressed in this phase:**
- Confirmed: Widget processes must not import PyQt6 — Pillow is the off-screen renderer; crashes on Windows spawn with a Qt context in the subprocess
- Confirmed: All widget `queue.put()` calls must be `block=False` with `queue.Full` guard; no blocking puts in steady state

**Success Criteria** (what must be TRUE):
  1. Pomodoro displays the current phase label and a MM:SS countdown that advances every second; it auto-transitions from Work to Short Break to Long Break following the configured cycle count
  2. Pomodoro start, pause, and reset commands issued from the control panel are reflected in the bar display within one drain cycle (~50 ms)
  3. Changing Pomodoro durations in the control panel takes effect on the next phase transition without restarting the widget process
  4. Calendar displays the correct day of week, full date, and time in the configured 12h or 24h format, updating each second
  5. Neither widget crashes the host when killed externally; no PyQt6 import errors appear in widget subprocess logs

**Plans**: TBD

Plans:
- [ ] 03-01: WidgetBase contract, Pillow rendering pipeline, Pomodoro state machine and display
- [ ] 03-02: Calendar widget, clock format config, bidirectional queue control signals

### Phase 4: Notification Interceptor
**Goal**: Windows toast notifications are read from the Action Center, surfaced in the notification slot with title/body/app name, and dismissible from the bar
**Depends on**: Phase 3
**Requirements**: NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05

**Research risks addressed in this phase:**
- HIGH: `RequestAccessAsync` must run from the host's Qt main thread, not the widget subprocess — the subprocess has no STA apartment; a silent failure (no dialog, no error) results if called from the subprocess
- MEDIUM: WinRT async in a subprocess is the least-validated area — a standalone spike is required before the full widget build to confirm: (1) `GetAccessStatus()` reliably reflects host-granted permission in a fresh subprocess; (2) asyncio loop behavior in a spawn subprocess is compatible with WinRT calls; (3) polling vs `NotificationChanged` event subscription reliability
- Confirmed out of scope: Notification pre-display suppression — v1 surfaces toasts in the bar *in addition to* the system toast; suppression is not achievable via any supported Windows API

**Spike required before full build:**
Before building the complete notification widget, validate in a standalone script:
- `asyncio.run()` with a WinRT coroutine works from a `multiprocessing.Process(spawn)` subprocess
- `GetAccessStatus()` returns ALLOWED in the subprocess after `RequestAccessAsync()` is called in the host
- Determine whether polling `GetNotificationsAsync()` on a timer or subscribing to `NotificationChanged` is more reliable in a subprocess context

**Success Criteria** (what must be TRUE):
  1. On first run, a Windows notification access permission dialog appears (confirming `RequestAccessAsync` ran from the host main thread, not the subprocess)
  2. When another app sends a Windows toast, the notification title, body, and app name appear in the notification slot on Display 3 within a few seconds
  3. Clicking the dismiss control on the notification slot removes the notification from the Windows Action Center
  4. When notification access is denied, the notification slot shows a "permission required" placeholder instead of a blank or crashing slot
  5. The `winsdk` package is not installed; all WinRT calls use `winrt-Windows.UI.Notifications.Management==3.2.1` and `winrt-runtime==3.2.1` pinned to the same minor version

**Plans**: TBD

Plans:
- [ ] 04-01: WinRT spike — standalone subprocess asyncio/STA validation; GetAccessStatus and polling vs event subscription
- [ ] 04-02: Host-side RequestAccessAsync one-time setup; notification widget subprocess with GetAccessStatus check, polling loop, FrameData push, dismiss action

---

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Host Infrastructure + Pipeline | 3/3 | Complete   | 2026-03-27 |
| 2. Config System + Control Panel | 0/2 | Not started | - |
| 3. Pomodoro + Calendar Widgets | 0/2 | Not started | - |
| 4. Notification Interceptor | 0/2 | Not started | - |

---
*Roadmap created: 2026-03-26*
*Last updated: 2026-03-26 after Phase 1 complete (all 3 plans hardware-verified)*
