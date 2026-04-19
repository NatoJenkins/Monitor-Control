---
phase: 05-path-resolution-freeze-safety
plan: "01"
subsystem: infra

tags: [python, pathlib, pythonw, sys.stdout, null-guard, config-path]

# Dependency graph
requires: []
provides:
  - shared/paths.py with get_config_path() resolving config.json from __file__ anchor
  - sys.stdout/sys.stderr null-guard at top of host/main.py for pythonw.exe safety
  - Both entry points (host/main.py, control_panel/__main__.py) using get_config_path()
  - 7-test suite validating INFRA-01 (path resolution) and INFRA-02 (null-guard)
affects: [06-autostart, 07-pyinstaller-packaging]

# Tech tracking
tech-stack:
  added: []
  patterns: [shared/ canonical path resolution via __file__ anchor, null-guard at module top]

key-files:
  created:
    - shared/paths.py
    - tests/test_paths.py
  modified:
    - host/main.py
    - control_panel/__main__.py

key-decisions:
  - "get_config_path() uses _PROJECT_ROOT = Path(__file__).resolve().parent.parent so it is cwd-independent regardless of how Python is launched"
  - "Null-guard inserted before all other imports in host/main.py so no print() call can execute before stdout/stderr are safe"

patterns-established:
  - "All config path references must go through shared.paths.get_config_path() — no bare 'config.json' strings in entry points"
  - "pythonw.exe null-guard pattern: check sys.stdout is None and replace with open(os.devnull, 'w') at the very top of the entry point"

requirements-completed: [INFRA-01, INFRA-02]

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 5 Plan 01: Path Resolution & Freeze Safety Summary

**Absolute config path via shared/paths.py get_config_path() and pythonw.exe null-guard in host/main.py eliminate cwd-dependent launch failures and stdout crash**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T07:26:28Z
- **Completed:** 2026-03-27T07:31:00Z
- **Tasks:** 2
- **Files modified:** 4 (plus 2 created)

## Accomplishments

- Created `shared/paths.py` with `get_config_path()` anchored to `__file__` — returns the same absolute path regardless of process cwd, pythonw.exe context, HKCU Run key, or PyInstaller
- Added sys.stdout/sys.stderr null-guard at the very top of `host/main.py` before all other imports, protecting all 12 print() calls across host/main.py and host/config_loader.py
- Replaced both bare `"config.json"` occurrences in `host/main.py` (lines 87 and 92) and the one in `control_panel/__main__.py` with `get_config_path()` calls
- 7-test suite in `tests/test_paths.py` validates INFRA-01 (absolute path, cwd independence, project root detection, no bare strings) and INFRA-02 (null-guard for stdout and stderr)
- Full regression suite: 112 tests pass, 0 failures from Phase 5 changes

## Task Commits

Each task was committed atomically:

1. **Task 1: Create test scaffold and implement shared/paths.py + null-guard** - `5bfb8e7` (feat)
2. **Task 2: Full regression suite and cleanup** - `4c62a9b` (chore)

**Plan metadata:** *(pending final docs commit)*

_Note: TDD task — RED phase confirmed ModuleNotFoundError; GREEN phase all 7 pass._

## Files Created/Modified

- `shared/paths.py` — Canonical config path resolver; exports `get_config_path()` returning `_PROJECT_ROOT / "config.json"` with `_PROJECT_ROOT = Path(__file__).resolve().parent.parent`
- `tests/test_paths.py` — 7 tests: 5 for INFRA-01 (path correctness, cwd independence, project root, no bare strings in both entry points), 2 for INFRA-02 (null-guard stdout/stderr)
- `host/main.py` — Added null-guard block after `import sys/os`; added `from shared.paths import get_config_path`; replaced `ConfigLoader("config.json", ...)` with `_cfg = get_config_path(); ConfigLoader(str(_cfg), ...)`; replaced `os.path.dirname(os.path.abspath("config.json"))` with `str(_cfg.parent)`
- `control_panel/__main__.py` — Added `from shared.paths import get_config_path`; replaced `"config.json"` with `str(get_config_path())`

## Decisions Made

- Used `_PROJECT_ROOT = Path(__file__).resolve().parent.parent` as a module-level constant (not computed on every call) — correct because `__file__` is fixed at module load time and avoids repeated filesystem resolution
- Null-guard placed BEFORE all other imports in `host/main.py` so there is no window during import-time print() calls where stdout could still be None

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- **Pre-existing integration test failure:** `tests/test_e2e_dummy.py::test_dummy_frame_received` was already failing before Phase 5 changes (confirmed by reverting to previous commit). This is a flaky `@pytest.mark.integration` test that uses real multiprocessing; the subprocess does not push frames within the 0.5s window in this environment. Documented in `deferred-items.md`. Not caused by Phase 5 changes.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- INFRA-01 and INFRA-02 both satisfied — both entry points now resolve config path correctly from any launch context
- Phase 6 (HKCU Run key autostart) can proceed: the config path will resolve correctly when the process starts from `C:\Windows\System32`
- Phase 7 (PyInstaller packaging) can proceed: `get_config_path()` will work correctly in a --onedir bundle since `__file__` anchor is valid in both development and packaged contexts
- Blocker removed: sys.stdout null-guard means `console=False` in PyInstaller spec will not cause crashes

---
*Phase: 05-path-resolution-freeze-safety*
*Completed: 2026-03-27*

## Self-Check: PASSED

- FOUND: shared/paths.py
- FOUND: tests/test_paths.py
- FOUND: host/main.py
- FOUND: control_panel/__main__.py
- FOUND commit: 5bfb8e7 (feat: Task 1)
- FOUND commit: 4c62a9b (chore: Task 2)
- pytest tests/test_paths.py: 7 passed
- get_config_path() returns absolute path: E:\ClaudeCodeProjects\MonitorControl\config.json
- grep get_config_path in host/main.py: 2 occurrences
- grep get_config_path in control_panel/__main__.py: 2 occurrences
- grep "sys.stdout = open(os.devnull" in host/main.py: 1 occurrence
