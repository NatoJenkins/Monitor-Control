---
phase: 01-host-infrastructure-pipeline
plan: "01"
subsystem: host-window
tags: [PyQt6, window-flags, display-targeting, multiprocessing, test-infrastructure]
dependency_graph:
  requires: []
  provides:
    - shared.message_schema.FrameData
    - host.window.HostWindow
    - host.win32_utils.find_target_screen
    - host.win32_utils.place_on_screen
    - host.main (entry point with __main__ guard)
  affects:
    - 01-02 (win32_utils extended with ClipCursor + WTS)
    - 01-03 (compositor, queue drain, process manager)
tech_stack:
  added:
    - PyQt6==6.10.2
    - pytest-mock>=3.12
  patterns:
    - Atomic window flag setting: all flags in ONE setWindowFlags() call before show()
    - Physical pixel matching: logical geometry * devicePixelRatio for DPI-aware display targeting
    - create() + setScreen + move + showFullScreen sequence for reliable cross-screen placement
    - AST-based static analysis for __main__ guard enforcement
key_files:
  created:
    - shared/message_schema.py
    - shared/__init__.py
    - host/__init__.py
    - host/window.py
    - host/win32_utils.py
    - host/main.py
    - widgets/__init__.py
    - tests/__init__.py
    - tests/conftest.py
    - tests/test_window.py
    - tests/test_win32_utils.py
    - tests/test_guard.py
    - requirements.txt
    - pytest.ini
    - .gitignore
  modified: []
decisions:
  - "FrameData dataclass is pure Python (no Qt/win32 imports) so widget subprocesses can import it without pulling in Qt"
  - "find_target_screen multiplies logical geometry by devicePixelRatio rather than using physicalSize() to stay consistent with Qt coordinate space and avoid OS-level scaling ambiguity"
  - "place_on_screen calls window.create() first to force native HWND before setScreen — required for windowHandle() to be non-None at placement time"
  - ".gitignore added as deviation (Rule 2) to prevent __pycache__ from polluting untracked state"
metrics:
  duration_seconds: 248
  completed_date: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 15
  files_modified: 0
  tests_added: 5
  tests_passing: 5
requirements_satisfied:
  - HOST-01
  - HOST-02
  - HOST-05
---

# Phase 01 Plan 01: Host Window Foundation Summary

**One-liner:** Borderless always-on-top PyQt6 HostWindow targeting Display 3 via devicePixelRatio physical pixel matching, with atomic flags and __main__ guard enforced by AST test.

## What Was Built

The complete host window foundation establishing the project skeleton. A PyQt6 `HostWindow` widget sets three window flags (`FramelessWindowHint | WindowStaysOnTopHint | Tool`) in a single `setWindowFlags()` call in `__init__`, before any `show()` call — this is the HOST-02 BLOCKER pattern. The `find_target_screen()` function identifies Display 3 by multiplying logical geometry by `devicePixelRatio()` to compare against physical pixel dimensions (1920x515), satisfying HOST-01. The `place_on_screen()` function uses `create() + windowHandle().setScreen() + move() + showFullScreen()` for reliable cross-screen placement. The `host/main.py` entry point has an `if __name__ == "__main__":` guard with explicit `multiprocessing.set_start_method("spawn")`, satisfying HOST-05.

## Task Breakdown

| Task | Name | Commit | Key Files |
|------|------|--------|-----------|
| 1 | Project skeleton, shared types, test infrastructure | 0123a64 | shared/message_schema.py, tests/conftest.py, tests/test_*.py, requirements.txt, pytest.ini |
| 2 | HostWindow, display targeting, window flags, main entry | 21365e1 | host/window.py, host/win32_utils.py, host/main.py, .gitignore |

## Test Results

All 5 unit tests pass:
- `test_window_flags_set_before_show` — HOST-02: flags include all three before show()
- `test_window_placement` — HOST-01: place_on_screen calls move(topLeft) + showFullScreen()
- `test_find_target_screen_by_physical_pixels` — HOST-01: correct screen returned for 1920x515
- `test_find_target_screen_returns_none` — HOST-01: None returned when no match
- `test_main_guard_exists` — HOST-05: AST-verified __main__ guard present

## Decisions Made

1. **FrameData is pure Python** — No Qt or win32 imports in `shared/message_schema.py`. Widget subprocesses import `FrameData` to build payloads; if Qt leaked in, the subprocess import would crash on Windows spawn mode.

2. **devicePixelRatio for physical pixel matching** — `find_target_screen` uses `int(logical_geo.width() * dpr)` rather than `QScreen.physicalSize()` (which returns millimeters) or platform-specific APIs. This stays within Qt's coordinate model and handles mixed-DPI layouts correctly.

3. **window.create() before setScreen** — Without `create()`, the native HWND doesn't exist yet and `windowHandle()` returns None. The `create()` call forces native window creation so `setScreen()` can be called reliably.

4. **Explicit spawn method in __main__** — `multiprocessing.set_start_method("spawn")` is placed in the `__main__` block rather than in `main()`. This documents intent and ensures it only runs when the process is the root host, not in any subprocess.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] PyQt6 not installed in execution environment**
- **Found during:** Task 2 verification
- **Issue:** `ModuleNotFoundError: No module named 'PyQt6'` when running tests — PyQt6 and pytest-mock were not installed in the Python 3.11.9 environment
- **Fix:** `python -m pip install "PyQt6==6.10.2" "pytest-mock>=3.12"` — exact versions from requirements.txt
- **Files modified:** None (system-level install)
- **Impact:** Tests that imported PyQt6 could not be collected; fixed before Task 2 verification

**2. [Rule 2 - Missing critical] Added .gitignore**
- **Found during:** Task 2 commit
- **Issue:** `__pycache__/` directories appeared as untracked in git status after pytest run — no .gitignore existed
- **Fix:** Created `.gitignore` with Python standard patterns (pycache, .venv, build artifacts)
- **Files modified:** .gitignore (created)
- **Commit:** 21365e1 (included with Task 2)

## Requirements Satisfied

| Requirement | Status | Verification |
|-------------|--------|--------------|
| HOST-01 | DONE | test_find_target_screen_by_physical_pixels + test_window_placement pass |
| HOST-02 | DONE | test_window_flags_set_before_show passes |
| HOST-05 | DONE | test_main_guard_exists passes (AST check) |

## What Comes Next

- **01-02:** Extend `host/win32_utils.py` with `ClipCursor()`, `WTSRegisterSessionNotification`, and `QAbstractNativeEventFilter` for session lock/unlock recovery (HOST-04)
- **01-03:** Add `ProcessManager`, `QueueDrainTimer`, slot compositor in `paintEvent`, and dummy widget for end-to-end IPC validation (HOST-03, IPC-01 through IPC-04)
