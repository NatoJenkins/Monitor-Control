# MonitorControl

## Current Milestone: v1.1 Startup & Distribution

**Goal:** Make MonitorControl feel like finished software — autostart on login and a distributable control panel .exe.

**Target features:**
- Host configurable to start automatically on Windows login (no terminal required)
- Control panel packaged as standalone .exe (no Python environment required)

## What This Is

A modular widget framework that drives a dedicated 1920×515 secondary display (Display 3, positioned below two primary monitors) as a persistent utility bar. A host Python/PyQt6 app owns the display as a borderless always-on-top window, compositing rendered output from individual widget subprocesses that communicate via multiprocessing queues. A separate PyQt6 control panel manages widget layout and per-widget configuration via a config.json the host hot-reloads. v1.0 ships with Pomodoro timer, Calendar/Clock, and Windows notification interceptor widgets.

## Core Value

Keep productivity tooling off the primary monitors — widgets run persistently in a dedicated display the cursor cannot enter, requiring zero window management from the user.

## Requirements

### Validated

- ✓ Host app claims Display 3 as a borderless always-on-top PyQt6 window at 1920×515 — v1.0 (HOST-01..03)
- ✓ Windows ClipCursor() prevents the cursor from entering Display 3; re-applied on session unlock, sleep/wake, WM_DISPLAYCHANGE, and WM_ACTIVATEAPP — v1.0 (HOST-04)
- ✓ Widget processes communicate with host via multiprocessing queues (non-blocking put; drain timer in Qt main thread) — v1.0 (IPC-01..03)
- ✓ Dummy widget validates the full host pipeline end-to-end before any real widget — v1.0 (IPC-04)
- ✓ config.json is the single source of truth; QFileSystemWatcher hot-reload with atomic-replace re-add and 100ms debounce — v1.0 (CFG-01..02)
- ✓ Hot-reload reconciles running widgets (stop/start/CONFIG_UPDATE) without restarting the host — v1.0 (CFG-03)
- ✓ PyQt6 control panel reads/writes config.json atomically; sole writer; sole configuration surface — v1.0 (CTRL-01..03)
- ✓ Pomodoro timer widget: IDLE→WORK→SHORT_BREAK→LONG_BREAK state machine, configurable durations, command-file IPC for Start/Pause/Reset — v1.0 (POMO-01..05)
- ✓ Calendar widget: styled date and time display (12h/24h configurable, locale-aware, no external calendar integration) — v1.0 (CAL-01..03)
- ✓ Notification interceptor widget: surfaces Windows toast title/body/app name in bar; auto-dismiss after configurable timeout; WinRT polling approach — v1.0 (NOTF-01..05)

### Active

<!-- v1.1 scope -->
- [ ] User can enable/disable host autostart at Windows login from the control panel (STRT-01..04)
- [ ] Host launches without a visible terminal/console window when started automatically (STRT-03)
- [ ] Control panel packaged as a standalone .exe requiring no Python environment (EXEC-01..04)

<!-- Backlog — not in v1.1 scope -->
- [ ] Pomodoro plays an audio cue at each phase transition (PLSH-01)
- [ ] Widget crash detection with visual placeholder and control panel restart button (PLSH-02)
- [ ] Notification widget shows scrollable queue of multiple simultaneous toasts (PLSH-03)
- [ ] Calendar widget seconds display toggle (PLSH-04)
- [ ] IPC-03 language amendment: document deliberate `proc.terminate()` design (no drain-before-join) to resolve spec/implementation mismatch
- [ ] Retroactive Phase 1 VERIFICATION.md (documentation gap from v1.0 audit)

### Out of Scope

- External calendar integration (Google, Outlook, ICS) — date/time display only; OAuth complexity exceeds v1 value
- Non-Windows platforms — ClipCursor(), WinRT notification APIs, and multi-monitor assumptions are Windows-specific
- GPU-accelerated compositing — standard QPainter is sufficient at 1920×515
- Widget sandboxing beyond process boundaries — process isolation already provides crash containment
- Notification pre-display suppression — no supported Windows API; v1 surfaces toasts in bar in addition to system toast
- In-bar widget configuration UI — ClipCursor() prevents cursor from entering Display 3; architecturally impossible
- Live drag-and-drop widget layout — same cursor constraint
- Per-widget top-level Qt windows — defeats unified compositing model
- winsdk package — archived October 2024; use modular winrt-* packages at 3.2.1

## Context

**Shipped v1.0:** ~4,578 Python LOC across 95 files, 2026-03-26 → 2026-03-27 (2 days)

**Tech stack:**
- Python, PyQt6 6.10.2
- Pillow (widget off-screen rendering)
- pywin32 311 (ClipCursor, WTS session notifications)
- winrt-Windows.UI.Notifications.Management 3.2.1 + 5 peer packages
- multiprocessing.Queue for all IPC (widget → host: FrameData; host → widget: ConfigUpdateMessage, ControlSignal)

**Architecture:**
- Host is the single renderer — widgets never create their own windows
- Widget processes are long-running; they own their own state and push updates to the host
- Control panel is a separate always-accessible process (not embedded in Display 3)
- Notification access requires host-side `RequestAccessAsync` before widget spawn (STA apartment requirement)
- WinRT notification polling at 2s interval (event subscription raises OSError on python.org Python — confirmed in spike)

**Known issues going into v1.1:**
- `test_e2e_dummy.py::test_dummy_frame_received` fails on Windows spawn (pre-existing, excluded from default suite via `@pytest.mark.integration`)
- All 4 VALIDATION.md files are in `draft` status (Nyquist validation was not completed for v1.0)
- Phase 1 has no formal VERIFICATION.md

## Constraints

- **Platform**: Windows only
- **Display**: Hardcoded to Display 3 at 1920×515 for v1.0
- **Language**: Python throughout (PyQt6 for host and control panel)
- **IPC**: multiprocessing.Queue only — no sockets, shared memory, or external message brokers
- **Notification**: Surface-only (no pre-display suppression; no RemoveNotification in v1.0)

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Host renders, widgets push data | Single rendering context avoids Z-order/transparency issues with multiple windows | ✓ Good — clean compositing, no per-widget top-level window issues |
| ClipCursor() for cursor lockout | Simplest reliable Win32 approach; no third-party driver needed | ✓ Good — required WM_ACTIVATEAPP patch for alt-tab edge case (v1.0 fix) |
| Separate control panel process | Keeps configuration UI decoupled; avoids restarting host to reconfigure | ✓ Good — works well; cursor lockout makes in-bar config architecturally impossible |
| config.json as config store | Simple, human-readable; host watches for file changes | ✓ Good — QFileSystemWatcher re-add pattern required for atomic saves |
| Pillow for widget rendering | Keeps widget subprocesses Qt-free (Qt in spawn subprocess crashes on Windows) | ✓ Good — confirmed IPC-01 requirement |
| Command-file IPC for Pomodoro controls | QFileSystemWatcher already watching config dir; same atomic-write pattern | ✓ Good — clean separation from config update path |
| WinRT polling (not event subscription) | add_notification_changed raises OSError on python.org Python; validated in Phase 4 spike | ✓ Good — 2s polling is acceptable latency for notification bar |
| RequestAccessAsync from Qt main thread | Widget subprocess has no STA apartment; call must happen before widget spawn | ✓ Good — confirmed required by Windows COM threading model |
| proc.terminate() without join() in stop_widget | join() on Qt main thread deadlocks on Windows (queue pipe not being drained) | ⚠️ Revisit — IPC-03 spec language needs amendment in v1.1 |

---
*Last updated: 2026-03-27 after v1.1 milestone started*
