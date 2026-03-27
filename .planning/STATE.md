# Project State

## Status
`IN_PROGRESS` — Phase 2 plan 1 complete; config system foundation built

## Current Phase
Phase 2 — Config System + Control Panel
Current Plan: 1 / 2

## Progress
[##########] Phase 1 complete (3/3 plans)
[#####     ] Phase 2 in progress (1/2 plans)

## Milestone
v1.0 — initial release

## Completed Phases
- Phase 1 — Host Infrastructure + IPC Pipeline (completed 2026-03-26, hardware verified)

## Last Action
2026-03-26 — Completed Phase 2 Plan 01 (all 2 tasks): config.json schema, ConfigUpdateMessage, bidirectional IPC queues, ConfigLoader with QFileSystemWatcher hot-reload and reconcile, config-driven main.py. 18 tests pass.

## Stopped At
Phase 2 — completed 02-01-PLAN.md; ready for 02-02-PLAN.md (control panel)

## Next Action
Begin Phase 2 Plan 02: control panel UI that reads/writes config.json to trigger hot-reload.

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
