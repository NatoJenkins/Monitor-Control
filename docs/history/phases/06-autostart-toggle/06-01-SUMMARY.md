---
phase: 6
plan: 1
slug: autostart-toggle
subsystem: control-panel
tags: [autostart, registry, winreg, pyqt6, windows, startup]
dependency_graph:
  requires: [shared/paths.py, control_panel/main_window.py, host/main.py]
  provides: [control_panel/autostart.py, launch_host.pyw, Startup tab UI]
  affects: [control_panel/main_window.py, tests/test_control_panel_window.py]
tech_stack:
  added: [winreg (stdlib), QCheckBox (PyQt6)]
  patterns: [function-level imports for lazy winreg access, blockSignals guard for registry reads]
key_files:
  created:
    - control_panel/autostart.py
    - launch_host.pyw
    - tests/test_autostart.py
  modified:
    - control_panel/main_window.py
    - tests/test_control_panel_window.py
decisions:
  - "Function-level imports in _load_values and _on_autostart_toggled prevent winreg from being imported at module load time, enabling test isolation without patching at the main_window module level"
  - "blockSignals(True/False) wraps setChecked() in _load_values() to prevent spurious registry writes on every panel open"
  - "isHidden() used instead of isVisible() in label visibility tests — isVisible() returns False when parent window not shown to screen"
metrics:
  duration_minutes: 5
  completed_date: "2026-03-27"
  tasks_completed: 4
  tests_added: 15
  files_created: 3
  files_modified: 2
requirements: [STRT-01, STRT-02, STRT-03, STRT-04, STRT-05]
---

# Phase 6 Plan 1: Autostart Toggle Summary

**One-liner:** HKCU Run key autostart via winreg stdlib — registry module, no-console launcher, and Startup tab in control panel with live registry read and immediate toggle.

## What Was Built

Three artifacts deliver the complete autostart feature:

1. **`control_panel/autostart.py`** — Registry module with 3 public functions (`is_autostart_enabled`, `enable_autostart`, `disable_autostart`) and 2 private helpers (`_get_pythonw`, `_build_command`). Uses `winreg.OpenKey` + `SetValueEx`/`QueryValueEx`/`DeleteValue` on `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Both paths in the Run key value are individually double-quoted to handle spaces in paths.

2. **`launch_host.pyw`** — Minimal no-console entry point at the project root. When `pythonw.exe` runs this by absolute path from the Run key, `sys.path[0]` is set to the project root directory, making all `from host.X import Y` and `from shared.X import Y` imports work correctly. Contains null-guard, `multiprocessing.set_start_method("spawn")` under `__name__ == "__main__"`, and delegates to `host.main.main()`.

3. **Startup tab in `ControlPanelWindow`** — Sixth tab with a QCheckBox and conditional QLabel. `_load_values()` reads the live HKCU registry state (with `blockSignals` guard) on every panel open. Checkbox toggle calls `enable_autostart()`/`disable_autostart()` immediately with OSError revert on failure.

## Test Results

- **Before:** 112 tests passing (baseline, excluding test_e2e_dummy)
- **After:** 127 tests passing
- **New tests added:** 15 (9 in test_autostart.py, 6 in test_control_panel_window.py)
- **Full regression:** PASS (127 passed, 3 pre-existing warnings, 0 failures)

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 0 — Wave 0 scaffold | 804115d | Test stubs for autostart module and Startup tab (RED state) |
| 1 — Registry module | c04cc3d | Full autostart.py implementation + launch_host.pyw |
| 2 — Startup tab | 410d5fa | ControlPanelWindow Startup tab + existing test mocks |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed label visibility test using isHidden() instead of isVisible()**
- **Found during:** Task 2
- **Issue:** `test_startup_label_visible_when_checked` failed because `QLabel.isVisible()` returns `False` when the parent window has not been shown (`.show()` not called). The plan specified `assert window._autostart_label.isVisible() is True` which only works post-show.
- **Fix:** Changed both label visibility tests to use `not window._autostart_label.isHidden()` for the "visible" case and `window._autostart_label.isHidden()` for the "hidden" case. `isHidden()` correctly reflects the widget's explicit visibility state independent of parent hierarchy shown state.
- **Files modified:** `tests/test_control_panel_window.py`
- **Commit:** 410d5fa

## Self-Check: PASSED

- control_panel/autostart.py: FOUND
- launch_host.pyw: FOUND
- tests/test_autostart.py: FOUND
- 06-01-SUMMARY.md: FOUND
- Commit 804115d: FOUND
- Commit c04cc3d: FOUND
- Commit 410d5fa: FOUND
