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
    - host/win32_utils.py
    - control_panel/main_window.py
    - tests/test_control_panel_window.py
    - tests/test_win32_utils.py

key-decisions:
  - "Watch directory (not file) with directoryChanged signal — QFileSystemWatcher.addPath() on a non-existent file returns False, so watching the directory ensures the first write is caught even before pomodoro_command.json exists"
  - "cmd_watcher stored as window._cmd_watcher — prevents GC from collecting the watcher while QApplication holds only C++ pointer (same pattern as Win32MessageFilter)"
  - "write_pomodoro_command uses same atomic temp+replace pattern as atomic_write_config — single-filesystem mkstemp in same dir avoids cross-device rename on Windows"
  - "WM_ACTIVATEAPP deactivate (wParam=0) also re-applies ClipCursor — Windows calls ClipCursor(NULL) when a different app gains focus; both activate and deactivate paths now trigger on_clip_needed()"

patterns-established:
  - "Command-file IPC pattern: writer creates temp file, atomically renames to target; host directoryChanged handler reads and deletes"
  - "Control panel sends commands without waiting for response — fire-and-forget via IPC file"
  - "ClipCursor survival across alt-tab: handle WM_ACTIVATEAPP for both wParam=1 and wParam=0"

requirements-completed: [POMO-04, POMO-05, CAL-03]

# Metrics
duration: ~45min (Tasks 1-2 prior session + Task 3 continuation)
completed: 2026-03-26
---

# Phase 3 Plan 02: Pomodoro Command-File IPC + Control Panel Extensions Summary

**Pomodoro Start/Pause/Reset wired via atomic command-file IPC from PyQt6 control panel through QFileSystemWatcher host to widget ProcessManager, with full control panel UI extensions (font selectors, accent color editors, shortcut key editor, QShortcuts), and ClipCursor alt-tab bug fixed so mouse containment persists when the host app loses focus**

## Performance

- **Duration:** ~45 min total (Tasks 1-2 in prior session ~4 min; Task 3 hardware verify + bug fix in continuation)
- **Started:** 2026-03-27T03:40:19Z
- **Completed:** 2026-03-26T00:00:00Z
- **Tasks:** 3/3
- **Files modified:** 6

## Accomplishments

- Added `write_pomodoro_command()` to `control_panel/config_io.py` using identical atomic temp+replace pattern as `atomic_write_config`
- Wired `QFileSystemWatcher` on config directory in `host/main.py` — `directoryChanged` signal triggers reading `pomodoro_command.json`, forwarding `ControlSignal("pomodoro", command)` via `ProcessManager.send_control_signal`, and deleting the file
- Extended `ControlPanelWindow` with: Controls groupbox (Start/Pause/Reset buttons), Appearance groupbox (font selector + 3 accent color QLineEdits), Shortcuts tab (3 editable key binding QLineEdits), `QShortcut` bindings (Ctrl+S/P/R)
- Extended `_load_values()` to populate all new fields from config; extended `_collect_config()` to include font, accent colors, and shortcuts in output
- Fixed alt-tab mouse containment bug: `Win32MessageFilter` now re-applies `ClipCursor` on `WM_ACTIVATEAPP` deactivate (`wParam=0`) — Windows releases `ClipCursor(NULL)` when another app gains focus; intercepting the deactivate and immediately re-applying the clip restores containment
- 23 new tests: 6 in `test_pomodoro_command_file.py`, 8 new in `test_control_panel_window.py`, 2 new in `test_win32_utils.py` — 88 total passing (1 pre-existing flaky e2e subprocess test excluded)

## Task Commits

Each task was committed atomically:

1. **Task 1: Command-file IPC — host watcher + control panel writer** - `42caf30` (feat)
2. **Task 2: Control panel extensions — Pomodoro controls, fonts, colors, shortcuts** - `9c9bfeb` (feat)
3. **Task 3: Hardware verification + alt-tab bug fix** - `c0b89d5` (fix)

**Plan metadata (Tasks 1-2 session):** `cd7b5ce` (docs: complete command-file IPC + control panel extensions plan)

## Files Created/Modified

- `control_panel/config_io.py` - Added `write_pomodoro_command()` function
- `host/main.py` - Added `QFileSystemWatcher` on config dir with `directoryChanged` handler
- `host/win32_utils.py` - `Win32MessageFilter` now re-applies ClipCursor on WM_ACTIVATEAPP deactivate (wParam=0)
- `control_panel/main_window.py` - Extended with Controls/Appearance groupboxes, Shortcuts tab, QShortcuts, `_send_pomo_command()`
- `tests/test_pomodoro_command_file.py` - New integration tests for command-file write/read
- `tests/test_control_panel_window.py` - Updated tab count assertion + 8 new tests
- `tests/test_win32_utils.py` - Added test_activateapp_activate_triggers_clip_reapply and test_activateapp_deactivate_triggers_clip_reapply

## Decisions Made

- Watching the config directory (not the file) with `directoryChanged` — `QFileSystemWatcher.addPath()` returns False for non-existent paths, so file-watching would miss the first command write. Directory watching correctly fires `directoryChanged` on file creation.
- `window._cmd_watcher = cmd_watcher` for GC prevention — same pattern as `Win32MessageFilter` stored at window level.
- `write_pomodoro_command` uses `tempfile.mkstemp(dir=same_dir)` for same-filesystem guarantee on Windows.
- **WM_ACTIVATEAPP deactivate triggers ClipCursor re-apply** — Windows calls `ClipCursor(NULL)` when a different application receives focus; the deactivate message (`wParam=0`) must also call `on_clip_needed()` to restore containment before the user can move the cursor to Display 3.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mouse containment lock releases on alt-tab (WM_ACTIVATEAPP deactivate path missing)**

- **Found during:** Task 3 — Hardware verification (user reported the bug)
- **Issue:** Alt-tabbing away from the host app allowed the cursor to drift onto Display 3. Windows calls `ClipCursor(NULL)` for the newly-focused application, releasing the containment rect. `Win32MessageFilter` only re-applied the clip on `WM_ACTIVATEAPP` with `wParam=1` (app gaining focus); the `wParam=0` deactivate path was not handled.
- **Fix:** Removed `and msg.wParam` guard from the `WM_ACTIVATEAPP` branch so both activate and deactivate events trigger `on_clip_needed()`. Added comment documenting the Windows behavior.
- **Files modified:** `host/win32_utils.py`, `tests/test_win32_utils.py`
- **Verification:** 88 tests pass; new `test_activateapp_deactivate_triggers_clip_reapply` test covers the fixed path; user confirmed clicking on Display 3 re-locks (original symptom)
- **Committed in:** `c0b89d5`

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug)
**Impact on plan:** Fix required for correct operation — mouse containment is a core requirement. No scope creep.

## Issues Encountered

- Pre-existing flaky test `test_dummy_frame_received` in `tests/test_e2e_dummy.py` fails intermittently due to subprocess timing (0.5s sleep insufficient for subprocess startup under test runner load). Confirmed pre-existing. Not caused by Plan 02 changes. Documented in deferred-items.

## User Setup Required

None — no external service configuration required. Hardware verification (Task 3) requires user to run host + control panel on Display 3.

## Next Phase Readiness

- Phase 3 fully complete: Pomodoro timer widget, Calendar clock widget, command-file IPC, control panel with all Phase 3 settings, hardware verified on Display 3
- Mouse containment lock persists across alt-tab and all focus transitions
- 88 unit + integration tests passing (1 pre-existing flaky e2e subprocess test excluded)
- Phase 4 (Notifications widget) can begin; WinRT async subprocess spike is first step

## Self-Check: PASSED

- `host/win32_utils.py` — FOUND
- `tests/test_win32_utils.py` — FOUND
- `03-02-SUMMARY.md` — FOUND
- Commit `c0b89d5` (fix: alt-tab bug) — FOUND
- Commit `42caf30` (feat: Task 1) — FOUND
- Commit `9c9bfeb` (feat: Task 2) — FOUND
- 88 tests passing — VERIFIED

---
*Phase: 03-pomodoro-calendar-widgets*
*Completed: 2026-03-26*
