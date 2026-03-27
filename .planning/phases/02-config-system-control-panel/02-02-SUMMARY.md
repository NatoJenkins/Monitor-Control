---
phase: 02-config-system-control-panel
plan: "02"
subsystem: ui
tags: [pyqt6, config, atomic-write, control-panel, qmainwindow, qtabwidget, qfilesystemwatcher, hot-reload]

# Dependency graph
requires:
  - phase: 02-01
    provides: config.json schema, ConfigLoader with QFileSystemWatcher hot-reload, WIDGET_REGISTRY

provides:
  - control_panel package with python -m control_panel entry point
  - atomic_write_config via tempfile.mkstemp + os.replace (same-directory temp)
  - load_config with DEFAULT_CONFIG fallback
  - ControlPanelWindow QMainWindow with Layout/Pomodoro/Calendar tabs
  - Pomodoro tab with 4 QSpinBox fields (work_minutes 1-120, short_break 1-30, long_break 1-60, cycles 1-10)
  - Calendar tab with QComboBox clock_format (12h/24h)
  - Save button calls atomic_write_config triggering host QFileSystemWatcher
  - Hardware-verified: double-save fires two reloads (QFileSystemWatcher re-add pattern confirmed)

affects:
  - Phase 3 (Pomodoro/Calendar widget implementation will read settings written by this panel)
  - Phase 4 (any future config-driven widgets use same pattern)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Atomic write via tempfile.mkstemp(dir=same_dir) + os.replace (not os.rename)
    - QMainWindow control panel as sole config.json writer; host never writes config
    - Tab-based QFormLayout UI with per-widget-type settings sections
    - load_config returns DEFAULT_CONFIG shallow copy when file missing (zero dependencies on existing config)
    - flush=True print logging for observable hot-reload events during hardware verification

key-files:
  created:
    - control_panel/__init__.py
    - control_panel/__main__.py
    - control_panel/config_io.py
    - control_panel/main_window.py
    - tests/test_config_io.py
    - tests/test_control_panel_window.py
  modified:
    - tests/conftest.py
    - host/config_loader.py

key-decisions:
  - "control_panel is the sole writer of config.json — host (ConfigLoader) never writes, only reads and watches"
  - "Temp file in same directory as target ensures os.replace stays on same filesystem (avoids cross-device rename errors on Windows)"
  - "_update_widget_settings does NOT auto-create widget entries — Phase 3 adds Pomodoro/Calendar to config.json, panel only updates existing entries"
  - "qapp fixture is session-scoped to avoid creating multiple QApplication instances across the test session"

patterns-established:
  - "Widget-type settings lookup: iterate config['widgets'], match by 'type', return settings dict or {}"
  - "Form population via _load_values() called in __init__ after _build_ui()"
  - "Session-scoped qapp fixture in conftest.py for all Qt widget tests"

requirements-completed: [CTRL-01, CTRL-02, CTRL-03, CFG-02, CFG-03]

# Metrics
duration: 30min
completed: 2026-03-26
---

# Phase 2 Plan 02: Control Panel Summary

**PyQt6 QMainWindow control panel with tab-based config UI (Pomodoro/Calendar/Layout) writing config.json atomically via tempfile.mkstemp + os.replace to trigger host QFileSystemWatcher — double-save hot-reload verified on hardware**

## Performance

- **Duration:** ~30 min (implementation + hardware verification)
- **Started:** 2026-03-26T19:57Z
- **Completed:** 2026-03-26
- **Tasks:** 2/2
- **Files modified:** 8

## Accomplishments

- Standalone `control_panel` package launchable via `python -m control_panel`
- Atomic config write using `tempfile.mkstemp(dir=same_dir)` + `os.replace` — prevents partial writes and cross-device errors
- `ControlPanelWindow` QMainWindow with three tabs: Layout (display dimensions), Pomodoro (4 spinboxes), Calendar (12h/24h combo)
- 14 tests covering atomic write correctness, error cleanup, temp file placement, form field presence, save round-trip, and value loading; 50 total passing
- Hardware verification confirmed: double-save fires two distinct hot-reload log lines (QFileSystemWatcher re-add pattern working end-to-end), widget process lifecycle correct on add/remove

## Task Commits

Each task was committed atomically:

1. **Task 1: Atomic config I/O, control panel package skeleton, and ControlPanelWindow with tab forms** - `3d8ee36` (feat)
2. **Task 1 fix: Add ConfigLoader console logging so hot-reload is observable** - `b30f97d` (fix)
3. **Task 2: Hardware verification checkpoint** - N/A (no code changes; confirmed by user)

## Files Created/Modified

- `control_panel/__init__.py` - Package marker
- `control_panel/__main__.py` - Entry point: QApplication + ControlPanelWindow("config.json")
- `control_panel/config_io.py` - load_config (DEFAULT_CONFIG fallback) + atomic_write_config (tempfile.mkstemp + os.replace)
- `control_panel/main_window.py` - ControlPanelWindow QMainWindow: tabs, spinboxes, combobox, save button
- `tests/test_config_io.py` - 6 tests for atomic write and load_config
- `tests/test_control_panel_window.py` - 8 tests for window instantiation and form field presence
- `tests/conftest.py` - Added session-scoped qapp fixture for Qt widget tests
- `host/config_loader.py` - Added flush=True print statements for hot-reload observability (watcher init, fileChanged, _do_reload)

## Decisions Made

- `control_panel` is the sole writer of `config.json` — `ConfigLoader` in the host never writes, only reads and watches
- Temp file placed in same directory as target so `os.replace` stays within one filesystem (avoids cross-device errors on Windows)
- `_update_widget_settings` does NOT auto-create widget entries for unknown types — Phase 3 is responsible for adding Pomodoro/Calendar entries to config.json
- `qapp` fixture is session-scoped to avoid multiple QApplication instances across the test session

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed recursive mock in test_atomic_write_uses_os_replace**
- **Found during:** Task 1 (TDD GREEN phase — running tests)
- **Issue:** `real_replace = os.replace` was assigned inside the `patch("os.replace")` context, so `real_replace` captured the mock itself, causing infinite recursion
- **Fix:** Changed to `patch("control_panel.config_io.os.replace", wraps=os.replace)` to patch the module-local reference while delegating to the real function
- **Files modified:** tests/test_config_io.py
- **Verification:** test_atomic_write_uses_os_replace passes without recursion error
- **Committed in:** 3d8ee36 (Task 1 commit)

**2. [Rule 1 - Bug] Added flush=True logging to ConfigLoader so hot-reload is observable during hardware verification**
- **Found during:** Task 2 (hardware verification checkpoint — before user ran the test)
- **Issue:** ConfigLoader had no console output on fileChanged or _do_reload; hardware tester would see no signal that hot-reload fired, making the double-save test impossible to verify
- **Fix:** Added print statements with `flush=True` at watcher init (path + addPath result), on every fileChanged signal (shows re-add is happening), and on _do_reload entry (confirms debounce fired)
- **Files modified:** host/config_loader.py
- **Verification:** Host console showed both reload log lines during double-save test, confirming re-add pattern works
- **Committed in:** b30f97d (separate fix commit)

---

**3. [Rule 1 - Bug] stop_widget deadlocked Qt main thread on proc.join()**
- **Found during:** Hardware verification (widget removal test — host froze, cursor escaped Display 3)
- **Issue:** `stop_widget` called `proc.join(timeout=5)` on the Qt main thread. The child's multiprocessing Queue feeder thread blocks flushing the pipe; the drain timer (also on the main thread) can't run while join() blocks; classic deadlock. Host window became unresponsive indefinitely.
- **Fix:** Removed drain loop and `proc.join()` from `stop_widget`. `proc.terminate()` on Windows calls `TerminateProcess()` — immediate hard kill, no join needed. Daemon processes are OS-collected on parent exit.
- **Files modified:** host/process_manager.py
- **Committed in:** 726eccc

**4. [Rule 1 - Bug] remove_slot did not trigger a repaint — removed widget frame lingered on screen**
- **Found during:** Hardware verification (widget still visible after remove + hot-reload)
- **Issue:** `QueueDrainTimer._drain()` only calls `schedule_repaint()` when new frames arrive. After `stop_widget`, the widget is removed from `_pm._widgets` so no frames arrive; `updated` stays False; repaint never fires; old teal frame lingers.
- **Fix:** `compositor.remove_slot()` now calls `self.schedule_repaint()` directly after clearing the slot.
- **Files modified:** host/compositor.py
- **Committed in:** d3fb9fd

**5. [Rule 1 - Bug] ClipCursor cleared after hot-reload — cursor escaped Display 3 after widget add/remove**
- **Found during:** Hardware verification (cursor restriction broken after reconcile cycle)
- **Issue:** Process spawn/terminate during reconcile cleared ClipCursor silently. `Win32MessageFilter` only re-applied on session unlock and display change — not on app activation or config reloads.
- **Fix:** Two-part: (a) `ConfigLoader` accepts `after_reload` callback, called after every successful `_reconcile` — `main.py` passes `reapply_clip`. (b) `Win32MessageFilter` handles `WM_ACTIVATEAPP` to re-apply whenever the host window regains focus.
- **Files modified:** host/config_loader.py, host/win32_utils.py, host/main.py
- **Committed in:** d5ba291

---

**Total deviations:** 5 auto-fixed (1 test mock bug, 1 observability bug, 3 runtime bugs found during hardware verification)
**Impact on plan:** All fixes necessary for correctness. No scope creep.

## Issues Encountered

None beyond the two auto-fixed issues above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Control panel package is complete and hardware-verified; Phase 3 can proceed
- Phase 3 will add Pomodoro and Calendar widget entries to config.json; control panel will then populate their settings fields on save
- QFileSystemWatcher hot-reload confirmed working end-to-end — Phase 3 settings changes will propagate to host automatically
- No blockers

## Self-Check: PASSED

All 8 created/modified files exist on disk. Task commits 3d8ee36 and b30f97d verified in git log.

---
*Phase: 02-config-system-control-panel*
*Completed: 2026-03-26*
