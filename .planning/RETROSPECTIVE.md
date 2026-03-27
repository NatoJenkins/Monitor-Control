# Retrospective: MonitorControl

---

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-27
**Phases:** 4 | **Plans:** 9

### What Was Built

1. PyQt6 host process owning Display 3 as a borderless always-on-top 1920×515 window with ClipCursor() enforcement and WTS session-unlock recovery
2. IPC pipeline: WidgetBase, ProcessManager, QueueDrainTimer, and Compositor enabling zero-Qt widget subprocesses at 50ms drain rate
3. config.json hot-reload system with QFileSystemWatcher atomic-replace handling, 100ms debounce, and live widget reconciliation
4. Pomodoro timer widget with full state machine, configurable durations, and command-file IPC for control panel integration
5. Calendar widget showing locale-aware date/time in 12h/24h format at 1Hz via Pillow
6. WinRT notification interceptor: surface Windows toast title/body/app name with auto-dismiss; backed by hardware-validated spike

### What Worked

- **Research-first on risky phases**: Phase 4's WinRT spike (04-01) ran before the widget build (04-02). This caught the `add_notification_changed` OSError on python.org Python early, before it could block widget implementation.
- **Hardware verification checkpoints per phase**: Each phase ended with real-hardware confirmation. This caught at least two bugs that would not have surfaced in automated tests: the `showFullScreen()` wrong-monitor bug (01-03) and the WM_ACTIVATEAPP alt-tab ClipCursor gap (03-02).
- **Deferred dependencies in widget subprocesses**: WinRT imports inside methods (`_get_winrt_listener()`) kept widget.py importable in test environments without WinRT installed — enabling a full unit test suite without hardware.
- **Atomic command-file IPC for Pomodoro controls**: Reusing the existing QFileSystemWatcher pattern (same as config hot-reload) kept the control channel simple and consistent with no new infrastructure.

### What Was Inefficient

- **Phase 1 VERIFICATION.md never created**: Only phases 2–4 have formal verification documents. This created a documentation gap that surfaced in the v1.0 audit and required the integration checker to retroactively confirm Phase 1 wiring.
- **SUMMARY.md frontmatter schema inconsistency**: All SUMMARY files use `provides:` instead of `requirements_completed:`. The gsd-tools `summary-extract` command returned empty results, requiring manual accomplishment extraction during milestone completion.
- **IPC-03 spec/implementation mismatch unresolved during development**: The drain-before-join requirement was written before the Windows deadlock constraint was discovered. The implementation is correct but the requirement was never amended, creating a misleading test name (`test_stop_widget_drains_queue_before_join`) that asserts behavior the code does not perform.
- **Nyquist validation not completed**: All 4 VALIDATION.md files remained in `draft` status throughout v1.0. Validation strategy documents were created but not executed.

### Patterns Established

- **Command-file IPC for control signals**: Write atomic JSON file → host `directoryChanged` → forward as typed message → widget `in_queue` poll. Clean separation from config update path.
- **Deferred WinRT imports**: Import WinRT inside methods, not at module top level. Enables test environments without WinRT installed.
- **Hardware verification checkpoint as final plan task**: Every phase's last plan task is a hardware verification step. Non-negotiable for a display-hardware project.
- **Spike plan before widget plan**: For any phase with unvalidated external API (WinRT, Win32), create a spike plan first. Phase 4's 04-01/04-02 split was the right call.
- **GC prevention via window attribute storage**: All long-lived Qt/native objects (message filters, watchers) stored as `window._attr` to prevent Python GC from collecting objects that Qt holds as C++ raw pointers.

### Key Lessons

1. **Write VERIFICATION.md for every phase, including Phase 1.** The audit flagged Phase 1 as a documentation gap. Even if hardware-verified, create the doc.
2. **Amend requirements when implementation deliberately diverges.** IPC-03 needed a note explaining the `proc.terminate()` design. Leaving it created a misleading test.
3. **Standardize SUMMARY.md frontmatter schema.** `provides:` vs `requirements_completed:` ambiguity caused gsd-tools to extract zero accomplishments during milestone completion.
4. **Complete VALIDATION.md before phase closure.** All four phases shipped with `draft` VALIDATION.md. Nyquist compliance was never achieved in v1.0.

### Cost Observations

- Sessions: ~9 (one per plan, roughly)
- Notable: Phase 4 plan 02 was the longest session (~4500s execution time); WinRT hardware debugging required multiple fix-verify cycles.

---

## Milestone: v1.1 — Startup & Distribution

**Shipped:** 2026-03-27
**Phases:** 3 | **Plans:** 3

### What Was Built

1. `shared/paths.py` canonical config path module with `get_config_path()` using `%LOCALAPPDATA%\MonitorControl\config.json` — shared between packaged exe and Python host (Phase 5, evolved in Phase 7)
2. HKCU Run key autostart via `winreg` stdlib — registry module, no-console launcher (`launch_host.pyw`), and Startup tab in the control panel with live registry read and immediate toggle (Phase 6)
3. Standalone `MonitorControl.exe` packaged with PyInstaller 6.19.0 onedir — no console window, custom blue "MC" icon (16/32/48/256px), reproducible `build/control_panel.spec` (Phase 7)

### What Worked

- **Smoke testing caught a real architectural bug**: The Phase 7 checkpoint smoke test revealed that the packaged exe and Python host were writing to different `config.json` files. Automated tests could not catch this — only a live exe-plus-host test exposed it. The fix (switching to `%LOCALAPPDATA%`) was a meaningful architectural improvement, not a workaround.
- **Single-plan phases kept scope tight**: All three v1.1 phases shipped as single plans. The narrow scope meant each plan could be fully verified before moving on, with no wave coordination overhead.
- **`contents_directory='.'` in the spec solved PyInstaller 6's path breaking change cleanly**: Setting this one parameter restored the expected flat layout without any changes to `shared/paths.py` (at the time). The research phase identified this before planning, so the plan was correct on the first attempt.

### What Was Inefficient

- **Config path architecture was designed for a scenario that didn't exist in testing**: The plan assumed both the exe and host would be in the same directory at distribution time. This was true for the final distribution but false for the dev/test scenario (exe in `dist/MonitorControl/`, host at project root). The gap wasn't caught until manual smoke testing. A prior discussion of the dev vs. distribution topology would have surfaced this earlier.
- **SUMMARY.md `one_liner` field not populated**: Same schema inconsistency as v1.0 — `gsd-tools summary-extract` returned null for all three phases. The field needs to be written at plan completion time.
- **v1.1 MILESTONE-AUDIT.md was never created**: The audit step was skipped because all phases were known-complete. The audit would have been fast but added formal validation of cross-phase integration (especially the paths/autostart/packaging chain).

### Patterns Established

- **`%LOCALAPPDATA%\MonitorControl\` as the canonical config directory**: Both the packaged exe and the Python host use this path. Future phases (including host packaging) must respect this location.
- **`contents_directory='.'` in all future PyInstaller specs**: Flat layout is required for `Path(__file__).parent.parent` to work correctly in frozen apps. Document this in all future spec files.
- **One-time migration in `get_config_path()`**: Copy from legacy location on first run rather than requiring manual migration. Invisible to the user.

### Key Lessons

1. **Test packaged exe against running host before approving checkpoint.** The config path mismatch would have been caught immediately if the smoke test protocol included "make a change in the control panel and verify the host reacts."
2. **Document the dev vs. distribution topology explicitly in research.** Phase 7's research focused on the PyInstaller mechanics but did not address "where does config.json live when exe and host are in different directories during development?"
3. **Write `one_liner` in SUMMARY.md at task completion time.** The field is empty in all v1.1 summaries. GSD milestone tooling depends on it for accomplishment extraction.

### Cost Observations

- Sessions: ~3 (one per phase, roughly; Phase 7 extended by the config path debugging)
- Notable: Phase 7's checkpoint was the most valuable part of the milestone — the smoke test caught an architectural gap that automated tests would never have found.

---

## Cross-Milestone Trends

### Documentation Completeness

| Milestone | Phases with VERIFICATION.md | Phases Nyquist-compliant |
|-----------|----------------------------|--------------------------|
| v1.0      | 3/4                        | 0/4                      |
| v1.1      | 3/3                        | 0/3                      |

### Hardware Verification Coverage

| Milestone | Phases hardware-verified | Hardware bugs caught |
|-----------|--------------------------|----------------------|
| v1.0      | 4/4                      | 3 (showFullScreen wrong monitor, WM_ACTIVATEAPP ClipCursor gap, WinRT IVectorView/None crash) |
| v1.1      | 1/3 (Phase 7 only)       | 1 (config path mismatch between packaged exe and Python host) |
