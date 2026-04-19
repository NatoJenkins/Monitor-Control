---
phase: 03-pomodoro-calendar-widgets
plan: 01
subsystem: widgets
tags: [pillow, pomodoro, calendar, ipc, state-machine, fonts, pillow-rendering]

requires:
  - phase: 02-config-system-control-panel
    provides: WidgetBase, ProcessManager, ConfigLoader, ConfigUpdateMessage, QFileSystemWatcher pattern

provides:
  - PomodoroWidget subprocess with IDLE/WORK/SHORT_BREAK/LONG_BREAK state machine and Pillow rendering
  - CalendarWidget subprocess with 12h/24h time format and Pillow date rendering
  - ControlSignal dataclass in shared/message_schema.py
  - ProcessManager.send_control_signal method
  - config.json with pomodoro + calendar widget entries and shortcuts section
  - Host registration of both real widget types (dummy removed)
  - 20 unit tests covering state machine, rendering, config updates, source purity

affects:
  - 04-notifications
  - Any phase touching host/main.py widget registration

tech-stack:
  added: [Pillow (PIL), Inter-Regular.ttf, ShareTechMono-Regular.ttf]
  patterns:
    - Monotonic deadline countdown (time.monotonic() + duration, not wall clock)
    - Deferred duration config updates (applied on next state transition, not mid-countdown)
    - Immediate visual config updates (colors/font apply on next rendered frame)
    - Pillow textbbox centering with offset correction (bbox[0]/bbox[1] subtracted from position)
    - Non-blocking queue push with queue.Full guard (block=False)
    - Subprocess-safe widgets with no PyQt6 imports
    - AST-based source purity tests (no PyQt6, block=False enforcement)

key-files:
  created:
    - widgets/pomodoro/__init__.py
    - widgets/pomodoro/widget.py
    - widgets/pomodoro/fonts/Inter-Regular.ttf
    - widgets/pomodoro/fonts/ShareTechMono-Regular.ttf
    - widgets/calendar/__init__.py
    - widgets/calendar/widget.py
    - widgets/calendar/fonts/Inter-Regular.ttf
    - widgets/calendar/fonts/ShareTechMono-Regular.ttf
    - tests/test_pomodoro_widget.py
    - tests/test_calendar_widget.py
  modified:
    - shared/message_schema.py
    - host/process_manager.py
    - host/main.py
    - config.json
    - tests/test_config_loader.py

key-decisions:
  - "PomodoroState uses time.monotonic() deadline (not elapsed) for drift-free countdown — deadline = monotonic() + duration, remaining = deadline - monotonic()"
  - "Config duration updates deferred to _apply_pending_durations() called in _transition_to() — current countdown unaffected by mid-session config changes"
  - "Config color/font updates apply immediately — stored in _work_color/_font_name and used on next render_frame()"
  - "CalendarWidget uses poll_config_update() from WidgetBase (no ControlSignal needed for clock)"
  - "Digital-7.ttf not bundled (unavailable on GitHub) — both widgets fall back to ImageFont.load_default() without crash"
  - "test_config_json_valid_schema updated from dummy to pomodoro+calendar assertion — Phase 3 removes dummy from config"

patterns-established:
  - "Pillow RGBA widget pattern: Image.new('RGBA', (W, H), bg) -> ImageDraw -> textbbox centering -> img.tobytes()"
  - "State machine pattern: enum.Enum states + _transition_to() + _auto_advance() + monotonic deadline"
  - "TDD source purity pattern: ast.walk() to verify block=False on all .put() calls; source scan for PyQt6 absence"

requirements-completed: [POMO-01, POMO-02, POMO-03, POMO-05, CAL-01, CAL-02, CAL-03]

duration: 6min
completed: 2026-03-26
---

# Phase 3 Plan 01: Pomodoro and Calendar Widgets Summary

**Pillow-rendered Pomodoro timer (IDLE/WORK/SHORT_BREAK/LONG_BREAK state machine with monotonic countdown) and Calendar clock (12h/24h format) running as subprocess-safe widgets with ControlSignal IPC, 20 passing unit tests, and both registered in host**

## Performance

- **Duration:** 6 min
- **Started:** 2026-03-26T22:49:58Z
- **Completed:** 2026-03-26T22:56:00Z
- **Tasks:** 3
- **Files modified:** 14

## Accomplishments
- PomodoroWidget with full state machine: IDLE -> WORK -> SHORT_BREAK -> LONG_BREAK cycle, pause/resume, reset, deferred duration config updates
- CalendarWidget with 12h/24h format switching, day-of-week date display, 1Hz push rate, immediate config updates
- ControlSignal dataclass added to shared IPC schema; ProcessManager.send_control_signal method added
- config.json replaced dummy widget with pomodoro (x=0, w=640) + calendar (x=640, w=640) entries plus shortcuts section
- host/main.py updated to register both real widget types; dummy widget import removed
- Inter-Regular.ttf and ShareTechMono-Regular.ttf bundled in both widget fonts directories

## Task Commits

Each task was committed atomically:

1. **Task 1: IPC schema + ProcessManager + config.json + host registration** - `5e92dcd` (feat)
2. **Task 2 RED: Pomodoro failing tests** - `63b4ee5` (test)
3. **Task 2 GREEN: PomodoroWidget implementation** - `9e25f2f` (feat)
4. **Task 3 RED: Calendar failing tests** - `7d9ebba` (test)
5. **Task 3 GREEN: CalendarWidget implementation** - `74107af` (feat)
6. **Auto-fix: stale config schema test** - `8962a37` (fix)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks have RED (test) and GREEN (feat) commits._

## Files Created/Modified
- `shared/message_schema.py` - Added ControlSignal dataclass
- `host/process_manager.py` - Added send_control_signal method, imported ControlSignal
- `host/main.py` - Replaced dummy registration with pomodoro + calendar registrations
- `config.json` - Replaced dummy widget with pomodoro + calendar entries; added shortcuts
- `widgets/pomodoro/__init__.py` - Package marker (empty)
- `widgets/pomodoro/widget.py` - PomodoroWidget, PomodoroState enum, format_mm_ss, run_pomodoro_widget
- `widgets/pomodoro/fonts/Inter-Regular.ttf` - Bundled font (downloaded from rsms/inter v4.1)
- `widgets/pomodoro/fonts/ShareTechMono-Regular.ttf` - Bundled font (from google/fonts)
- `widgets/calendar/__init__.py` - Package marker (empty)
- `widgets/calendar/widget.py` - CalendarWidget, _format_time, _format_date, run_calendar_widget
- `widgets/calendar/fonts/Inter-Regular.ttf` - Bundled font (copied from pomodoro/fonts)
- `widgets/calendar/fonts/ShareTechMono-Regular.ttf` - Bundled font (copied from pomodoro/fonts)
- `tests/test_pomodoro_widget.py` - 12 tests: source purity, state machine, rendering, config update
- `tests/test_calendar_widget.py` - 8 tests: source purity, rendering, time/date format, config update, run loop
- `tests/test_config_loader.py` - Updated stale dummy assertion to pomodoro+calendar (auto-fix)

## Decisions Made
- Used `time.monotonic()` deadline pattern for drift-free countdown instead of elapsed-time accumulation
- Deferred duration updates: stored in `_pending_durations`, applied only in `_transition_to()` to avoid disrupting active countdown
- CalendarWidget uses `%#d` (Windows no-leading-zero day) in `_format_date()` per research
- Digital-7.ttf not bundled — unavailable on public GitHub; widget falls back cleanly to `ImageFont.load_default()`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated stale test_config_json_valid_schema assertion**
- **Found during:** Post-task full suite regression check
- **Issue:** test_config_loader.py line 66 asserted `data["widgets"][0]["id"] == "dummy"`. Phase 3 replaced dummy with pomodoro+calendar, causing `AssertionError: 'pomodoro' == 'dummy'`
- **Fix:** Updated assertion to check for presence of `"pomodoro"` and `"calendar"` widget IDs
- **Files modified:** `tests/test_config_loader.py`
- **Verification:** `python -m pytest tests/ -m "not integration" -x -q` — 70 passed
- **Committed in:** `8962a37`

---

**Total deviations:** 1 auto-fixed (Rule 1 — stale test assertion)
**Impact on plan:** Fix necessary for full suite regression passing. No scope creep.

## Issues Encountered
- Digital-7.ttf download failed (unavailable on public GitHub/dafont direct URL). Per plan fallback guidance, widget uses `ImageFont.load_default(size=N)` when TTF file absent — no crash. Not a blocking issue.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Both widgets are running in host and rendering meaningful frames via Pillow
- ProcessManager.send_control_signal available for future keyboard shortcut wiring
- Phase 4 (notifications) can proceed — IPC schema, host registration, and widget subprocess pattern are established
- Digital-7.ttf can be manually downloaded and placed in `widgets/pomodoro/fonts/` and `widgets/calendar/fonts/` for the digital clock font if desired

---
*Phase: 03-pomodoro-calendar-widgets*
*Completed: 2026-03-26*

## Self-Check: PASSED

All 10 required files found on disk. All 6 task commits verified in git log. 70/70 unit tests pass (no regressions).
