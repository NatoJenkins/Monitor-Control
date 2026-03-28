# MonitorControl

## Current State: v1.2 Shipped

**Shipped:** 2026-03-27
**Milestone:** v1.2 Configurable Colors — all bar and widget colors user-configurable from the control panel

## What This Is

A modular widget framework that drives a dedicated 1920×515 secondary display (Display 3, positioned below two primary monitors) as a persistent utility bar. A host Python/PyQt6 app owns the display as a borderless always-on-top window, compositing rendered output from individual widget subprocesses that communicate via multiprocessing queues. A separate PyQt6 control panel manages widget layout and per-widget configuration via a config.json the host hot-reloads. The control panel ships as a standalone `MonitorControl.exe` (no Python required). v1.2 ships with Pomodoro timer, Calendar/Clock, and Windows notification interceptor widgets, with all colors configurable via hue/intensity color pickers.

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
- ✓ Config resolution is cwd-independent for all launch contexts (desktop double-click, HKCU Run key, pythonw.exe) — v1.1 (INFRA-01..02)
- ✓ Host autostart at Windows login via Startup folder shortcut; Startup tab in control panel with immediate toggle — v1.1 (STRT-01..05)
- ✓ Control panel packaged as standalone MonitorControl.exe (PyInstaller 6 onedir); no Python environment required — v1.1 (PKG-01..04)
- ✓ Reusable ColorPickerWidget with hue slider (0–360), intensity slider (0–100, HSL lightness), live swatch, hex input; QColor.fromHslF — no new pip dependencies — v1.2 (CPKR-01..05)
- ✓ Host compositor owns bar background fill; all widgets render on transparent RGBA background — v1.2 (BG-01..02)
- ✓ bg_color top-level config key (default #1a1a2e) hot-reloads to bar background without host restart — v1.2 (BG-03)
- ✓ Control panel Layout tab exposes bg_color via ColorPickerWidget — v1.2 (BG-04)
- ✓ Calendar widget reads time_color (default #ffffff) and date_color (default #dcdcdc) from settings; updates live on hot-reload — v1.2 (CAL-04..05)
- ✓ Calendar tab exposes time_color and date_color via ColorPickerWidget instances — v1.2 (CAL-06)
- ✓ Pomodoro tab replaces three hex QLineEdit fields with ColorPickerWidget instances for accent colors — v1.2 (POMO-06)
- ✓ All new config keys use .get() with defaults matching current hardcoded values — zero visual change on upgrade — v1.2 (CLR-01)

### Active

<!-- Backlog — deferred to future milestones -->
- [ ] Pomodoro plays an audio cue at each phase transition (PLSH-01)
- [ ] Widget crash detection with visual placeholder and control panel restart button (PLSH-02)
- [ ] Notification widget shows scrollable queue of multiple simultaneous toasts (PLSH-03)
- [ ] Calendar widget seconds display toggle (PLSH-04)
- [ ] IPC-03 spec language amendment: document deliberate `proc.terminate()` design (no drain-before-join)
- [ ] Retroactive Phase 1 VERIFICATION.md (documentation gap from v1.0 audit)
- [ ] Host packaging as standalone .exe (HPKG-01..03) — host still requires a Python environment

### Out of Scope

- External calendar integration (Google, Outlook, ICS) — date/time display only; OAuth complexity exceeds value
- Non-Windows platforms — ClipCursor(), WinRT notification APIs, and multi-monitor assumptions are Windows-specific
- GPU-accelerated compositing — standard QPainter is sufficient at 1920×515
- Widget sandboxing beyond process boundaries — process isolation already provides crash containment
- Notification pre-display suppression — no supported Windows API
- In-bar widget configuration UI — ClipCursor() prevents cursor from entering Display 3; architecturally impossible
- Live drag-and-drop widget layout — same cursor constraint
- Per-widget top-level Qt windows — defeats unified compositing model
- winsdk package — archived October 2024; use modular winrt-* packages at 3.2.1

## Context

**Shipped v1.2:** ~6,096 Python LOC, 2026-03-27

**Tech stack:**
- Python, PyQt6 6.10.2
- Pillow (widget off-screen rendering + icon generation)
- pywin32 311 (ClipCursor, WTS session notifications, HKCU registry via winreg stdlib)
- winrt-Windows.UI.Notifications.Management 3.2.1 + 5 peer packages
- PyInstaller 6.19.0 (build-time only — control panel packaging)
- multiprocessing.Queue for all IPC (widget → host: FrameData; host → widget: ConfigUpdateMessage, ControlSignal)

**Architecture:**
- Host is the single renderer — widgets never create their own windows
- Widget processes are long-running; they own their own state and push updates to the host
- Control panel is a separate always-accessible process (not embedded in Display 3)
- Config lives at `%LOCALAPPDATA%\MonitorControl\config.json` (shared between packaged exe and Python host)
- Notification access requires host-side `RequestAccessAsync` before widget spawn (STA apartment requirement)
- WinRT notification polling at 2s interval (event subscription raises OSError on python.org Python — confirmed in spike)
- ColorPickerWidget uses QColor.fromHslF with fixed SATURATION=0.8 — normalized float internal state preserves hue across achromatic round-trips

**Known issues going into next milestone:**
- `test_e2e_dummy.py::test_dummy_frame_received` fails on Windows spawn (pre-existing)
- All VALIDATION.md files remain in `draft` status (Nyquist sign-off not completed)
- Host packaging deferred to future milestone (HPKG-*) — host still requires a Python environment
- `_update_widget_settings()` docstring claims to create missing widget entries but does not (masked in practice)
- CalendarWidget uses `_text_color` to store `date_color` config value (naming inconsistency)
- After any control panel source change, the PyInstaller exe must be rebuilt: `python -m PyInstaller build/control_panel.spec -y`

## Constraints

- **Platform**: Windows only
- **Display**: Hardcoded to Display 3 at 1920×515
- **Language**: Python throughout (PyQt6 for host and control panel)
- **IPC**: multiprocessing.Queue only — no sockets, shared memory, or external message brokers
- **Notification**: Surface-only (no pre-display suppression)

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
| proc.terminate() without join() in stop_widget | join() on Qt main thread deadlocks on Windows (queue pipe not being drained) | ⚠️ Revisit — IPC-03 spec language needs amendment |
| %LOCALAPPDATA% for shared config path | Packaged exe and Python host must share config.json; exe dir ≠ project root during dev | ✓ Good — discovered during Phase 7 smoke test; both processes now use same file |
| shell:startup shortcut for autostart (not HKCU Run key) | HKCU\Run + StartupApproved\Run is unreliable on Windows 11 — silently ignored despite correct registry state | ✓ Good — .lnk shortcut in Startup folder bypasses broken StartupApproved gate |
| WM_DISPLAYCHANGE triggers full display re-discovery | Monitor power-cycle causes Windows to move host window; ClipCursor reapply alone is insufficient | ✓ Good — debounced re-find + reposition + reclip with 2s retry if display not yet available |
| contents_directory='.' in PyInstaller spec | PyInstaller 6.0+ puts modules in _internal/ by default; breaks Path(__file__).parent.parent | ✓ Good — flat layout restores expected path resolution without code changes |
| ColorPickerWidget uses QColor.fromHslF (not colorsys) | colorsys HLS argument order (H,L,S) is counterintuitive and error-prone; QColor API is already available | ✓ Good — no new pip dependency; re-entrancy guard (_updating flag) required for bidirectional slider sync |
| bg_color as top-level config key (not widget setting) | Background color belongs to the host compositor, not any individual widget | ✓ Good — bypasses _update_widget_settings entirely; simpler load/collect wiring |
| _after_reload wired post-construction (not constructor arg) | ConfigLoader must be bound before the lambda can close over it | ✓ Good — avoids forward-reference problem; documented in Phase 9 SUMMARY |
| Control panel exe rebuild required after source changes | PyInstaller bakes code into binary; no hot-reload for the packaged exe | ✓ Good (operational note) — rebuild with `python -m PyInstaller build/control_panel.spec -y` |

---
*Last updated: 2026-03-27 after v1.2 milestone*
