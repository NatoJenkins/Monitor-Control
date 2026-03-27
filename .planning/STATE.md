---
gsd_state_version: 1.0
milestone: v1.1
milestone_name: Startup & Distribution
status: completed
stopped_at: Completed 07-01-PLAN.md (Phase 7 Plan 01 — control panel packaging)
last_updated: "2026-03-27T15:05:09.472Z"
last_activity: 2026-03-27 — Phase 7 Plan 01 executed (PyInstaller packaging, custom icon, LOCALAPPDATA config path)
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Keep productivity tooling off the primary monitors — widgets run persistently in a dedicated display the cursor cannot enter, requiring zero window management from the user.
**Current focus:** v1.1 COMPLETE — all phases done

## Current Position

Phase: 7 of 7 (Control Panel Packaging) — COMPLETE
Plan: 1 of 1 in current phase (COMPLETE)
Status: v1.1 milestone complete — MonitorControl.exe distributed as standalone folder
Last activity: 2026-03-27 — Phase 7 Plan 01 executed (PyInstaller packaging, custom icon, LOCALAPPDATA config path)

Progress: [██████████] 100% (v1.1 — 3/3 phases complete)

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

| Phase 05 P01 | ~30min | 4 tasks | 6 files |
| Phase 06 P01 | 5 | 4 tasks | 5 files |
| Phase 07 P01 | ~45min | 3 tasks | 8 files |

## Accumulated Context

### Decisions

- [v1.0]: Qt must not be imported in widget subprocesses (spawn + Qt = crash on Windows) — Pillow for widget rendering
- [v1.0]: WinRT event subscription raises OSError; polling at 2s confirmed working; use winrt-* 3.2.1 not archived winsdk
- [v1.0]: proc.terminate() without join() is deliberate — join() deadlocks Qt main thread on Windows queue drain
- [v1.1]: Autostart via HKCU Run key (winreg stdlib), not Task Scheduler — simpler, appears in Windows Settings, no invisible-window BLOCKER risk
- [v1.1]: PyInstaller --onedir (not --onefile) — faster startup, no AV temp-extraction, multiprocessing-compatible
- [v1.1 Phase 5]: get_config_path() uses _PROJECT_ROOT = Path(__file__).resolve().parent.parent — cwd-independent, works under pythonw.exe, HKCU Run key, and PyInstaller
- [v1.1 Phase 5]: Null-guard placed before ALL imports in host/main.py — no window where print() can crash before stdout is safe
- [Phase 06]: Function-level imports in _load_values and _on_autostart_toggled prevent winreg from importing at module load time, enabling test isolation
- [Phase 06]: blockSignals guard wraps setChecked() in _load_values() to prevent spurious registry writes on every panel open (STRT-03)
- [Phase 07]: contents_directory='.' in PyInstaller EXE() prevents _internal/ nesting that breaks _PROJECT_ROOT resolution in shared/paths.py
- [Phase 07]: Config path switched from _PROJECT_ROOT/config.json to %LOCALAPPDATA%\MonitorControl\config.json so packaged exe and Python host share one file
- [Phase 07]: PyInstaller 6.19.0 installed as build-time tool only — not added to requirements.txt
- [Phase 07]: Autostart enable/disable deferred from packaged exe (v2, HPKG-02) — pythonw.exe not beside MonitorControl.exe; fails gracefully via OSError catch

### Pending Todos

None.

### Blockers/Concerns

- [v1.0 carry]: IPC-03 spec language needs amendment — proc.terminate() design is deliberate but undocumented
- [v1.1 Phase 7]: winrt-* 3.2.1 has no PyInstaller community hooks — host packaging (v2) will need collect_submodules("winrt") iteration
- [v1.1 carry]: test_e2e_dummy::test_dummy_frame_received is a flaky integration test (pre-existing failure, unrelated to Phase 5)

## Session Continuity

Last session: 2026-03-27T14:30:00.000Z
Stopped at: Completed 07-01-PLAN.md (Phase 7 Plan 01 — control panel packaging)
Resume file: None
