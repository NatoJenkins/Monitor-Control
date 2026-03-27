---
phase: 09-config-schema-host-hot-reload-wiring
plan: "01"
subsystem: host
tags: [config, hot-reload, bg_color, schema, wiring]
dependency_graph:
  requires: [08-02]
  provides: [bg_color hot-reload pipeline, config.json Phase 9 schema]
  affects: [host/main.py, config.json, tests/test_config_loader.py]
tech_stack:
  added: []
  patterns: [after_reload callback post-construction wiring, .get() with hardcoded defaults]
key_files:
  created: []
  modified:
    - host/main.py
    - config.json
    - tests/test_config_loader.py
decisions:
  - "ConfigLoader constructed without after_reload; _after_reload assigned post-construction to avoid forward reference (config_loader must be bound before lambda can close over it)"
  - "reapply_clip() called first in _after_reload to preserve HOST-04 behavior before bg_color update"
  - "window.set_bg_color() called between load() and apply_config() on initial startup to ensure bg renders before widgets are composited"
  - "LOCALAPPDATA config.json updated alongside project-root config.json — both needed for dev and packaged runtime"
metrics:
  duration: "2 minutes"
  completed_date: "2026-03-27"
  tasks_completed: 2
  files_modified: 3
requirements_completed: [BG-03, CLR-01]
---

# Phase 9 Plan 01: Config Schema + bg_color Hot-Reload Wiring Summary

**One-liner:** bg_color wired through ConfigLoader after_reload pipeline with post-construction callback assignment; config.json extended with bg_color, time_color, and date_color keys.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add bg_color wiring tests (TestBgColorWiring) | 3692cdf | tests/test_config_loader.py |
| 2 | Wire bg_color in main.py + update config.json schema | 77bb8eb | host/main.py, config.json |

## What Was Built

### host/main.py — bg_color wiring

The ConfigLoader construction block was refactored from:
```python
config_loader = ConfigLoader(str(_cfg), pm, window.compositor, after_reload=reapply_clip)
config = config_loader.load()
config_loader.apply_config(config)
```

To the composed pattern:
```python
config_loader = ConfigLoader(str(_cfg), pm, window.compositor)
config = config_loader.load()
window.set_bg_color(config.get("bg_color", "#1a1a2e"))
config_loader.apply_config(config)

def _after_reload():
    reapply_clip()
    window.set_bg_color(config_loader.current_config.get("bg_color", "#1a1a2e"))

config_loader._after_reload = _after_reload
```

This ensures:
- bg_color is applied on initial load (before widgets are composited)
- bg_color is re-applied on every hot-reload via the after_reload callback
- reapply_clip() runs first in _after_reload (HOST-04 preservation)
- Post-construction assignment eliminates forward reference issue

### config.json — Phase 9 schema additions

Added `"bg_color": "#1a1a2e"` as first top-level key.
Added `"time_color": "#ffffff"` and `"date_color": "#dcdcdc"` to calendar widget settings.
Both the project-root config.json and %LOCALAPPDATA%\MonitorControl\config.json updated.

### tests/test_config_loader.py — TestBgColorWiring

Three tests added as regression guards:
- `test_after_reload_calls_set_bg_color` — verifies callback invokes set_bg_color with value from current_config
- `test_bg_color_missing_defaults_to_1a1a2e` — verifies .get() default when key absent
- `test_bg_color_initial_load_applied` — verifies initial-load pattern returns correct value

## Test Results

27 tests pass (21 pre-existing + 3 new TestBgColorWiring + 3 test_window.py).

## Deviations from Plan

None — plan executed exactly as written. The LOCALAPPDATA config.json update was prescribed in Task 2 action block and was carried out.

Note: `test_send_config_update_delivers_message` exhibited one transient failure during verification (multiprocessing queue timing, pre-existing flaky test). The test passes consistently in isolation and is unrelated to this plan's changes.

## Self-Check: PASSED

- [x] tests/test_config_loader.py contains `class TestBgColorWiring`
- [x] tests/test_config_loader.py contains `def test_after_reload_calls_set_bg_color`
- [x] tests/test_config_loader.py contains `def test_bg_color_missing_defaults_to_1a1a2e`
- [x] tests/test_config_loader.py contains `def test_bg_color_initial_load_applied`
- [x] host/main.py contains `def _after_reload():`
- [x] host/main.py contains `window.set_bg_color(config_loader.current_config.get("bg_color", "#1a1a2e"))`
- [x] host/main.py contains `window.set_bg_color(config.get("bg_color", "#1a1a2e"))` (initial load)
- [x] host/main.py contains `config_loader._after_reload = _after_reload`
- [x] host/main.py does NOT contain `after_reload=reapply_clip`
- [x] config.json contains `"bg_color": "#1a1a2e"` at top level
- [x] config.json calendar settings contains `"time_color": "#ffffff"`
- [x] config.json calendar settings contains `"date_color": "#dcdcdc"`
- [x] commit 3692cdf exists
- [x] commit 77bb8eb exists
