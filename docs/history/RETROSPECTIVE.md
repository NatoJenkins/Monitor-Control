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
2. Startup folder shortcut autostart — `.lnk` in `shell:startup`, no-console launcher (`launch_host.pyw`), and Startup tab in the control panel with immediate toggle (Phase 6, reworked post-ship)
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

### Post-Ship Bugs (discovered after v1.1 tag)

**Bug 1: Packaged exe silently failed to enable autostart**
- **Symptom:** Clicking "Start at login" in the packaged exe appeared to work (checkbox toggled) but nothing was written to the registry. Autostart never activated.
- **Root cause:** `_build_command()` raised `RuntimeError` when `sys.frozen` was True (the exe can't derive `launch_host.pyw` location via `__file__`). The exception handler in `_on_autostart_toggled` only caught `OSError`, so the `RuntimeError` was silently eaten by Qt's signal dispatch. The checkbox showed as checked, the registry key was never written.
- **Fix:** Persist the full command string to `%LOCALAPPDATA%\MonitorControl\host_command.txt` when autostart is enabled from the Python source. The frozen exe reads this file instead of deriving the path. Also catch `RuntimeError` alongside `OSError` in the toggle handler so failures show a dialog.
- **Commits:** `a3965a5`, `b8fe518`

**Bug 2: Windows 11 ignored HKCU Run key despite correct registry state**
- **Symptom:** Registry key existed with correct command, `StartupApproved\Run` had `0x02` (enabled), all four policy keys (`SupportUwpStartupTasks`, etc.) were correct — but Windows Settings showed "Off" and the command was never executed on boot. No `launch.log` was created, confirming Windows never attempted to run it.
- **Root cause:** Known Windows 11 reliability issue with the `HKCU\Run` + `StartupApproved\Run` mechanism. Extensive research identified profile corruption from KB updates, dynamic idle-wait delays (`Explorer\Serialize`), and Settings app caching as contributing factors. The exact trigger on this machine was not isolated, but the mechanism is documented across multiple Microsoft Q&A threads and community forums.
- **Fix:** Abandoned the registry-based approach entirely. Switched to placing a `.lnk` shortcut in `shell:startup` (`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\`), which is processed by a different Explorer code path not subject to the StartupApproved gate. Old registry entries are cleaned up on every enable/disable call.
- **Commit:** `ce808fc`

**Bug 3: Host window moved to Monitor 1 after Monitor 2 power-cycle**
- **Symptom:** When Monitor 2 turned off and back on, Windows rearranged the virtual desktop and moved the host window from Display 3 to Monitor 1. The host stayed on Monitor 1 permanently.
- **Root cause:** The `WM_DISPLAYCHANGE` handler only reapplied `ClipCursor()` with the original coordinates — it never re-found Display 3 or repositioned the window. The window position and ClipCursor rect were computed once at startup and never updated.
- **Fix:** On `WM_DISPLAYCHANGE` and session unlock, debounce (1.5s), then re-find Display 3 via `find_target_screen()`, reposition the window with `setGeometry()`, recompute the allowed cursor rect, and reapply `ClipCursor()`. Retry after 2s if Display 3 isn't available yet (still powering on).
- **Commit:** `2dde26b`
- **Note:** The brief flicker to Monitor 1 is expected — Windows moves the window before the debounce fires. The 1.5s delay ensures the display layout has stabilized before repositioning.

**Bug 4: Cursor escapes to Display 3 on focus-change events**
- **Symptom:** Cursor could freely move onto Display 3 (the excluded monitor) after: pressing the Windows key, Alt-Tab, interacting with another monitor, or Ctrl+Win+Arrow virtual desktop switch. Clicking on Display 3 itself would re-enforce the lock (cursor snapped back), but the cursor remained free until then.
- **Root cause:** The message-based ClipCursor re-application (WM_ACTIVATE, WM_ACTIVATEAPP) fires during our deactivation handler, but Windows clears ClipCursor *after* the message returns — when the newly-focused window/shell processes its activation. The re-apply is immediately overridden. Virtual desktop switches and cross-monitor interactions don't reliably send these messages at all.
- **Fix:** Added a 100ms polling QTimer that continuously re-applies ClipCursor as a safety net. ClipCursor is a single Win32 syscall with negligible overhead, and it auto-snaps the cursor back into the allowed region if it has already escaped. The existing message-based handlers are retained for immediate response when timing works out.
- **Commit:** `c94d0be`

**Bug 5: Packaged control panel exe stale after autostart fix commits**
- **Symptom:** The control panel exe (`dist/MonitorControl/MonitorControl.exe`) could not save settings or send pomodoro commands to the host. Buttons appeared to work but had no effect. Running the control panel from source (`python -m control_panel`) worked correctly.
- **Root cause:** The packaged exe was built before the autostart fix commits (`ce808fc`, etc.) which modified `control_panel/autostart.py` and `control_panel/main_window.py`. PyInstaller's cache detected the stale modules on rebuild: "Building because control_panel\main_window.py changed". The exe was bundling old code.
- **Fix:** Rebuilt the packaged exe with `python -m PyInstaller build/control_panel.spec --noconfirm`.
- **Commit:** (this commit)

### Key Lessons (Post-Ship)

4. **Never trust the HKCU Run key on Windows 11 for autostart.** Use `shell:startup` shortcut instead. The registry approach has known reliability issues that are extremely difficult to diagnose — the registry looks correct but Windows silently refuses to execute.
5. **Any UI toggle that modifies system state must show errors, never silently succeed.** The RuntimeError was swallowed because only `OSError` was caught. Every code path that changes registry/filesystem state should catch `Exception` and surface failures to the user.
6. **`WM_DISPLAYCHANGE` must trigger full display re-discovery, not just ClipCursor reapplication.** Any host with display-dependent geometry needs to re-find its target screen and reposition after display topology changes.
7. **Message-based ClipCursor re-application is insufficient — use a polling timer as a safety net.** Windows clears ClipCursor after our deactivation message returns, overriding the re-apply. A 100ms polling timer guarantees restoration regardless of the trigger (Start menu, Alt-Tab, virtual desktop switch, cross-monitor interaction).
8. **Rebuild the packaged exe after every code change to the control panel.** PyInstaller's onedir build caches modules; the exe silently runs stale code if not rebuilt. Add a rebuild step to the post-commit checklist for any change touching `control_panel/`.

### Cost Observations

- Sessions: ~3 (one per phase, roughly; Phase 7 extended by the config path debugging)
- Post-ship bug fixing: ~2 additional sessions covering 5 bugs discovered during real-world testing
- Notable: Phase 7's checkpoint was the most valuable part of the milestone — the smoke test caught an architectural gap that automated tests would never have found. The post-ship bugs reinforce that reboot-cycle testing should be part of the phase verification protocol for any startup/display feature.

---

## Milestone: v1.2 — Configurable Colors

**Shipped:** 2026-03-27
**Phases:** 4 | **Plans:** 6

### What Was Built

1. `control_panel/color_picker.py` — `ColorPickerWidget` with hue slider (0–359), intensity slider (0–100), live swatch, hex input; QColor.fromHslF with fixed saturation 0.8; re-entrancy guard; hue preserved across achromatic round-trips (Phase 8-01)
2. Host compositor background ownership — `HostWindow.set_bg_color()`, `paintEvent` fill, all three widgets migrated to transparent RGBA; zero visual change at default #1a1a2e (Phase 8-02)
3. `bg_color` hot-reload pipeline — top-level config key wired through `ConfigLoader._after_reload` → `HostWindow.set_bg_color()`; `_safe_hex_color` helper in CalendarWidget for config-driven `time_color`/`date_color` (Phase 9)
4. Pomodoro Appearance groupbox — three `ColorPickerWidget` instances replacing hex `QLineEdit` fields; full `_load_values`/`_collect_config` wiring with `.get()` defaults (Phase 10)
5. Calendar Clock Settings groupbox — two `ColorPickerWidget` instances for `time_color` and `date_color`; 4-key dict overwrite safety (Phase 10)
6. Layout tab Appearance groupbox — one `ColorPickerWidget` for `bg_color`; top-level config key pattern (not widget settings); closes v1.2 end-to-end (Phase 11)

### What Worked

- **Proving the pipeline before building the UI**: Phase 9 wired and verified the full config-to-screen hot-reload pipeline (bg_color and calendar colors) before Phase 10 added any control panel UI. When the UI was built, it just needed to write the correct keys — the pipeline was already known-good.
- **TDD discipline on every plan**: All four implementation plans followed RED (failing tests) → GREEN (implementation) → commit cycle. The 30 tests in `test_control_panel_window.py` caught the HSL normalization behavior (ColorPickerWidget round-trips produce slightly different hex than the stored value) before it could cause assertion failures in production tests.
- **Rebuild memory saves re-discovery time**: After Phase 10 the user confirmed the exe needed a rebuild to show changes. This was saved to memory, so the Phase 11 rebuild was automatic.
- **Integration checker caught real issues**: The MISS-01 finding (`_update_widget_settings` docstring/behavior mismatch) was discovered only through the integration checker's source trace — not flagged by any unit test because the edge case is masked at runtime.

### What Was Inefficient

- **Exe rebuild not automated into the workflow**: Every code change to the control panel requires a manual `pyinstaller` rebuild. The first time this was discovered (after Phase 10 was complete), the user had already launched the old exe and was confused by unchanged UI. A post-commit hook or build script would eliminate this discovery cost.
- **SUMMARY.md `one_liner` and `tasks` fields still empty**: Third milestone with zero accomplishments extracted by `gsd-tools summary-extract`. The milestone CLI returned `tasks: 0` and `accomplishments: []` for the same reason as v1.0 and v1.1 — the SUMMARY schema the executor writes does not match what the CLI expects.
- **Phase 9 VERIFICATION.md stuck at `human_needed`**: Automated verification confirmed 5/5 must-haves; the `human_needed` status persisted because the hot-reload tests were never formally signed off in the VERIFICATION.md. The manual confirmation happened implicitly through Phase 10/11 testing.

### Patterns Established

- **Top-level config key pattern**: `bg_color` is accessed directly from `self._config` — no `_find_widget_settings()` call. Widget-scoped keys go under `widgets[N]["settings"]`; host-scoped keys go at the top level. Future phases should document which pattern applies.
- **`set_color()` / `.color()` wiring pattern**: All color pickers initialized with `set_color(cfg.get(key, default))` in `_load_values()`; read with `.color()` in `_collect_config()`. Consistent across all 6 pickers.
- **Fixed saturation ColorPickerWidget**: SATURATION = 0.8 is a deliberate design choice. Test assertions must use structural checks (`startswith("#")`, `len == 7`) not exact equality — the widget normalizes through HSL.
- **Separate groupboxes for geometry vs. appearance**: Layout tab has "Display" (width/height) and "Appearance" (bg_color) as separate groupboxes. Pomodoro tab has "Durations" and "Appearance". This pattern should be followed for all future tabs.

### Key Lessons

1. **Add exe rebuild to the post-code-change checklist.** Any change to `control_panel/` requires `python -m PyInstaller build/control_panel.spec -y` before the user can see results. Consider a shell hook or Makefile target.
2. **Sign off VERIFICATION.md human checks immediately after user confirms.** Phase 9's `human_needed` status lingered because the sign-off step was deferred. The executor should update VERIFICATION.md status atomically when human confirms.
3. **Fix the SUMMARY.md schema mismatch.** Three milestones in, `gsd-tools summary-extract` has never returned a non-null `one_liner` or accurate `tasks` count. The executor's SUMMARY format and the CLI's extraction format need to be reconciled once.
4. **Correct `_update_widget_settings` or fix the docstring.** The edge case (missing widget entry in config) is harmless now but will bite a future developer. Either implement the create path or remove the misleading docstring.

### Cost Observations

- Sessions: ~4 (plan + execute per phase group; Phases 10 and 11 were single sessions each)
- Notable: v1.2 was the smoothest milestone — prior pipeline work (v1.0/v1.1) meant every Phase 8–11 change had a clear integration point. No unexpected host changes required.

---

## Cross-Milestone Trends

### Documentation Completeness

| Milestone | Phases with VERIFICATION.md | Phases Nyquist-compliant |
|-----------|----------------------------|--------------------------|
| v1.0      | 3/4                        | 0/4                      |
| v1.1      | 3/3                        | 0/3                      |
| v1.2      | 4/4                        | 0/4 (1/4 if Phase 5 counted) |

### Hardware Verification Coverage

| Milestone | Phases hardware-verified | Hardware bugs caught |
|-----------|--------------------------|----------------------|
| v1.0      | 4/4                      | 3 (showFullScreen wrong monitor, WM_ACTIVATEAPP ClipCursor gap, WinRT IVectorView/None crash) |
| v1.1      | 1/3 (Phase 7 only)       | 5 (config path mismatch, silent autostart failure, Win11 Run key ignored, display reposition on power-cycle, ClipCursor escape on focus change) |
| v1.2      | 4/4 (human verification per phase) | 1 (stale exe — user saw old UI after Phase 10 code change, before rebuild) |

### SUMMARY.md Schema Compliance

| Milestone | `one_liner` populated | `requirements_completed` populated | `tasks` populated |
|-----------|----------------------|-------------------------------------|-------------------|
| v1.0      | ✗                    | ✗                                   | ✗                 |
| v1.1      | ✗                    | ✗                                   | ✗                 |
| v1.2      | ✗                    | ✓ (phases 9-11)                     | ✗                 |
