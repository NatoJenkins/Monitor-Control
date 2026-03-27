---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_plan: 2 / 2 (COMPLETE)
status: IN_PROGRESS
last_updated: "2026-03-26T00:00:00Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 7
  completed_plans: 7
---

# Project State

## Status
`IN_PROGRESS` — Phase 3 complete (hardware verified); ready for Phase 4

## Current Phase
Phase 4 — Notifications Widget
Current Plan: 0 / TBD

## Progress
[##########] Phase 1 complete (3/3 plans)
[##########] Phase 2 complete — hardware verified (2/2 plans)
[##########] Phase 3 complete — hardware verified (2/2 plans)

## Milestone
v1.0 — initial release

## Completed Phases
- Phase 1 — Host Infrastructure + IPC Pipeline (completed 2026-03-26, hardware verified)
- Phase 2 — Config System + Control Panel (completed 2026-03-26, hardware verified)
- Phase 3 — Pomodoro + Calendar Widgets (completed 2026-03-26, hardware verified)

## Last Action
2026-03-26 — Completed Phase 3 Plan 02 fully (all 3 tasks): hardware verified on Display 3, fixed alt-tab mouse containment bug (WM_ACTIVATEAPP deactivate path now re-applies ClipCursor). 88 tests passing.

## Stopped At
Phase 3 complete. Next: Phase 4 (Notifications widget — WinRT async spike first).

## Next Action
Begin Phase 4: WinRT async subprocess spike, then build notifications widget.

## Key Context
- Target display: 1920x515, Display 3 (below two primary monitors)
- Stack: PyQt6 6.10.2, pywin32 311, winrt-Windows.UI.Notifications.Management 3.2.1, watchdog 6.x
- IPC: multiprocessing.Queue (widget → host only for v1; host → widget config update is v2)
- Rendering: host composites RGBA frames from widgets via QTimer drain at 50ms
- Config: atomic write + QFileSystemWatcher re-add pattern
- Notification widget: surface-and-dismiss only (no pre-display suppression — no public API exists)
- Build order: Phase 1 (host+dummy) → Phase 2 (config+panel) → Phase 3 (Pomodoro+Calendar) → Phase 4 (notifications)

## Decisions

1. **FrameData is pure Python** — No Qt/win32 imports in shared/message_schema.py. Widget subprocesses must be able to import FrameData without pulling in Qt. (01-01)
2. **devicePixelRatio for physical pixel matching** — find_target_screen uses int(logical_geo.width() * dpr) rather than physicalSize() (which returns mm). Stays within Qt coordinate model. (01-01)
3. **window.create() before setScreen** — Forces native HWND so windowHandle() is non-None at placement time. (01-01)
4. **Explicit spawn method in __main__** — multiprocessing.set_start_method("spawn") placed in __main__ guard, not in main(). Documents intent and prevents running in subprocesses. (01-01)
5. **Qt QRect.right() off-by-one** — compute_allowed_rect uses left()+width() and top()+height() instead of right()/bottom() because Qt QRect.right() returns left+width-1. Prevents 1-pixel gap at cursor boundary. (01-02)
6. **b"windows_generic_MSG" bytes literal required** — nativeEventFilter event_type on Windows is bytes, not str. Using str would silently never match, breaking all native MSG interception. (01-02)
7. **Win32MessageFilter GC prevention** — Filter stored as window._msg_filter; without a Python-level strong reference, GC can collect the object while QApplication holds only a C++ pointer. (01-02)
8. **QueueDrainTimer schedule_repaint() once per drain cycle** — Called after full drain loop, not inside per-queue loop, letting Qt coalesce repaints into a single paintEvent. (01-03)
9. **Compositor owned by HostWindow** — Stored as window.compositor; paintEvent delegates directly. ProcessManager and drain timer stored as window._pm / window._drain_timer to prevent GC. (01-03)
10. **ProcessManager deadline drain** — Drain loop uses 2s deadline budget before join, not single get_nowait, to flush burst frames and prevent feeder thread deadlock. (01-03)
11. **DummyWidget silent drop on queue.Full** — Backpressure handled by frame dropping (not stalling subprocess); host drain rate matches push rate at 50ms. (01-03)
12. **place_on_screen: setGeometry+show instead of showFullScreen** — showFullScreen() calls MonitorFromWindow internally which selects the active monitor, not the intended target. On the HDMI strip (Display 3), this caused the window to appear on Monitor 2. Fix: setGeometry(screen.geometry()) + show() assigns Qt geometry from the target QScreen directly. (01-03 bug fix, commit 547ef4a)
13. **WIDGET_REGISTRY as module-level dict** — register_widget_type() called before ConfigLoader construction in main.py, enabling upfront type dispatch without coupling ConfigLoader to specific widget imports. (02-01)
14. **in_q maxsize=5 for config updates** — Config updates are infrequent; small buffer prevents unbounded memory if widget subprocess falls behind. Separate from out_q (maxsize=10, high-frequency frames). (02-01)
15. **reconcile: stop before start** — Prevents transient duplicate widget_id state if a widget ID is repurposed across a hot-reload. (02-01)
16. **QFileSystemWatcher re-add on every fileChanged** — Atomic file replacement (editor write) drops the watched path from the watcher; re-add on every event is mandatory for hot-reload to survive saves. (02-01)
17. **control_panel is sole writer of config.json** — host (ConfigLoader) never writes, only reads and watches. Enforced by design: only control_panel/config_io.py has atomic_write_config. (02-02)
18. **Temp file in same directory as target** — tempfile.mkstemp(dir=same_dir) ensures os.replace stays on same filesystem, avoiding cross-device rename errors on Windows. (02-02)
19. **_update_widget_settings does NOT auto-create widget entries** — Phase 3 adds Pomodoro/Calendar to config.json; panel only updates settings for existing entries. (02-02)
20. **qapp fixture is session-scoped** — Avoids creating multiple QApplication instances across test session (Qt enforces singleton). (02-02)
- [Phase 03]: PomodoroState uses time.monotonic() deadline for drift-free countdown — avoids accumulated sleep drift over long sessions. (03-01)
- [Phase 03]: Config duration updates deferred to _apply_pending_durations() at _transition_to() — current countdown unaffected by mid-session config changes. (03-01)
- [Phase 03]: CalendarWidget uses WidgetBase.poll_config_update() not custom _poll_in_queue() — no ControlSignal needed for clock widget. (03-01)
- [Phase 03]: Digital-7.ttf not bundled — unavailable on public GitHub; both widgets fall back to ImageFont.load_default() without crash. (03-01)
- [Phase 03]: Watch config directory with directoryChanged (not file with fileChanged) — QFileSystemWatcher.addPath() returns False for non-existent paths; directory watching catches first pomodoro_command.json creation. (03-02)
- [Phase 03]: window._cmd_watcher = cmd_watcher stored at window level for GC prevention — same pattern as Win32MessageFilter. (03-02)
- [Phase 03]: write_pomodoro_command uses tempfile.mkstemp(dir=same_dir) for same-filesystem atomic rename guarantee on Windows. (03-02)
- [Phase 03]: WM_ACTIVATEAPP deactivate (wParam=0) also re-applies ClipCursor — Windows calls ClipCursor(NULL) when a different app gains focus; both activate and deactivate paths now trigger on_clip_needed() so mouse containment persists across alt-tab. (03-02 bug fix)

## Blockers
None

## Open Questions
1. WinRT async in subprocess — spike required in Phase 4 plan 04-01 before widget build
2. ClipCursor RECT geometry across mixed-DPI 3-monitor layout — validate on real hardware in Phase 1
3. Notification permission persistence across host restarts — confirm during Phase 4 spike

## Performance Metrics

| Phase | Plan | Duration (s) | Tasks | Files |
|-------|------|-------------|-------|-------|
| 01 | 01 | 248 | 2/2 | 15 |
| 01 | 02 | 124 | 2/2 | 3 |
| 01 | 03 | 1800 | 3/3 | 14 |
| 02 | 01 | 331 | 2/2 | 10 |
| 02 | 02 | 1800 | 2/2 | 8 |
| 03 | 01 | 360 | 3/3 | 15 |
| 03 | 02 | 232 | 2/3 | 4 |

