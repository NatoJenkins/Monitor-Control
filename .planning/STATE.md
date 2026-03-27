---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Configurable Colors
status: executing
stopped_at: Completed 09-01-PLAN.md
last_updated: "2026-03-27T22:00:37.783Z"
last_activity: 2026-03-27 — 09-01 complete (bg_color config schema + hot-reload wiring)
progress:
  total_phases: 4
  completed_phases: 1
  total_plans: 4
  completed_plans: 3
  percent: 38
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Keep productivity tooling off the primary monitors — widgets run persistently in a dedicated display the cursor cannot enter, requiring zero window management from the user.
**Current focus:** v1.2 Configurable Colors — roadmap defined, ready to plan Phase 8

## Current Position

Phase: 9 — Config Schema + Host Hot-Reload Wiring
Plan: 01 (complete)
Status: Phase 09 in progress — 1 of 2 plans done
Last activity: 2026-03-27 — 09-01 complete (bg_color config schema + hot-reload wiring)

Progress: [███░░░░░░░] 38%

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
| Phase 08 P01 | 4 | 2 tasks | 2 files |
| Phase 08 P02 | 3 | 2 tasks | 5 files |
| Phase 09 P01 | 2min | 2 tasks | 3 files |

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
- [v1.2 Roadmap]: ColorPickerWidget lives only in control_panel/color_picker.py — never in shared/ (would import PyQt6 in widget subprocesses, crashes on Windows spawn)
- [v1.2 Roadmap]: Widget transparency and host bg fill are one atomic change (Phase 8) — partial migration causes host fill to be silently overwritten on every compositor pass
- [v1.2 Roadmap]: colorsys.hls_to_rgb(h, l, s) takes H, L, S order — use a named wrapper or QColor.fromHslF exclusively to avoid silent wrong-color output
- [v1.2 Roadmap]: QColor.hslHueF() returns -1 for achromatic colors — track _hue separately in ColorPickerWidget state
- [v1.2 Roadmap]: All new config keys use .get() with exact hardcoded defaults — never bracket access on new keys (CLR-01)
- [v1.2 Roadmap]: Widget subprocesses use PIL.ImageColor.getrgb() for hex-to-RGBA; must be wrapped in _safe_hex_color() fallback to prevent subprocess crash on invalid config
- [Phase 08-01]: QColor.fromHslF used exclusively over colorsys — eliminates HLS argument-order trap, no new pip dependencies
- [Phase 08-01]: _hue stored as private float independent of QColor.hslHueF() — QColor returns -1 for achromatic colors, tracking separately preserves hue across gray round-trips
- [Phase 08-01]: sliderReleased (not valueChanged) connected to _emit_color_changed — programmatic setValue() in _sync_all_from_state() does not trigger emissions
- [Phase 08-02]: set_bg_color() uses QColor.isValid() to reject invalid hex strings — leaves _bg_qcolor unchanged, consistent with QColor validation pattern from 08-01
- [Phase 08-02]: All four file changes (host fill + 3 widget transparency) committed atomically — partial migration silently overwrites host fill on every compositor pass
- [Phase 09-01]: ConfigLoader constructed without after_reload; _after_reload assigned post-construction to avoid forward reference — config_loader must be bound before lambda can close over it
- [Phase 09-01]: reapply_clip() called first in _after_reload to preserve HOST-04 behavior before bg_color update
- [Phase 09-01]: window.set_bg_color() called between load() and apply_config() on initial startup — bg renders before widgets are composited

### Pending Todos

None.

### Blockers/Concerns

- [v1.0 carry]: IPC-03 spec language needs amendment — proc.terminate() design is deliberate but undocumented
- [v1.1 Phase 7]: winrt-* 3.2.1 has no PyInstaller community hooks — host packaging (v2) will need collect_submodules("winrt") iteration
- [v1.1 carry]: test_e2e_dummy::test_dummy_frame_received is a flaky integration test (pre-existing failure, unrelated to Phase 5)

## Session Continuity

Last session: 2026-03-27T21:58:47Z
Stopped at: Completed 09-01-PLAN.md
Resume file: None
