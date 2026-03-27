# Deferred Items — Phase 08

## Pre-existing Test Failure (Out of Scope)

**Discovered during:** Task 2 (08-01), full test suite run
**File:** `tests/test_autostart.py`
**Tests affected:** `test_is_autostart_enabled_true` and likely adjacent autostart tests

**Issue:** `AttributeError: <module 'control_panel.autostart'> does not have the attribute 'winreg'`

The test patches `control_panel.autostart.winreg` but the autostart module uses a function-level import (per Phase 06 decision: "Function-level imports in _load_values and _on_autostart_toggled prevent winreg from importing at module load time, enabling test isolation"). The mock target path is therefore wrong — `winreg` is not a module-level attribute of `control_panel.autostart`.

**Confirmed pre-existing:** Failure reproduced on git stash (before any 08-01 changes).

**Impact:** Does not affect 08-01 deliverables. ColorPickerWidget tests all pass.

**Action required:** Fix mock target in `tests/test_autostart.py` to patch at the correct import path. Out of scope for Phase 08.
