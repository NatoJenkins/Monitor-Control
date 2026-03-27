---
phase: 06-autostart-toggle
verified: 2026-03-27T00:00:00Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 6: Autostart Toggle Verification Report

**Phase Goal:** Users can enable and disable host autostart at Windows login from the control panel, with no terminal visible at launch
**Verified:** 2026-03-27
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #   | Truth                                                              | Status     | Evidence                                                                                                      |
| --- | ------------------------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------------------- |
| 1   | User can check the Startup toggle to register autostart in HKCU Run | VERIFIED  | `enable_autostart()` calls `winreg.SetValueEx` on `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`; checkbox toggle wired to `_on_autostart_toggled` which calls `enable_autostart()` immediately |
| 2   | User can uncheck the Startup toggle to remove autostart from HKCU Run | VERIFIED | `disable_autostart()` calls `winreg.DeleteValue` on the same key; no-ops silently if entry absent; wired to same toggle handler |
| 3   | Opening the control panel always reflects the live HKCU registry state | VERIFIED | `_load_values()` does a function-level `from control_panel.autostart import is_autostart_enabled`, calls it on every window construction, wraps `setChecked` with `blockSignals(True/False)` to prevent spurious writes |
| 4   | Host launches with no terminal window when autostarted via Run key | VERIFIED  | `launch_host.pyw` exists at project root with `.pyw` extension (Windows runs via `pythonw.exe`), contains null-guard for `sys.stdout`/`sys.stderr`, `__name__` guard, and `multiprocessing.set_start_method("spawn")`; Run key command uses `pythonw.exe` path built by `_build_command()` |
| 5   | Status label shows "MonitorControl will start automatically at next login" when autostart is active | VERIFIED | `_build_startup_tab()` creates `QLabel` with that exact text, initially hidden; `_on_autostart_toggled` and `_load_values` both call `setVisible(enabled)` to sync label with state |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact                                 | Expected                                         | Status     | Details                                                                                           |
| ---------------------------------------- | ------------------------------------------------ | ---------- | ------------------------------------------------------------------------------------------------- |
| `control_panel/autostart.py`             | Registry read/write/delete for HKCU Run key      | VERIFIED   | 54 lines; exports `is_autostart_enabled`, `enable_autostart`, `disable_autostart`, `_get_pythonw`, `_build_command`; no stubs or NotImplementedError |
| `launch_host.pyw`                        | No-console entry point for HKCU Run key          | VERIFIED   | 18 lines at project root; has null-guard, `__name__` guard, `set_start_method("spawn")`, imports `host.main.main` |
| `control_panel/main_window.py`           | Startup tab with checkbox, label, and toggle handler | VERIFIED | Contains `_build_startup_tab`, `_on_autostart_toggled`; 6th tab "Startup" added in `_build_ui`; `_load_values` reads live registry with `blockSignals` guard |
| `tests/test_autostart.py`               | Unit tests for registry module (min 50 lines)    | VERIFIED   | 145 lines; 9 test functions covering all 3 public functions and both helpers; uses `@patch("control_panel.autostart.winreg")` — never touches real registry |
| `tests/test_control_panel_window.py`    | Updated tests including Startup tab assertions   | VERIFIED   | Contains 6 Startup-specific tests (`test_startup_tab_checkbox_exists`, `test_startup_label_visible_when_checked`, `test_startup_label_hidden_when_unchecked`, `test_startup_toggle_calls_enable`, `test_startup_toggle_calls_disable`, `test_startup_tab_present`); all existing tests updated with `@patch("control_panel.autostart.is_autostart_enabled", return_value=False)` |

---

### Key Link Verification

| From                            | To                            | Via                                                        | Status   | Details                                                                                                       |
| ------------------------------- | ----------------------------- | ---------------------------------------------------------- | -------- | ------------------------------------------------------------------------------------------------------------- |
| `control_panel/main_window.py`  | `control_panel/autostart.py`  | function-level imports in `_load_values` and `_on_autostart_toggled` | WIRED | Lines 266, 279, 332: `from control_panel.autostart import enable_autostart, disable_autostart` and `from control_panel.autostart import is_autostart_enabled` — resolved at call time, enabling test isolation |
| `control_panel/autostart.py`    | `shared/paths.py`             | `get_config_path().parent` for project root                | WIRED    | Line 6: module-level `from shared.paths import get_config_path`; line 20: `get_config_path().parent` used in `_build_command()` |
| `control_panel/autostart.py`    | HKCU Run registry key         | `winreg.OpenKey` + `SetValueEx`/`QueryValueEx`/`DeleteValue` | WIRED  | Lines 28-29, 39-42, 48-51: all three winreg operations present and returning/using results; `_VALUE_NAME = "MonitorControl"` used consistently |

---

### Requirements Coverage

| Requirement | Description                                                           | Status     | Evidence                                                                                          |
| ----------- | --------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------------------------------------- |
| STRT-01     | Checking the toggle writes HKCU Run entry                             | SATISFIED  | `enable_autostart()` calls `SetValueEx`; `_on_autostart_toggled(True)` calls `enable_autostart()` |
| STRT-02     | Unchecking the toggle deletes HKCU Run entry; no-op if absent         | SATISFIED  | `disable_autostart()` calls `DeleteValue`; catches `FileNotFoundError` silently; wired to toggle handler |
| STRT-03     | Control panel reads live registry state on every open (no cache)      | SATISFIED  | `_load_values()` does function-level import and calls `is_autostart_enabled()` on every `ControlPanelWindow.__init__`; `blockSignals` prevents side effects |
| STRT-04     | Host launches with no terminal window via Run key                     | SATISFIED  | `_build_command()` uses `pythonw.exe` (not `python.exe`); `launch_host.pyw` extension suppresses console; null-guard handles None stdout/stderr |
| STRT-05     | Status label text "MonitorControl will start automatically at next login" displayed when toggle checked | SATISFIED | Label with exact text created in `_build_startup_tab()`; visibility synced to checkbox state in both `_load_values` and `_on_autostart_toggled` |

---

### Anti-Patterns Found

No anti-patterns detected.

| File                               | Scan                                      | Result  |
| ---------------------------------- | ----------------------------------------- | ------- |
| `control_panel/autostart.py`       | TODO/FIXME/NotImplementedError/stubs      | CLEAN   |
| `launch_host.pyw`                  | TODO/FIXME/stubs/empty implementations   | CLEAN   |
| `control_panel/main_window.py`     | TODO/FIXME/stubs                          | CLEAN   |
| `tests/test_autostart.py`          | NotImplementedError/incomplete mocks      | CLEAN   |
| `tests/test_control_panel_window.py` | Missing mocks / untested toggle paths   | CLEAN   |

---

### Human Verification Required

The following behaviors cannot be verified programmatically and require a live Windows session:

#### 1. End-to-end autostart at login

**Test:** Check the Startup tab checkbox, log out of Windows, log back in.
**Expected:** The host process starts automatically with no visible terminal or console window.
**Why human:** Registry state at login, `pythonw.exe` console suppression, and the spawn of the host process cannot be verified through static analysis or pytest.

#### 2. Registry persistence across control panel sessions

**Test:** Check the toggle, close the control panel, reopen it.
**Expected:** The checkbox is checked on reopen (live registry read confirmed).
**Why human:** Requires a running control panel session — live Qt widget state cannot be observed from tests alone. The code path is tested with mocks but real registry interaction needs human confirmation.

#### 3. Run key command path correctness

**Test:** After checking the toggle, open Registry Editor and inspect `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` -> `MonitorControl`.
**Expected:** Value contains `"C:\...\pythonw.exe" "C:\...\MonitorControl\launch_host.pyw"` with both paths individually double-quoted and pointing to real files.
**Why human:** Path construction depends on the actual Python installation directory and project root on the test machine — this is correct by code logic but the absolute paths need visual spot-check.

---

### Test Suite Results

| Suite                              | Tests | Result                        |
| ---------------------------------- | ----- | ----------------------------- |
| `tests/test_autostart.py`          | 9     | 9 passed                      |
| `tests/test_control_panel_window.py` | 21  | 21 passed                     |
| Full suite (excl. `test_e2e_dummy`) | 127  | 127 passed, 3 pre-existing warnings (coroutine in notification widget — unrelated to this phase) |

Commits verified in repository:
- `804115d` — Wave 0 test scaffolding
- `c04cc3d` — `autostart.py` + `launch_host.pyw` implementation
- `410d5fa` — Startup tab + existing test mock updates

---

### Deviations Noted

One plan deviation was correctly self-resolved: label visibility tests use `isHidden()` instead of `isVisible()` because `isVisible()` returns `False` when the parent `QMainWindow` has not been shown to the screen (no `.show()` call in tests). The `isHidden()` approach correctly reflects widget-level explicit visibility state and is the right pattern for headless Qt testing.

---

## Summary

Phase 6 achieved its goal. All five observable truths are satisfied by real, substantive, wired implementations. The registry module is fully implemented with no stubs. The launcher script has all required guards for no-console operation. The Startup tab is correctly wired to the live registry with a `blockSignals` guard preventing spurious writes on every panel open. All 127 tests pass. Three items require human verification (live login autostart, registry persistence, and path spot-check) but these are inherently runtime behaviors that cannot be verified statically.

---

_Verified: 2026-03-27_
_Verifier: Claude (gsd-verifier)_
