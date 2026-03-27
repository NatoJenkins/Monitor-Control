---
phase: 09-config-schema-host-hot-reload-wiring
verified: 2026-03-27T22:30:00Z
status: human_needed
score: 5/5 must-haves verified
human_verification:
  - test: "Edit %LOCALAPPDATA%\\MonitorControl\\config.json, change bg_color to #ff0000, save — observe bar background"
    expected: "Bar background turns red within the hot-reload debounce window (~200ms) without restarting the host"
    why_human: "QFileSystemWatcher + QTimer debounce + paintEvent refresh requires a running host on real hardware — cannot be verified headlessly"
  - test: "Edit %LOCALAPPDATA%\\MonitorControl\\config.json, change time_color to #ff0000 in calendar settings, save — observe calendar widget"
    expected: "Calendar time text changes to red within the next render cycle without restarting the host or the calendar subprocess"
    why_human: "Subprocess CONFIG_UPDATE round-trip (host _reconcile -> send_config_update -> in_queue -> poll_config_update -> render) requires running processes — integration test would need process spawning"
  - test: "Edit %LOCALAPPDATA%\\MonitorControl\\config.json and remove the bg_color key entirely, restart the host"
    expected: "Host starts without error and renders the bar at #1a1a2e (the default)"
    why_human: "Default fallback on missing key requires a running host to confirm no crash and correct visual color"
---

# Phase 9: Config Schema + Host Hot-Reload Wiring — Verification Report

**Phase Goal:** Editing config.json by hand causes the bar background color and calendar text colors to update live — the full config-to-screen pipeline is verified before any control panel UI is built
**Verified:** 2026-03-27T22:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths (from ROADMAP Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Manually setting `bg_color` in config.json causes bar background to change within the hot-reload debounce window (no host restart) | ? UNCERTAIN | Pipeline code verified: `_after_reload` calls `window.set_bg_color(config_loader.current_config.get("bg_color", "#1a1a2e"))`. Actual live update requires human test |
| 2 | A v1.1 config.json with no `bg_color` key loads without error and renders at #1a1a2e | ✓ VERIFIED | `test_bg_color_missing_defaults_to_1a1a2e` passes; `.get("bg_color", "#1a1a2e")` pattern confirmed in both initial load (line 140) and `_after_reload` (line 145) |
| 3 | A v1.1 config.json with no `time_color` or `date_color` loads without error and renders at #ffffff and #dcdcdc | ✓ VERIFIED | `TestCalendarColorInit::test_default_time_color` and `test_default_date_color` both pass; `_safe_hex_color(settings.get("time_color", "#ffffff"), (255,255,255,255))` wired in `__init__` |
| 4 | Manually setting `time_color` and `date_color` causes calendar text to update without restarting the subprocess | ? UNCERTAIN | Widget-side code verified: CONFIG_UPDATE handler applies `_safe_hex_color` for both keys (lines 107-110 of widget.py). Actual live propagation requires running processes |

**Score:** 5/5 truths have supporting implementation (2 require human confirmation for the live hot-reload behavior specifically)

---

## Required Artifacts

### Plan 01 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `host/main.py` | bg_color wiring — initial load + after_reload callback | ✓ VERIFIED | Lines 138-147: ConfigLoader constructed without after_reload; `window.set_bg_color(config.get("bg_color", "#1a1a2e"))` on line 140 (initial load); `_after_reload` defined at line 143-145 and assigned at line 147 |
| `config.json` | bg_color top-level key + calendar color keys | ✓ VERIFIED | `"bg_color": "#1a1a2e"` is first key in root object; calendar settings contains `"time_color": "#ffffff"` and `"date_color": "#dcdcdc"` |
| `tests/test_config_loader.py` | TestBgColorWiring test class | ✓ VERIFIED | Class with 3 methods present (lines 358-455): `test_after_reload_calls_set_bg_color`, `test_bg_color_missing_defaults_to_1a1a2e`, `test_bg_color_initial_load_applied`; all pass |

### Plan 02 Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `widgets/calendar/widget.py` | `_safe_hex_color` helper + color-aware init + CONFIG_UPDATE handler | ✓ VERIFIED | `_safe_hex_color` at lines 26-32; `__init__` reads `time_color` and `date_color` via `.get()` through `_safe_hex_color` at lines 45-50; `run()` handler applies both at lines 107-110 |
| `tests/test_calendar_widget.py` | TestCalendarColorInit and TestCalendarColorUpdate test classes | ✓ VERIFIED | TestSafeHexColor (3 tests), TestCalendarColorInit (6 tests), TestCalendarColorUpdate (3 tests) — all present and pass |

---

## Key Link Verification

### Plan 01 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `host/main.py` | `host/window.py` | `window.set_bg_color(config.get('bg_color', '#1a1a2e'))` | ✓ WIRED | Line 140: initial load call confirmed. Line 145: `_after_reload` call confirmed. Pattern `set_bg_color.*bg_color.*1a1a2e` matches both occurrences |
| `host/config_loader.py` | `host/main.py` | `_after_reload` callback invocation | ✓ WIRED | `config_loader._after_reload = _after_reload` at line 147 assigns the composed callback post-construction. `ConfigLoader._do_reload` checks `if self._after_reload: self._after_reload()` — confirmed in codebase from plan interfaces |

### Plan 02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `widgets/calendar/widget.py` | `PIL.ImageColor` | `_safe_hex_color` calls `ImageColor.getrgb()` | ✓ WIRED | Line 6: `from PIL import Image, ImageColor, ImageDraw, ImageFont`; line 29: `r, g, b = ImageColor.getrgb(hex_str)` |
| `CalendarWidget.__init__` | config settings dict | `settings.get('time_color', '#ffffff')` | ✓ WIRED | Lines 45-50 in `__init__` confirmed; `settings.get("time_color", "#ffffff")` and `settings.get("date_color", "#dcdcdc")` both present |
| `CalendarWidget.run()` | CONFIG_UPDATE handler | `_safe_hex_color` applied to updated settings | ✓ WIRED | Lines 107-110: `if "time_color" in settings: self._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))` and matching block for `date_color` |

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| BG-03 | 09-01 | Bar background color stored as top-level `bg_color` key in config.json; default #1a1a2e matches current hardcoded value | ✓ SATISFIED | `config.json` has `"bg_color": "#1a1a2e"` at root; `host/main.py` reads it on initial load and in `_after_reload`; 3 unit tests cover the pipeline; TestBgColorWiring all pass |
| CAL-04 | 09-02 | Calendar widget reads `time_color` from settings block; default #ffffff matches current hardcoded | ✓ SATISFIED | `CalendarWidget.__init__` reads via `_safe_hex_color(settings.get("time_color", "#ffffff"), ...)`. `run()` handler applies updates. 3 tests in TestCalendarColorInit + 1 in TestCalendarColorUpdate cover this |
| CAL-05 | 09-02 | Calendar widget reads `date_color` from settings block; default #dcdcdc matches current hardcoded | ✓ SATISFIED | `CalendarWidget.__init__` reads via `_safe_hex_color(settings.get("date_color", "#dcdcdc"), ...)`. `run()` handler applies updates. 3 tests in TestCalendarColorInit + 1 in TestCalendarColorUpdate cover this |
| CLR-01 | 09-01, 09-02 | All new config keys use `.get()` with defaults matching current hardcoded values — zero visual change on upgrade | ✓ SATISFIED | All four new `.get()` calls confirmed with exact hardcoded defaults: `#1a1a2e` (host), `#ffffff` (time), `#dcdcdc` (date). `test_bg_color_missing_defaults_to_1a1a2e`, `test_default_time_color`, `test_default_date_color` verify fallback behavior. `TestSafeHexColor::test_invalid_hex_returns_default` and `test_none_returns_default` verify crash protection |

**Coverage:** 4/4 requirement IDs accounted for. No orphaned requirements found for Phase 9 in roadmap or research files.

**Note:** The v1.2 requirements are documented inline in the RESEARCH.md phase requirements table — there is no separate `v1.2-REQUIREMENTS.md` file yet. All four requirement IDs (BG-03, CAL-04, CAL-05, CLR-01) are fully described in `09-RESEARCH.md` and cross-referenced in both PLAN frontmatter `requirements` fields. No orphaned requirements detected.

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `host/main.py` | 125 | String `"placeholder"` in log message | Info | Not a code stub — part of `"widget will show placeholder"` user-facing log string for notification access denial; unrelated to Phase 9 changes |

No blockers. No TODO/FIXME/stub patterns in any Phase 9 modified file. Old `after_reload=reapply_clip` pattern confirmed absent from `host/main.py`.

---

## Test Results (Automated)

```
tests/test_config_loader.py + tests/test_calendar_widget.py
41 passed in 0.17s

Breakdown:
  TestBgColorWiring: 3/3 pass
  TestSafeHexColor: 3/3 pass
  TestCalendarColorInit: 6/6 pass
  TestCalendarColorUpdate: 3/3 pass
  Pre-existing tests: 26/26 pass (no regressions)
```

Commits verified in git log:
- `3692cdf` — test(09-01): add TestBgColorWiring tests
- `77bb8eb` — feat(09-01): wire bg_color + update config schema
- `4002985` — test(09-02): add failing color tests (TDD RED)
- `c9ccdec` — feat(09-02): add _safe_hex_color and config-driven colors (TDD GREEN)

---

## Human Verification Required

All automated checks pass. The following behaviors require a running host on physical hardware to confirm the live hot-reload path end-to-end.

### 1. bg_color Live Hot-Reload

**Test:** With the host running, edit `%LOCALAPPDATA%\MonitorControl\config.json`. Change `"bg_color"` from `"#1a1a2e"` to `"#ff0000"`. Save the file.
**Expected:** The bar background turns red within approximately 200ms (the QFileSystemWatcher debounce window) without any host restart.
**Why human:** QFileSystemWatcher file-change events, QTimer debounce, and `paintEvent` refresh require a running Qt application on real hardware. Cannot be triggered headlessly.

### 2. Calendar Color Live Hot-Reload

**Test:** With the host running, edit `%LOCALAPPDATA%\MonitorControl\config.json`. Change `"time_color"` to `"#ff0000"` in the calendar widget's settings block. Save the file.
**Expected:** The calendar time text changes color to red within the next 1-second render cycle (1Hz loop in `CalendarWidget.run()`) without restarting the host or calendar subprocess.
**Why human:** The full pipeline (file change -> QFileSystemWatcher -> debounce -> `_reconcile` -> `send_config_update` -> multiprocessing queue -> `poll_config_update` -> `_safe_hex_color` -> `render_frame` -> compositor) requires live running processes. Integration testing this headlessly would require process spawning and IPC timing synchronization.

### 3. Missing-Key Default on Running Host

**Test:** Remove the `"bg_color"` key from `%LOCALAPPDATA%\MonitorControl\config.json` entirely. Restart the host.
**Expected:** Host starts without error and bar renders at `#1a1a2e`. (Unit tests cover the `.get()` default pattern; this confirms no crash on startup with the actual Qt paint cycle.)
**Why human:** Confirms the full startup path through `main()` with a real `HostWindow`, not the mocked `MagicMock` compositor and `pm` in unit tests.

---

## Gaps Summary

No gaps found. All code-verifiable must-haves pass:
- All 5 artifacts exist and are substantive (no stubs)
- All 5 key links are wired (confirmed by code inspection)
- All 4 requirements are satisfied with test coverage
- 41 tests pass with no regressions
- No TODO/FIXME/placeholder anti-patterns in Phase 9 modified files

The 3 human verification items are confirmation of live hot-reload behavior that automated checks cannot replicate — the underlying pipeline code is fully wired and tested at unit level. The phase goal is structurally achieved; human tests confirm the end-to-end runtime behavior.

---

_Verified: 2026-03-27T22:30:00Z_
_Verifier: Claude (gsd-verifier)_
