---
phase: 02-config-system-control-panel
plan: "02"
subsystem: ui
tags: [pyqt6, config, atomic-write, control-panel, qmainwindow, qtabwidget]

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

key-decisions:
  - "control_panel is the sole writer of config.json — host (ConfigLoader) never writes, only reads and watches"
  - "Temp file in same directory as target ensures os.replace stays on same filesystem (avoids cross-device rename errors on Windows)"
  - "_update_widget_settings does NOT auto-create widget entries — Phase 3 adds Pomodoro/Calendar to config.json, panel only updates existing entries"
  - "qapp fixture is session-scoped to avoid creating multiple QApplication instances across the test session"

patterns-established:
  - "Widget-type settings lookup: iterate config['widgets'], match by 'type', return settings dict or {}"
  - "Form population via _load_values() called in __init__ after _build_ui()"
  - "Session-scoped qapp fixture in conftest.py for all Qt widget tests"

requirements-completed: [CTRL-01, CTRL-02, CTRL-03]

# Metrics
duration: 2min
completed: 2026-03-26
---

# Phase 2 Plan 02: Control Panel Summary

**PyQt6 QMainWindow control panel with tab-based config UI (Pomodoro/Calendar/Layout) writing config.json atomically via tempfile.mkstemp + os.replace to trigger host QFileSystemWatcher**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-26T13:35:13Z
- **Completed:** 2026-03-26T13:37:23Z
- **Tasks:** 1/2 (Task 2 is a hardware verification checkpoint — no code)
- **Files modified:** 7

## Accomplishments
- Standalone `control_panel` package launchable via `python -m control_panel`
- Atomic config write using `tempfile.mkstemp(dir=same_dir)` + `os.replace` — prevents partial writes and cross-device errors
- `ControlPanelWindow` QMainWindow with three tabs: Layout (display dimensions), Pomodoro (4 spinboxes), Calendar (12h/24h combo)
- 14 tests covering atomic write correctness, error cleanup, temp file placement, form field presence, save round-trip, and value loading
- 50 non-integration tests pass (zero regressions)

## Task Commits

Each task was committed atomically:

1. **Task 1: Atomic config I/O, control panel package skeleton, and ControlPanelWindow with tab forms** - `3d8ee36` (feat)
2. **Task 2: Hardware verification checkpoint** - N/A (no code changes; awaiting human verify)

## Files Created/Modified
- `control_panel/__init__.py` - Package marker
- `control_panel/__main__.py` - Entry point: QApplication + ControlPanelWindow("config.json")
- `control_panel/config_io.py` - load_config (DEFAULT_CONFIG fallback) + atomic_write_config (tempfile.mkstemp + os.replace)
- `control_panel/main_window.py` - ControlPanelWindow QMainWindow: tabs, spinboxes, combobox, save button
- `tests/test_config_io.py` - 6 tests for atomic write and load_config
- `tests/test_control_panel_window.py` - 8 tests for window instantiation and form field presence
- `tests/conftest.py` - Added session-scoped qapp fixture for Qt widget tests

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

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug in test mock setup)
**Impact on plan:** Fix was necessary for test correctness. No scope creep.

## Issues Encountered
None beyond the auto-fixed mock recursion bug above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Control panel package is complete and ready for hardware verification (Task 2 checkpoint)
- After hardware verification confirms double-save hot-reload and widget add/remove, Phase 3 can proceed
- Phase 3 will add Pomodoro and Calendar widget entries to config.json; control panel will then populate their settings fields on save

## Self-Check: PASSED

All 7 created/modified files exist on disk. Task commit 3d8ee36 verified in git log.

---
*Phase: 02-config-system-control-panel*
*Completed: 2026-03-26*
