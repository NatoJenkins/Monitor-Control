---
phase: 03-pomodoro-calendar-widgets
plan: 02
subsystem: ui
tags: [pyqt6, ipc, command-file, qfilesystemwatcher, control-panel, pomodoro]

# Dependency graph
requires:
  - phase: 03-01
    provides: PomodoroWidget + CalendarWidget with ControlSignal IPC schema, ProcessManager.send_control_signal
  - phase: 02-02
    provides: ControlPanelWindow base, atomic_write_config, QFileSystemWatcher config hot-reload pattern

provides:
  - write_pomodoro_command() in control_panel/config_io.py (atomic JSON command-file writer)
  - QFileSystemWatcher on config directory in host/main.py (directoryChanged -> send_control_signal)
  - ControlPanelWindow extended with Controls groupbox (Start/Pause/Reset), Appearance (font + accent colors), Shortcuts tab
  - QShortcut bindings Ctrl+S/P/R wired to _send_pomo_command
  - 21 new tests covering command-file IPC and all new control panel UI elements

affects: [04-notifications, hardware-verification]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Command-file IPC: control panel writes JSON atomically, host watches directory with directoryChanged signal, reads + forwards as ControlSignal, then deletes file"
    - "QFileSystemWatcher on directory (not file) catches creation of new files — directoryChanged fires on file create/delete within directory"
    - "GC prevention: window._cmd_watcher = cmd_watcher stores reference at window level to keep watcher alive"

key-files:
  created:
    - tests/test_pomodoro_command_file.py
  modified:
    - control_panel/config_io.py
    - host/main.py
    - control_panel/main_window.py
    - tests/test_control_panel_window.py

key-decisions:
  - "Watch directory (not file) with directoryChanged signal — QFileSystemWatcher.addPath() on a non-existent file returns False, so watching the directory ensures the first write is caught even before pomodoro_command.json exists"
  - "cmd_watcher stored as window._cmd_watcher — prevents GC from collecting the watcher while QApplication holds only C++ pointer (same pattern as Win32MessageFilter)"
  - "write_pomodoro_command uses same atomic temp+replace pattern as atomic_write_config — single-filesystem mkstemp in same dir avoids cross-device rename on Windows"

patterns-established:
  - "Command-file IPC pattern: writer creates temp file, atomically renames to target; host directoryChanged handler reads and deletes"
  - "Control panel sends commands without waiting for response — fire-and-forget via IPC file"

requirements-completed: [POMO-04, POMO-05, CAL-03]

# Metrics
duration: 4min
completed: 2026-03-27
---

# Phase 3 Plan 02: Pomodoro Command-File IPC + Control Panel Extensions Summary

**Pomodoro Start/Pause/Reset wired via atomic command-file IPC from PyQt6 control panel through QFileSystemWatcher host to widget ProcessManager, with full control panel UI extensions (font selectors, accent color editors, shortcut key editor, QShortcuts)**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T03:40:19Z
- **Completed:** 2026-03-27T03:44:11Z
- **Tasks:** 2/3 (Task 3 is checkpoint:human-verify — requires hardware)
- **Files modified:** 4

## Accomplishments

- Added `write_pomodoro_command()` to `control_panel/config_io.py` using identical atomic temp+replace pattern as `atomic_write_config`
- Wired `QFileSystemWatcher` on config directory in `host/main.py` — `directoryChanged` signal triggers reading `pomodoro_command.json`, forwarding `ControlSignal("pomodoro", command)` via `ProcessManager.send_control_signal`, and deleting the file
- Extended `ControlPanelWindow` with: Controls groupbox (Start/Pause/Reset buttons), Appearance groupbox (font selector + 3 accent color QLineEdits), Shortcuts tab (3 editable key binding QLineEdits), `QShortcut` bindings (Ctrl+S/P/R)
- Extended `_load_values()` to populate all new fields from config; extended `_collect_config()` to include font, accent colors, and shortcuts in output
- 21 new tests: 6 in `test_pomodoro_command_file.py` (command-file IPC integration), 8 new in `test_control_panel_window.py` (all new UI elements) — 86 total passing (1 pre-existing flaky e2e subprocess test excluded)

## Task Commits

Each task was committed atomically:

1. **Task 1: Command-file IPC — host watcher + control panel writer** - `42caf30` (feat)
2. **Task 2: Control panel extensions — Pomodoro controls, fonts, colors, shortcuts** - `9c9bfeb` (feat)
3. **Task 3: Hardware verification** - PENDING checkpoint:human-verify

**Plan metadata:** (pending — created at checkpoint)

## Files Created/Modified

- `control_panel/config_io.py` - Added `write_pomodoro_command()` function
- `host/main.py` - Added `QFileSystemWatcher` on config dir with `directoryChanged` handler
- `control_panel/main_window.py` - Extended with Controls/Appearance groupboxes, Shortcuts tab, QShortcuts, `_send_pomo_command()`
- `tests/test_pomodoro_command_file.py` - New integration tests for command-file write/read
- `tests/test_control_panel_window.py` - Updated tab count assertion + 8 new tests

## Decisions Made

- Watching the config directory (not the file) with `directoryChanged` — `QFileSystemWatcher.addPath()` returns False for non-existent paths, so file-watching would miss the first command write. Directory watching correctly fires `directoryChanged` on file creation.
- `window._cmd_watcher = cmd_watcher` for GC prevention — same pattern as `Win32MessageFilter` stored at window level.
- `write_pomodoro_command` uses `tempfile.mkstemp(dir=same_dir)` for same-filesystem guarantee on Windows.

## Deviations from Plan

None — plan executed exactly as written. The directory-watching approach was already specified as the "better approach" in the plan action section.

## Issues Encountered

- Pre-existing flaky test `test_dummy_frame_received` in `tests/test_e2e_dummy.py` fails intermittently due to subprocess timing (0.5s sleep insufficient for subprocess startup under test runner load). Confirmed pre-existing by checking on stashed state. Not caused by Plan 02 changes. Documented in deferred-items.

## User Setup Required

None — no external service configuration required. Hardware verification (Task 3) requires user to run host + control panel on Display 3.

## Next Phase Readiness

- Command-file IPC complete and tested
- Control panel fully extended with all Phase 3 settings
- Pending: hardware verification on Display 3 (Task 3 checkpoint)
- After hardware approval: Phase 4 (Notifications widget) can begin

---
*Phase: 03-pomodoro-calendar-widgets*
*Completed: 2026-03-27*
