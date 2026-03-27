---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Startup & Distribution
status: completed
stopped_at: Completed 05-01-PLAN.md (Phase 5 Plan 01 — path resolution & null-guard)
last_updated: "2026-03-27T07:34:25.619Z"
last_activity: 2026-03-27 — Phase 5 Plan 01 executed (path resolution + null-guard)
progress:
  total_phases: 3
  completed_phases: 1
  total_plans: 1
  completed_plans: 1
  percent: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Keep productivity tooling off the primary monitors — widgets run persistently in a dedicated display the cursor cannot enter, requiring zero window management from the user.
**Current focus:** Phase 5 — Path Resolution & Freeze Safety

## Current Position

Phase: 5 of 7 (Path Resolution & Freeze Safety)
Plan: 1 of 1 in current phase (COMPLETE)
Status: Phase 5 complete — ready for Phase 6
Last activity: 2026-03-27 — Phase 5 Plan 01 executed (path resolution + null-guard)

Progress: [███░░░░░░░] 33% (v1.1 — 1/3 phases complete)

## Performance Metrics

**Velocity (v1.0):**
- Total plans completed: 9
- Average duration: ~30 min
- Total execution time: ~4.5 hours

**By Phase (v1.0):**

| Phase | Plans | Completed |
|-------|-------|-----------|
| 1. Host Infrastructure + Pipeline | 3 | 2026-03-26 |
| 2. Config System + Control Panel | 2 | 2026-03-27 |
| 3. Pomodoro + Calendar Widgets | 2 | 2026-03-27 |
| 4. Notification Interceptor | 2 | 2026-03-27 |

*v1.1 metrics will populate during execution*

## Accumulated Context

### Decisions

- [v1.0]: Qt must not be imported in widget subprocesses (spawn + Qt = crash on Windows) — Pillow for widget rendering
- [v1.0]: WinRT event subscription raises OSError; polling at 2s confirmed working; use winrt-* 3.2.1 not archived winsdk
- [v1.0]: proc.terminate() without join() is deliberate — join() deadlocks Qt main thread on Windows queue drain
- [v1.1]: Autostart via HKCU Run key (winreg stdlib), not Task Scheduler — simpler, appears in Windows Settings, no invisible-window BLOCKER risk
- [v1.1]: PyInstaller --onedir (not --onefile) — faster startup, no AV temp-extraction, multiprocessing-compatible
- [v1.1 Phase 5]: get_config_path() uses _PROJECT_ROOT = Path(__file__).resolve().parent.parent — cwd-independent, works under pythonw.exe, HKCU Run key, and PyInstaller
- [v1.1 Phase 5]: Null-guard placed before ALL imports in host/main.py — no window where print() can crash before stdout is safe

### Pending Todos

None.

### Blockers/Concerns

- [v1.0 carry]: IPC-03 spec language needs amendment — proc.terminate() design is deliberate but undocumented
- [v1.1 Phase 7]: winrt-* 3.2.1 has no PyInstaller community hooks — host packaging (v2) will need collect_submodules("winrt") iteration
- [v1.1 carry]: test_e2e_dummy::test_dummy_frame_received is a flaky integration test (pre-existing failure, unrelated to Phase 5)

## Session Continuity

Last session: 2026-03-27
Stopped at: Completed 05-01-PLAN.md (Phase 5 Plan 01 — path resolution & null-guard)
Resume file: None
