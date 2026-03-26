# Project Research Summary

**Project:** MonitorControl
**Domain:** Python/PyQt6 desktop widget bar — Windows, dedicated secondary display (1920x515)
**Researched:** 2026-03-26
**Confidence:** HIGH (core architecture and stack), MEDIUM (notification interception), LOW (notification suppression)

---

## Executive Summary

MonitorControl is a host-renders/widget-pushes architecture where a single PyQt6 process owns a dedicated 1920x515 display as a borderless always-on-top window, compositing output from isolated widget subprocesses. Research confirms this model is the right choice: it eliminates Z-order fights, ensures crash isolation, and allows widgets to be developed and swapped without modifying host code. The closest production analog is Stream Deck's plugin architecture, not Rainmeter (per-widget windows) or YASB (all widgets in one process). All core technologies — Python 3.12, PyQt6 6.10.2, pywin32 311, watchdog 6.0.0, and the modular winrt-* packages — are verified stable as of early 2026.

The recommended build order from PROJECT.md is validated by research: host window + cursor lockout + dummy widget first (establishes the entire pipeline), then Pomodoro, Calendar, and finally Notification interceptor. The notification widget is the hardest feature technically — WinRT `UserNotificationListener` requires a one-time user consent granted from the host's main thread, not from the widget subprocess. Importantly, this API can only read and dismiss notifications after they appear; pre-display suppression is not achievable via any supported Windows API and should not be in scope for v1.

The biggest implementation risks are concentrated in Phase 1: five BLOCKER-severity pitfalls all apply to the host window and ProcessManager scaffolding, not to individual widget logic. Getting Phase 1 right — window flags ordering, multiprocessing spawn guard, queue deadlock prevention, ClipCursor recovery on session events, and DPI-correct geometry — is the prerequisite for everything else. None of these are speculative; all have verified mitigations documented in PITFALLS.md.

---

## Key Findings

### Recommended Stack

The stack is fully validated with no controversial choices. Python 3.12 + PyQt6 6.10.2 covers the host window, compositor, config watcher, and control panel. pywin32 311 handles Win32 APIs (ClipCursor, WTS session notifications, window message hooks). watchdog 6.0.0 provides the correct Windows backend (ReadDirectoryChangesW) for config.json hot-reload. The modular `winrt-*` packages (3.2.1) replace the archived `winsdk` monolith for WinRT notification access.

**Core technologies:**
- Python 3.12: runtime — broadest ecosystem validation for Windows GUI work; 3.13 is acceptable alternative
- PyQt6 6.10.2: host window, compositor, control panel — only Python framework with full Qt6 rendering pipeline and correct multi-monitor QScreen API
- pywin32 311: Win32 API access — ClipCursor, WTS session notifications, COM; cleaner than raw ctypes for anything beyond a single call
- watchdog 6.0.0: config hot-reload — ReadDirectoryChangesW backend on Windows, not polling; callback-based, integrates with QThread
- winrt-Windows.UI.Notifications.Management 3.2.1 + winrt-runtime 3.2.1: WinRT notification listener — only supported Python path to UserNotificationListener; `winsdk` is archived (Oct 2024) and must not be used
- Pillow (PIL): widget off-screen rendering — widget subprocesses cannot import PyQt6 (crashes); Pillow renders RGBA bytes that cross the queue safely

**Critical version note:** All winrt-* packages must be pinned to the same minor version (3.2.1). Mixed versions produce import failures.

### Expected Features

Research confirms the project's planned feature set is well-scoped. The core proposition — dedicated display, cursor lockout, host-rendered compositing — is genuinely differentiated from Rainmeter, YASB, and Windows 11 Widgets, none of which implement all three together.

**Must have (table stakes):**
- Persistent always-on-top borderless window — the entire value proposition collapses without this
- Deterministic Display 3 claiming by geometry (not index) — enumeration order is unstable across reboots
- Cursor exclusion via ClipCursor() with recovery on session events — without recovery, cursor enters Display 3 after every lock/sleep
- Flicker-free rendering — double-buffered single surface; per-widget top-level windows are an anti-pattern
- Widget start/stop without host restart — validated via config hot-reload and ProcessManager
- Dummy widget end-to-end — validates the pipeline before any real widget is built
- Pomodoro: start/pause/reset, work/break auto-advance, MM:SS countdown, configurable durations
- Calendar: time/date display, local clock only (no external integration)
- Notification display in bar — surfaces captured toasts with title + body + dismiss action
- Control panel process — separate PyQt6 QMainWindow; the only configuration surface (cursor lockout makes in-bar config impossible)

**Should have after v1 validation:**
- Pomodoro audio cue at phase transition
- Widget crash recovery indicator + restart button in control panel
- Notification queue (multiple simultaneous toasts)

**Confirmed anti-features (do not build):**
- In-bar widget configuration — impossible given ClipCursor(); all config goes through control panel
- Per-widget top-level Qt windows — causes Z-order fights; defeats the compositing model
- Live drag-and-drop widget layout — cursor cannot enter Display 3
- Notification pre-display suppression — no supported Windows API exists for this (confirmed by Microsoft docs)
- Cross-platform support — ClipCursor, QScreen assumptions, and WinRT APIs are all Windows-specific

**Defer to v2+:**
- System resource widgets (CPU/RAM/GPU) — high polling cost; out of scope until plugin framework is proven
- Configurable display selection — hardcoded Display 3 simplifies v1 enormously
- External calendar integration — explicitly deferred in PROJECT.md

### Architecture Approach

The architecture is a hub-and-spoke model with strict process boundaries. The host process owns the Qt event loop, the display surface, the config watcher, and the ProcessManager. Widget subprocesses own their own state and push serialized RGBA frame data via `multiprocessing.Queue`. The control panel is a third independent process that communicates with the host only through config.json on disk. Nothing crosses process boundaries except picklable Python objects (dataclasses, dicts, bytes).

**Major components:**
1. HostWindow — borderless always-on-top PyQt6 QWidget at Display 3; all flags set before show()
2. Compositor — QPainter-based slot renderer; receives FrameData from QueueDrainTimer; one update() per drain cycle
3. QueueDrainTimer — QTimer at 50 ms; drains all widget queues via get_nowait(); never blocks the Qt event loop
4. ProcessManager — spawns, monitors, and terminates widget multiprocessing.Process instances; drain-before-join on stop
5. ConfigLoader/Watcher — QFileSystemWatcher with re-add after atomic file replace; debounced 100ms reload
6. WidgetBase — abstract contract in shared/; defines run() entry point and out_queue push obligation; no Qt imports allowed
7. ControlPanel — separate QMainWindow process; sole writer of config.json; reads/writes atomically (write-to-tmp, os.replace)
8. Win32Utils — ClipCursor with WTS session notification recovery; monitor geometry helpers

**Key data flow:** Widget process renders to RGBA bytes via Pillow → queue.put(FrameData, block=False) → QueueDrainTimer drains → Compositor.update_frame() → QPainter.drawImage() → Display 3. One-way push; host never sends draw requests to widgets. Control signals (Pomodoro start/pause) flow via a second queue from host to widget.

### Critical Pitfalls

All five BLOCKER-severity pitfalls land in Phase 1. They have verified mitigations but no shortcuts are acceptable.

1. **Window flags must be set before show()** — set all flags (FramelessWindowHint | WindowStaysOnTopHint | Tool) in a single setWindowFlags() call before the first show(); never change flags on a visible window. Severity: BLOCKER. Phase 1.

2. **Windows spawn method requires `if __name__ == "__main__":` guard** — missing guard causes recursive subprocess spawning that exhausts handles. Every entry point that creates multiprocessing.Process must be guarded. Severity: BLOCKER. Phase 1.

3. **Queue put() + process.join() deadlock** — widget processes must use `queue.put(msg, block=False)`; host must drain the queue fully before calling process.join() on shutdown/restart. Add proc.kill() fallback after join(timeout=5). Severity: BLOCKER. Phase 1.

4. **QFileSystemWatcher stops watching after atomic file replace** — the file watcher loses the inode after os.replace(); must re-add the path inside the fileChanged slot and debounce with QTimer.singleShot(100ms). Severity: HIGH. Phase 2.

5. **ClipCursor is cleared on session lock, sleep/wake, and UAC prompts** — single call at startup is insufficient; must subscribe to WM_WTSSESSION_CHANGE and WM_DISPLAYCHANGE and re-apply on unlock/resume. Severity: HIGH. Phase 1.

6. **WinRT RequestAccessAsync must run from host's main thread, not from widget subprocess** — subprocess has no STA apartment; permission dialog will silently fail if called from subprocess. Grant access once from host before spawning the notification widget; widget checks GetAccessStatus() only. Severity: HIGH. Phase 4.

7. **QScreen.geometry() returns logical (DPI-scaled) pixels** — identify Display 3 by physical pixels (logical × devicePixelRatio), not raw geometry(); use showFullScreen() not resize() for placement. Severity: HIGH. Phase 1.

---

## Implications for Roadmap

Research validates the build order stated in PROJECT.md and refines it with pitfall context. The key insight is that nearly all blocking risk is in Phase 1 — the host infrastructure must be correct before any widget development begins.

### Phase 1: Host Infrastructure + Pipeline Validation

**Rationale:** All 5 BLOCKER-severity pitfalls live here. The dummy widget is the acceptance test for the entire pipeline. Nothing else can be built until this phase produces a stable, verified host.

**Delivers:** Running host process claiming Display 3 with cursor lockout; dummy widget pushes colored rect via queue and host renders it; config hot-reload working; ProcessManager handles widget crash and restart cleanly.

**Addresses:** All table stakes features except widget-specific logic (Pomodoro, Calendar, Notification).

**Must avoid (and verify):**
- Window flags set after show() — validate always-on-top persists after Alt+Tab and fullscreen app launch
- Missing spawn guard — verify expected process count in Task Manager on startup
- Queue deadlock — verify no hang when stopping a widget via config change
- ClipCursor reset — verify cursor stays blocked from Display 3 after Win+L unlock and sleep/wake
- DPI geometry — verify host window fills Display 3 with no black strip or overflow on target hardware

**Research flag:** Standard patterns — no additional phase research needed. All mitigations are documented.

### Phase 2: Config System + Control Panel

**Rationale:** Config hot-reload and the control panel are prerequisites for widget configurability. The QFileSystemWatcher atomic-replace pitfall (HIGH severity) belongs here. Building config before widgets ensures per-widget settings are available when Pomodoro and Calendar are developed.

**Delivers:** Control panel QMainWindow (separate process); reads/writes config.json atomically; host watches config.json with re-add after atomic replace; hot-reload diff reconciles running widgets without host restart.

**Must avoid:**
- QFileSystemWatcher stops watching — verify two sequential atomic saves both trigger reload
- Control panel and host both holding write handles — control panel is sole writer; host is sole reader
- Config schema drift — define the config schema before building hot-reload; migration logic is expensive to add later

**Research flag:** Standard patterns — QFileSystemWatcher re-add is well-documented; atomic file write pattern is established.

### Phase 3: Pomodoro + Calendar Widgets

**Rationale:** These are the simplest real widgets and validate that the WidgetBase contract, Pillow-based off-screen rendering, and bidirectional queue messaging (control signals Pomodoro → host → widget) work correctly before tackling the technically complex notification widget.

**Delivers:** Pomodoro widget with full state machine (IDLE/WORK/SHORT_BREAK/LONG_BREAK), MM:SS countdown, configurable durations, start/pause/reset from control panel; Calendar widget with 12h/24h display, day-of-week, full date.

**Must avoid:**
- Widget processes importing PyQt6 — use Pillow for off-screen rendering; crashes with host Qt context on Windows spawn
- Blocking queue.put() — all widget puts must be block=False with queue.Full guard

**Research flag:** Standard patterns — Pomodoro state machine and clock display are well-understood; no additional research needed.

### Phase 4: Notification Interceptor Widget

**Rationale:** Most technically complex feature; depends on WinRT APIs, one-time host-side permission grant, and async polling in a subprocess with no UI thread. Builds last so all other infrastructure is proven stable before tackling the highest-risk integration.

**Delivers:** Notification widget that reads Windows toasts from UserNotificationListener, displays title + body + app name in the notification slot, supports dismiss (RemoveNotification), and shows a "permission required" frame if access is denied.

**Must avoid:**
- Calling RequestAccessAsync from widget subprocess — grant access from host main thread before spawning widget
- Assuming pre-display suppression is possible — v1 shows notification in bar in addition to system toast; suppression is not in scope
- Using archived winsdk package — use modular winrt-* packages at 3.2.1

**Research flag:** Needs phase research. WinRT async in a subprocess is the least-validated area. Prototype the UserNotificationListener integration as a standalone spike before building the full notification widget. Validate: (1) GetAccessStatus() reliably reflects host-granted permission in subprocess; (2) asyncio loop behavior in subprocess is compatible with WinRT calls; (3) NotificationChanged event vs polling — determine which is more reliable.

### Phase 5: Polish + v1.x Features

**Rationale:** Once all four widgets are running in daily use, address quality-of-life gaps surfaced by real usage.

**Delivers:** Pomodoro audio cue at phase transition; widget crash recovery indicator in host + restart button in control panel; notification queue showing multiple simultaneous toasts; clock seconds toggle.

**Research flag:** Standard patterns — no additional research needed; all features are incremental additions to established components.

### Phase Ordering Rationale

- Phase 1 first because all BLOCKER pitfalls are in host infrastructure; widget development cannot begin safely until these are verified
- Phase 2 before widgets because config schema must be stable before per-widget settings are implemented in widget code
- Phase 3 before Phase 4 because Pomodoro and Calendar validate the WidgetBase/queue/compositor pipeline with simple widgets before the hard WinRT integration
- Phase 4 last because it has the most external API uncertainty and benefits from a fully proven host/widget infrastructure
- Phase 5 after daily use because its features address problems that only become apparent in real usage, not development

### Research Flags

Needs phase research:
- **Phase 4 (Notification interceptor):** WinRT async in subprocess is MEDIUM-confidence territory; spike required before full feature build. Key unknowns: subprocess asyncio/STA compatibility, polling vs event subscription reliability, permission persistence across host restarts.

Phases with standard patterns (skip research-phase):
- **Phase 1:** All mitigations documented; Win32 and Qt patterns are well-established
- **Phase 2:** QFileSystemWatcher behavior is documented in Qt official docs; atomic file patterns are standard
- **Phase 3:** Pomodoro state machine and clock display have no novel technical risk
- **Phase 5:** Incremental additions to proven components

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All packages verified on PyPI with confirmed versions as of 2026; no known incompatibilities; winsdk deprecation is confirmed |
| Features | HIGH | Table stakes confirmed against Rainmeter, YASB, Windows 11 Widgets; anti-features have clear architectural justification; notification suppression limitation confirmed by Microsoft docs |
| Architecture | HIGH | Core patterns (QueueDrainTimer, slot compositor, WidgetBase contract) are consistent with Qt multiprocessing community practice and Qt official docs; process boundary design is clean and enforceable |
| Pitfalls | HIGH (most), MEDIUM (WinRT async) | ClipCursor, window flags, spawn guard, queue deadlock, and QFileSystemWatcher pitfalls are documented in official sources; WinRT subprocess behavior is MEDIUM — community sources, needs spike validation |

**Overall confidence: HIGH**

### Gaps to Address

- **WinRT async in widget subprocess:** GetAccessStatus() in a subprocess after host-granted permission needs prototype validation. The theory is sound but real-world behavior (apartment type, asyncio loop compatibility) has MEDIUM confidence. Address with a dedicated spike before Phase 4 feature work.
- **ClipCursor geometry with mixed-DPI multi-monitor layout:** The cursor exclusion RECT must be calculated in physical coordinates across monitors with different DPI scaling. The calculation is documented in principle but must be validated on the specific 3-monitor layout (two primaries above, one 1920x515 strip below). Address in Phase 1 hardware testing.
- **Notification permission persistence:** Whether UserNotificationListener access granted in one host session persists without re-prompting across host restarts. Microsoft docs indicate it persists in Windows Settings, but subprocess GetAccessStatus() behavior should be confirmed in the Phase 4 spike.

---

## Sources

### Primary (HIGH confidence)
- PyPI — PyQt6 6.10.2, pywin32 311, watchdog 6.0.0, winrt-* 3.2.1 — version confirmation and compatibility
- Microsoft Learn — ClipCursor, WM_DISPLAYCHANGE, WM_WTSSESSION_CHANGE, Notification Listener — API constraints and requirements
- Qt Docs — QFileSystemWatcher (stops watching on rename), QScreen (logical vs physical pixels), High DPI support
- Python Docs — multiprocessing Queue deadlock warning, cancel_join_thread, spawn/__main__ guard requirement
- GitHub — pywinrt/python-winsdk (archived Oct 2024) — confirms winsdk replacement

### Secondary (MEDIUM confidence)
- Qt Forum — window flags set-after-show behavior in Qt6; monitor placement issues
- pythonguis.com — QThread queue monitor pattern; consistent with Qt docs
- Community sources — multiprocessing spawn behavior on Windows vs Linux; pipe buffer deadlock patterns

### Tertiary (LOW confidence)
- Windows notification suppression via Focus Assist registry — no official API; avoid entirely; do not pursue for v1

---

*Research completed: 2026-03-26*
*Ready for roadmap: yes*
