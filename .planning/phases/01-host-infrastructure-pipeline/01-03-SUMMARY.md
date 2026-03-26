---
phase: 01-host-infrastructure-pipeline
plan: 03
subsystem: ipc
tags: [pyqt6, multiprocessing, qpainter, qtimer, ipc, compositor, process-manager]

# Dependency graph
requires:
  - phase: 01-host-infrastructure-pipeline
    plan: 01
    provides: HostWindow, find_target_screen, place_on_screen, shared/message_schema.py (FrameData)
  - phase: 01-host-infrastructure-pipeline
    plan: 02
    provides: ClipCursor, Win32MessageFilter, WTS session notifications, host/main.py scaffold
provides:
  - WidgetBase abstract class with run() contract (no Qt/win32 dependencies)
  - DummyWidget: 20 Hz solid teal RGBA32 frame pusher with block=False IPC
  - run_dummy_widget subprocess entry point
  - ProcessManager: spawn/stop/monitor with drain-before-join and kill fallback
  - Compositor: QPainter slot renderer with placeholder (#1a1a1a) and crash (#8B0000) fills
  - QueueDrainTimer: 50ms QTimer drain via get_nowait(), update() once per cycle
  - Full pipeline wired in host/main.py and host/window.py
  - Unit and integration test coverage for all IPC components
affects: [02-config-panel, 03-pomodoro-calendar, 04-notifications]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "block=False on every multiprocessing.Queue.put() — never block in subprocess"
    - "Drain-before-join: drain queue fully before proc.join() on stop to prevent feeder thread deadlock"
    - "QueueDrainTimer: 50ms QTimer drain in Qt main thread, get_nowait() loop, update() once per drain"
    - "Compositor paintEvent delegation: HostWindow.paintEvent → Compositor.paint(painter)"
    - "Kill fallback: proc.kill() after 5s join timeout if process does not terminate"
    - "Crash detection: mark_crashed on dead process, rendered as dark red slot fill"

key-files:
  created:
    - widgets/base.py
    - widgets/dummy/__init__.py
    - widgets/dummy/widget.py
    - host/compositor.py
    - host/process_manager.py
    - host/queue_drain.py
    - tests/test_compositor.py
    - tests/test_process_manager.py
    - tests/test_queue_drain.py
    - tests/test_dummy_widget.py
    - tests/test_e2e_dummy.py
  modified:
    - host/window.py
    - host/main.py

key-decisions:
  - "QueueDrainTimer calls schedule_repaint() once after full drain loop, not inside the per-queue loop — lets Qt coalesce repaints"
  - "Compositor stored as window.compositor attribute (not separate import) so HostWindow owns the lifecycle and paintEvent can call it directly"
  - "ProcessManager drain loop uses deadline-based while loop (not just one get_nowait) to handle bursts of queued frames before join"
  - "DummyWidget uses block=False with silent queue.Full drop — backpressure handled by dropping frames, not stalling the subprocess"

patterns-established:
  - "Pattern: Widget subprocess entry point is a standalone function (run_dummy_widget), not a method call — compatible with multiprocessing.Process target="
  - "Pattern: WidgetBase has no Qt/win32 imports — subprocess isolation boundary enforced at class level"
  - "Pattern: Compositor.set_slots({widget_id: QRect}) called at startup before first frame arrives — no lazy slot creation"

requirements-completed: [HOST-03, IPC-01, IPC-02, IPC-03, IPC-04]

# Metrics
duration: 4min
completed: 2026-03-26
---

# Phase 1 Plan 03: IPC Pipeline — Compositor, ProcessManager, QueueDrainTimer, DummyWidget Summary

**Full IPC pipeline from subprocess to screen: multiprocessing.Queue push at 20 Hz through drain timer to QPainter compositor rendering a teal rectangle on Display 3**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-03-26T23:24:40Z
- **Completed:** 2026-03-26T23:28:26Z
- **Tasks:** 2 of 3 (Task 3 is hardware verification checkpoint — awaiting user)
- **Files modified:** 13

## Accomplishments
- Complete IPC pipeline: DummyWidget subprocess pushes FrameData via multiprocessing.Queue at 20 Hz
- ProcessManager handles spawn, graceful terminate with drain-before-join, and kill fallback after 5s
- QueueDrainTimer fires every 50ms in the Qt main thread, drains via get_nowait(), triggers single repaint
- Compositor renders all widget slots via QPainter.drawImage (active frame), fillRect #1a1a1a (empty), fillRect #8B0000 (crashed)
- HostWindow.paintEvent now delegates entirely to Compositor.paint(painter)
- host/main.py fully wired: ProcessManager + QueueDrainTimer started, aboutToQuit.connect(cleanup) for clean shutdown
- All 18 non-integration tests pass (8 new IPC tests + 10 from prior plans)

## Task Commits

Each task was committed atomically:

1. **Task 1: WidgetBase, DummyWidget, ProcessManager, Compositor, QueueDrainTimer, and test scaffolds** - `8584eff` (feat)
2. **Task 2: Wire ProcessManager, Compositor, QueueDrainTimer into host/window.py and host/main.py** - `055a885` (feat)

**Plan metadata:** (added after hardware verification — Task 3 checkpoint)

## Files Created/Modified

- `widgets/base.py` - WidgetBase abstract class with run() contract; no Qt/win32 imports
- `widgets/dummy/__init__.py` - Empty package init
- `widgets/dummy/widget.py` - DummyWidget: solid teal RGBA32 at 20 Hz with block=False; run_dummy_widget entry point
- `host/compositor.py` - Compositor: QPainter slot renderer with update_frame, mark_crashed, paint()
- `host/process_manager.py` - ProcessManager: spawn/stop/monitor with drain-before-join + kill fallback
- `host/queue_drain.py` - QueueDrainTimer: 50ms QTimer, get_nowait() drain, single schedule_repaint per cycle
- `host/window.py` - Updated: Compositor integrated, paintEvent delegates to compositor.paint()
- `host/main.py` - Updated: ProcessManager + QueueDrainTimer wired, aboutToQuit.connect(cleanup)
- `tests/test_compositor.py` - Tests: blit renders frame, placeholder fill, crash fill
- `tests/test_process_manager.py` - Integration tests: start creates process, stop drains queue, kill fallback
- `tests/test_queue_drain.py` - Tests: drain empties queue (update_frame x3, schedule_repaint x1), crash detection
- `tests/test_dummy_widget.py` - Tests: static analysis for block=False and no PyQt6, thread-based push test
- `tests/test_e2e_dummy.py` - Integration: real subprocess pushes FrameData with correct dimensions

## Decisions Made

- **QueueDrainTimer calls schedule_repaint() once after full drain loop** — not inside the per-queue inner loop. This lets Qt coalesce multiple pending repaints into a single paintEvent, reducing flicker.
- **Compositor stored as window.compositor** — HostWindow owns the lifecycle; paintEvent calls it directly without a separate reference chain.
- **ProcessManager deadline drain** — uses a deadline-based while loop (2s budget) rather than a single get_nowait to drain any burst of queued frames before calling join.
- **DummyWidget silent drop on queue.Full** — backpressure absorbed by frame dropping, not subprocess stalling. The host drain rate (50ms) matches the widget push rate (50ms); Full conditions are transient.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Hardware verification (Task 3) is a blocking checkpoint. The user must run `python -m host.main` and verify:
1. Display 3 shows a fullscreen window with no taskbar entry
2. Solid teal (0,128,128) rectangle fills the dummy widget slot — no flicker
3. Cursor cannot enter Display 3; survives Win+L/unlock
4. Killing the dummy widget subprocess turns its slot dark red within ~50ms
5. Exactly 2 Python processes (host + dummy widget), no cascade

After hardware verification passes, Phase 1 is complete and Phase 2 (config panel) can begin.

---
*Phase: 01-host-infrastructure-pipeline*
*Completed: 2026-03-26*
