---
phase: 07-control-panel-packaging
plan: "01"
subsystem: infra
tags: [pyinstaller, packaging, ico, pyqt6, windows, exe, onedir]

# Dependency graph
requires:
  - phase: 06-autostart-toggle
    provides: Startup tab and autostart registry module integrated into control panel
  - phase: 05-path-resolution-freeze-safety
    provides: shared/paths.py with get_config_path() — updated in this phase for packaged exe compatibility

provides:
  - Standalone MonitorControl.exe (PyInstaller 6 onedir) with no console window and custom icon
  - build/control_panel.spec — reproducible PyInstaller spec file
  - build/icon.ico — multi-size ICO (16/32/48/256px) with "MC" logo
  - build/make_icon.py — icon generation script
  - Null-guarded control_panel/__main__.py (stdout/stderr safe in windowed mode)
  - %LOCALAPPDATA%\MonitorControl\config.json as the shared config path used by both exe and host
  - tests/test_packaging.py — 4 precondition tests (spec, icon, ico validity, null-guard)

affects:
  - host-packaging (v2) — host packaging will need collect_submodules("winrt") and similar spec patterns
  - any future phase reading config.json — path is now LOCALAPPDATA-based, not project-root-based

# Tech tracking
tech-stack:
  added:
    - PyInstaller 6.19.0 (build-time only, not in requirements.txt)
    - Pillow (icon generation via make_icon.py)
  patterns:
    - PyInstaller onedir with contents_directory='.' to prevent _internal/ path nesting
    - Null-guard (stdout/stderr to devnull) placed before all non-stdlib imports in frozen entry points
    - %LOCALAPPDATA% for shared config so host process and packaged exe share one file

key-files:
  created:
    - build/control_panel.spec
    - build/icon.ico
    - build/make_icon.py
    - tests/test_packaging.py
  modified:
    - control_panel/__main__.py (null-guard added)
    - shared/paths.py (get_config_path() switched to LOCALAPPDATA)
    - tests/test_paths.py (updated for new config path)
    - tests/test_config_loader.py (updated for new config path)
    - .gitignore (selective build/ tracking)

key-decisions:
  - "PyInstaller onedir (not onefile): faster startup, no AV temp-extraction, multiprocessing-compatible"
  - "contents_directory='.' in EXE() prevents _internal/ nesting that breaks _PROJECT_ROOT resolution"
  - "Config path moved to %LOCALAPPDATA%\\MonitorControl\\config.json so packaged exe and Python host share one file"
  - "PyInstaller stays out of requirements.txt — it is a build-time tool only"
  - "Autostart enable/disable fails gracefully from packaged exe (pythonw.exe not beside MonitorControl.exe) — deferred to v2 (HPKG-02)"

patterns-established:
  - "Null-guard pattern: redirect sys.stdout/stderr to devnull before any non-stdlib import in windowed frozen entry points"
  - "Spec file pattern: use SPECPATH + pathex=[project_root] to keep all paths relative and reproducible from clean checkout"
  - "Targeted .gitignore: replace blanket build/ with per-extension PyInstaller temp artifact patterns to track spec + icon"

requirements-completed: [PKG-01, PKG-02, PKG-03, PKG-04]

# Metrics
duration: ~45min (including manual verification and config path fix)
completed: 2026-03-27
---

# Phase 7 Plan 01: Control Panel Packaging Summary

**MonitorControl.exe packaged with PyInstaller 6 onedir — no console, custom "MC" icon, config shared via %LOCALAPPDATA%\MonitorControl\config.json**

## Performance

- **Duration:** ~45 min (including human-verify checkpoint and config path fix)
- **Started:** 2026-03-27T13:45:00Z (estimated)
- **Completed:** 2026-03-27
- **Tasks:** 3 (Task 1 auto, Task 2 auto, Task 3 checkpoint:human-verify — approved)
- **Files modified:** 8

## Accomplishments

- Packaged control panel as `dist/MonitorControl/MonitorControl.exe` using PyInstaller 6.19.0 onedir mode
- No console window on launch; custom dark "MC" cornflower-blue icon visible in Explorer and taskbar
- Discovered and fixed config.json path split: both exe and Python host now write to `%LOCALAPPDATA%\MonitorControl\config.json`
- All 4 packaging precondition tests pass; full regression suite (131 tests) green after fix

## Task Commits

Each task was committed atomically:

1. **Task 1: Wave 0 — test scaffold and icon generation** - `a105ee8` (test)
2. **Task 2: Spec file, null-guard, and gitignore** - `14a9bf1` (feat)
3. **Task 3: Build exe + config path fix** - `eff6c06` (fix — see Deviations)

## Files Created/Modified

- `tests/test_packaging.py` — 4 precondition tests: spec exists, icon exists, ico validity, null-guard order
- `build/make_icon.py` — Pillow script generating 16/32/48/256px ICO with dark background and "MC" text
- `build/icon.ico` — Generated multi-size ICO file (7418 bytes, 4 sizes)
- `build/control_panel.spec` — PyInstaller 6.x onedir spec with `contents_directory='.'`, `console=False`, icon path
- `control_panel/__main__.py` — Null-guard (stdout/stderr -> devnull) added before PyQt6 imports
- `shared/paths.py` — `get_config_path()` updated to use `%LOCALAPPDATA%\MonitorControl\config.json` with one-time migration
- `tests/test_paths.py` — Updated assertions for new LOCALAPPDATA-based config path
- `tests/test_config_loader.py` — Updated assertions for new LOCALAPPDATA-based config path
- `.gitignore` — Replaced bare `build/` with targeted PyInstaller temp artifact patterns

## Decisions Made

- `contents_directory='.'` in the PyInstaller `EXE()` call is critical: without it, PyInstaller 6 places bundled files in `_internal/`, breaking `Path(__file__).parent.parent` resolution in shared/paths.py.
- Config path moved from `_PROJECT_ROOT / "config.json"` to `%LOCALAPPDATA%\MonitorControl\config.json` because `_PROJECT_ROOT` inside the frozen bundle resolves to the bundle's internal temp directory, not the exe's directory. LOCALAPPDATA provides a stable, user-writable location both processes can find.
- PyInstaller kept out of requirements.txt — it is a build-time tool with no runtime role.
- Autostart enable/disable intentionally left non-functional in the packaged exe (pythonw.exe not beside MonitorControl.exe). Fails gracefully via existing OSError catch. Deferred to v2 as HPKG-02.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ICO generation: single save call with sizes= parameter**
- **Found during:** Task 1 (icon generation)
- **Issue:** Initial make_icon.py used `append_images` incorrectly, producing an ICO with count=1 instead of count>=3, failing `test_icon_file_is_valid_ico`
- **Fix:** Rewrote save call to use `sizes=SIZES` directly on the base image list so Pillow writes all four sizes into one ICO correctly
- **Files modified:** `build/make_icon.py`, `build/icon.ico`
- **Verification:** `pytest tests/test_packaging.py::test_icon_file_is_valid_ico` passed
- **Committed in:** `a105ee8` (Task 1 commit)

**2. [Rule 1 - Bug] Config path mismatch: packaged exe and Python host wrote different config.json files**
- **Found during:** Task 3 manual verification (checkpoint)
- **Issue:** `shared/paths.py` resolved `_PROJECT_ROOT` from `__file__` inside the PyInstaller bundle, which points to the bundle's internal temp dir, not the exe's location. The exe silently wrote to a different config.json than the Python host.
- **Fix:** Updated `get_config_path()` to use `os.environ["LOCALAPPDATA"] / "MonitorControl" / "config.json"` with a one-time migration from the project-root config.json on first run. Both processes now share one file.
- **Files modified:** `shared/paths.py`, `tests/test_paths.py`, `tests/test_config_loader.py`
- **Verification:** User confirmed exe and host communicate via shared config after fix. Full test suite green (131 tests).
- **Committed in:** `eff6c06`

---

**Total deviations:** 2 auto-fixed (2 x Rule 1 - Bug)
**Impact on plan:** Both fixes essential for correctness. No scope creep.

## Issues Encountered

None beyond the two bugs documented above.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- Phase 7 (v1.1) is complete. MonitorControl.exe is distributable as a folder.
- Host packaging (v2) will require PyInstaller hooks for winrt-* 3.2.1 (no community hooks exist yet — see `collect_submodules("winrt")` iteration pattern from PyInstaller docs).
- Autostart enable/disable from the packaged exe is deferred to v2 (HPKG-02) — the exe reads autostart state correctly but cannot write it because pythonw.exe is not beside MonitorControl.exe.

---
*Phase: 07-control-panel-packaging*
*Completed: 2026-03-27*
