---
phase: 01-host-infrastructure-pipeline
plan: "02"
subsystem: infra
tags: [win32, ctypes, ClipCursor, WTS, PyQt6, QAbstractNativeEventFilter]

# Dependency graph
requires:
  - phase: 01-host-infrastructure-pipeline
    plan: "01"
    provides: "host/win32_utils.py with find_target_screen/place_on_screen; host/main.py startup scaffold; host/window.py HostWindow"
provides:
  - "ClipCursor enforcement confining cursor to primary monitors, excluding Display 3"
  - "WTS session-unlock recovery via WTSRegisterSessionNotification + Win32MessageFilter"
  - "WM_DISPLAYCHANGE recovery via same Win32MessageFilter"
  - "RECT ctypes structure and apply_clip_cursor / release_clip_cursor helpers"
  - "compute_allowed_rect with correct Qt off-by-one fix (left()+width())"
  - "5 new tests proving rect exclusion, ClipCursor call, unlock triggers, displaychange triggers, lock does NOT trigger"
affects:
  - 01-host-infrastructure-pipeline/01-03
  - validation

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Win32MessageFilter as QAbstractNativeEventFilter installed on QApplication for native MSG interception"
    - "WTS session notification registration before event loop to recover ClipCursor after Win+L unlock"
    - "Store native event filter on window attribute to prevent GC during app lifetime"
    - "Use ctypes.wintypes.MSG.from_address(message.__int__()) to decode native MSG pointer"

key-files:
  created: []
  modified:
    - host/win32_utils.py
    - host/main.py
    - tests/test_win32_utils.py

key-decisions:
  - "Use combined.left()+combined.width() not combined.right() — Qt QRect.right() is left+width-1 (off by one), using it would leave a 1-pixel gap at the right and bottom edges of the allowed cursor region"
  - "b'windows_generic_MSG' (bytes literal) is required for nativeEventFilter event_type comparison on Windows; str comparison silently never matches"
  - "WTS_SESSION_LOCK (0x7) deliberately does NOT re-apply ClipCursor — only UNLOCK (0x8) does, preventing unnecessary ClipCursor calls on lock"
  - "msg_filter stored as window._msg_filter to prevent Python GC from collecting the filter object while QApplication holds only a C++ reference"

patterns-established:
  - "Win32MessageFilter pattern: subclass QAbstractNativeEventFilter, install on app, decode MSG with ctypes, invoke callback"
  - "WTS registration pattern: call WTSRegisterSessionNotification with window HWND before app.exec()"

requirements-completed: [HOST-04]

# Metrics
duration: 2min
completed: "2026-03-26"
---

# Phase 1 Plan 02: ClipCursor + WTS Session Recovery Summary

**ctypes ClipCursor wrapper with WTS session-unlock and WM_DISPLAYCHANGE auto-recovery via QAbstractNativeEventFilter, enforcing cursor confinement to primary monitors excluding Display 3**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-26T00:39:14Z
- **Completed:** 2026-03-26T00:41:18Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Appended RECT structure, apply_clip_cursor, release_clip_cursor, compute_allowed_rect, register_session_notifications, unregister_session_notifications, and Win32MessageFilter to host/win32_utils.py without removing existing 01-01 code
- compute_allowed_rect correctly uses left()+width() / top()+height() (not Qt's off-by-one right()/bottom()) ensuring the cursor boundary pixel is included
- Win32MessageFilter intercepts WM_WTSSESSION_CHANGE (unlock only, not lock) and WM_DISPLAYCHANGE to re-apply ClipCursor, using b"windows_generic_MSG" bytes literal for correct Windows event_type matching
- host/main.py startup sequence wired: compute_allowed_rect, apply_clip_cursor, register_session_notifications, Win32MessageFilter installed, filter pinned to window._msg_filter
- 5 tests cover: allowed rect excludes Display 3 with correct edges, ClipCursor called, session unlock triggers re-apply, displaychange triggers re-apply, session lock does NOT trigger re-apply — all pass

## Task Commits

Each task was committed atomically:

1. **Task 1: ClipCursor wrapper, RECT computation, WTS registration, Win32MessageFilter** - `1b92f8b` (feat)
2. **Task 2: Wire ClipCursor and WTS into host/main.py startup sequence** - `428dfb2` (feat)

## Files Created/Modified

- `host/win32_utils.py` - Appended: RECT, apply_clip_cursor, release_clip_cursor, compute_allowed_rect, register_session_notifications, unregister_session_notifications, Win32MessageFilter
- `host/main.py` - Updated imports and startup sequence: ClipCursor enforcement + WTS + Win32MessageFilter wired after place_on_screen
- `tests/test_win32_utils.py` - Added TestComputeAllowedRect, TestApplyClipCursor, TestWin32MessageFilter with 5 new tests

## Decisions Made

- **Qt QRect off-by-one:** QRect.right() returns left+width-1 and QRect.bottom() returns top+height-1. compute_allowed_rect uses left()+width() and top()+height() to get the actual right and bottom pixel coordinates, preventing a 1-pixel gap at the cursor boundary.
- **Bytes vs str in nativeEventFilter:** event_type on Windows is b"windows_generic_MSG" (bytes), not a str. Using a str would silently never match, breaking all MSG interception.
- **Lock vs unlock:** Only WTS_SESSION_UNLOCK (0x8) re-applies ClipCursor. WTS_SESSION_LOCK (0x7) does not — ClipCursor is still active at lock time, only broken on unlock/desktop switch.
- **GC prevention:** window._msg_filter holds a strong Python reference to the filter. Without it, Python GC could collect the object while QApplication holds only a C++ pointer, causing a crash or silent failure.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- HOST-04 requirement fully satisfied: cursor confined at startup and auto-recovered after Win+L unlock and display change
- host/win32_utils.py exports all declared artifacts: apply_clip_cursor, release_clip_cursor, compute_allowed_rect, register_session_notifications, unregister_session_notifications, Win32MessageFilter, RECT
- Ready for 01-03: ProcessManager and QueueDrainTimer

---
*Phase: 01-host-infrastructure-pipeline*
*Completed: 2026-03-26*
