---
phase: 09-config-schema-host-hot-reload-wiring
plan: 02
subsystem: widgets
tags: [pillow, calendar, config, hot-reload, color]

# Dependency graph
requires:
  - phase: 08-bg-ownership-migration
    provides: transparent widget backgrounds (CalendarWidget renders RGBA with no fill)
  - phase: 09-01
    provides: ConfigLoader hot-reload wiring + bg_color pipeline (establishes CONFIG_UPDATE flow)
provides:
  - _safe_hex_color helper in widgets/calendar/widget.py
  - CalendarWidget reads time_color and date_color from settings on init
  - CalendarWidget CONFIG_UPDATE handler applies time_color and date_color via _safe_hex_color
affects: [any future widget subplot that needs hex color config reading in a subprocess]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "_safe_hex_color(hex_str, default_rgba) module-level helper wraps PIL.ImageColor.getrgb() with ValueError/AttributeError/TypeError guard — standard subprocess color parsing pattern (CLR-01)"
    - "Widget settings keys read via settings.get('key', '#default') with exact hardcoded defaults — zero visual change on v1.1 config upgrade"

key-files:
  created: []
  modified:
    - widgets/calendar/widget.py
    - tests/test_calendar_widget.py

key-decisions:
  - "_safe_hex_color except clause includes TypeError in addition to ValueError and AttributeError — PIL.ImageColor.getrgb() raises TypeError when given None (calls len() on arg), not AttributeError"

patterns-established:
  - "Pattern: subprocess color helper catches (ValueError, AttributeError, TypeError) — None input produces TypeError not AttributeError from PIL"

requirements-completed: [CAL-04, CAL-05, CLR-01]

# Metrics
duration: 2min
completed: 2026-03-27
---

# Phase 9 Plan 02: Calendar Color Config Summary

**CalendarWidget time_color and date_color config-driven via _safe_hex_color helper with PIL.ImageColor.getrgb() and TypeError/ValueError/AttributeError fallback protection**

## Performance

- **Duration:** ~2 min
- **Started:** 2026-03-27T22:01:46Z
- **Completed:** 2026-03-27T22:03:30Z
- **Tasks:** 2 (TDD: RED commit + GREEN commit)
- **Files modified:** 2

## Accomplishments
- Added `_safe_hex_color(hex_str, default_rgba)` module-level helper to `widgets/calendar/widget.py` using `PIL.ImageColor.getrgb()` with full exception guard
- Replaced hardcoded `(255, 255, 255, 255)` and `(220, 220, 220, 255)` color tuples in `CalendarWidget.__init__` with `settings.get()` calls through `_safe_hex_color`
- Added `time_color` and `date_color` handling to `run()` CONFIG_UPDATE block — calendar text colors update live on config file save
- Extended `tests/test_calendar_widget.py` with 12 new tests across 3 classes (TestSafeHexColor, TestCalendarColorInit, TestCalendarColorUpdate); all 20 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Add calendar color tests (TDD RED)** - `4002985` (test)
2. **Task 2: Add _safe_hex_color and config-driven colors (TDD GREEN)** - `c9ccdec` (feat)

_Note: TDD tasks have separate RED (test) and GREEN (implementation) commits_

## Files Created/Modified
- `widgets/calendar/widget.py` - Added `ImageColor` import, `_safe_hex_color` helper, replaced hardcoded colors, extended CONFIG_UPDATE handler
- `tests/test_calendar_widget.py` - Added TestSafeHexColor, TestCalendarColorInit, TestCalendarColorUpdate classes (12 new tests)

## Decisions Made
- `_safe_hex_color` except clause includes `TypeError` in addition to `ValueError` and `AttributeError`. The plan and research specified only `(ValueError, AttributeError)`, but `PIL.ImageColor.getrgb()` calls `len()` on its argument — passing `None` raises `TypeError`, not `AttributeError`. Auto-fixed during TDD GREEN verification (Rule 1 — bug).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Added TypeError to _safe_hex_color exception guard**
- **Found during:** Task 2 (TDD GREEN — test_none_returns_default failed)
- **Issue:** `PIL.ImageColor.getrgb(None)` raises `TypeError: object of type 'NoneType' has no len()` because PIL calls `len()` on the input string before doing any color parsing. The plan specified `except (ValueError, AttributeError)` which does not catch this.
- **Fix:** Changed `except (ValueError, AttributeError):` to `except (ValueError, AttributeError, TypeError):`
- **Files modified:** `widgets/calendar/widget.py`
- **Verification:** `test_none_returns_default` passes; all 20 tests green
- **Committed in:** `c9ccdec` (Task 2 feat commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 — bug)
**Impact on plan:** Necessary for correctness. Without TypeError guard, passing None as hex_str would crash the widget subprocess. No scope creep.

## Issues Encountered
- PIL TypeError from None input exposed a gap between the plan's exception list and PIL's actual behavior — caught by TDD RED/GREEN cycle as intended.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 9 complete: both plans done (09-01 bg_color host wiring + 09-02 calendar color config)
- All config-to-screen pipeline wiring for v1.2 is complete
- Calendar text colors (time_color, date_color) and host background (bg_color) are all config-driven with hot-reload support
- No blockers

## Self-Check: PASSED

- widgets/calendar/widget.py: FOUND
- tests/test_calendar_widget.py: FOUND
- .planning/phases/09-config-schema-host-hot-reload-wiring/09-02-SUMMARY.md: FOUND
- Commit 4002985 (test RED): FOUND
- Commit c9ccdec (feat GREEN): FOUND

---
*Phase: 09-config-schema-host-hot-reload-wiring*
*Completed: 2026-03-27*
