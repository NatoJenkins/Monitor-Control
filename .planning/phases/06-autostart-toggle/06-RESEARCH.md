# Phase 6: Autostart Toggle - Research

**Researched:** 2026-03-27
**Domain:** Windows registry (winreg stdlib), Python no-console launch (pythonw.exe), PyQt6 checkbox UI
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| STRT-01 | User can enable host autostart at Windows login from the control panel Startup tab | `winreg.SetValueEx` on `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` with a `REG_SZ` value — verified working on this machine |
| STRT-02 | User can disable host autostart from the control panel Startup tab | `winreg.DeleteValue` on the same key — verified working; raises `FileNotFoundError` (not `OSError`) when entry absent |
| STRT-03 | Autostart toggle reflects live HKCU registry state (reads current entry on every panel open, not cached) | `winreg.QueryValueEx` inside `_load_values()` (already called by `ControlPanelWindow.__init__`) — no config.json involved |
| STRT-04 | Host launches without a terminal or console window when autostarted | Run key value uses `pythonw.exe` (not `python.exe`) as interpreter — `pythonw.exe` confirmed present alongside `python.exe` |
| STRT-05 | Control panel Startup tab shows status label "MonitorControl will start automatically at next login" when toggle is checked | `QLabel.setVisible(bool)` driven by checkbox state — standard Qt pattern |
</phase_requirements>

---

## Summary

Phase 6 adds a single Startup tab to the control panel that reads and writes the Windows HKCU Run registry key. The entire implementation is confined to three new artifacts: `control_panel/autostart.py` (registry logic), a `launch_host.pyw` wrapper at the project root (the no-console entry point the Run key points to), and a new `_build_startup_tab()` method added to `ControlPanelWindow`.

The key architectural constraint is that the HKCU Run key requires a stand-alone launch script — not `host/main.py` directly — because invoking `host/main.py` by absolute path under `pythonw.exe` sets `sys.path[0]` to the `host/` directory, which breaks all `from host.X import Y` imports. A `launch_host.pyw` placed at the project root receives `sys.path[0] = project_root`, giving correct import resolution.

The registry cycle (`SetValueEx` / `QueryValueEx` / `DeleteValue`) was verified end-to-end against the live HKCU Run key on this machine. No new packages are required — `winreg` is Python stdlib on Windows.

**Primary recommendation:** Create `control_panel/autostart.py` with three functions (`is_autostart_enabled`, `enable_autostart`, `disable_autostart`), create `launch_host.pyw` at the project root, and add a Startup tab to `ControlPanelWindow` that reads the live registry state on every `_load_values()` call and writes/deletes immediately on checkbox toggle.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `winreg` (stdlib) | Python 3.11 (built-in) | Read/write/delete HKCU Run registry entry | Windows stdlib; no install; used by every Python Windows startup utility |
| `PyQt6.QtWidgets.QCheckBox` | 6.10.2 (already in project) | Boolean toggle for autostart enable/disable | Already the project UI framework |
| `PyQt6.QtWidgets.QLabel` | 6.10.2 (already in project) | Status message display when toggle is on | Already the project UI framework |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `sys` (stdlib) | Python 3.11 | Derive `pythonw.exe` path from `sys.executable` | Computing the Run key interpreter path in dev context |
| `os.path` (stdlib) | Python 3.11 | Path joining for Run key command string | Building the quoted command value |
| `shared.paths.get_config_path` | project | Derive project root for `launch_host.pyw` path | Computing the script path stored in the Run key |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `winreg` (stdlib) | `pywin32` `win32api.RegSetValueEx` | Same capability; `winreg` requires no extra install; `pywin32` already in project but redundant here |
| `launch_host.pyw` wrapper | `host/__main__.py` + pythonw.exe `-m host` | `-m host` requires PYTHONPATH to include project root, which means an env var in the Run key value — fragile; wrapper script is simpler |
| `launch_host.pyw` wrapper | Inline `sys.path.insert` at top of `host/main.py` | Pollutes the module-level import area; `main.py` is also run via `python -m host` (future) where `sys.path[0]` is already correct |
| Immediate registry write on toggle | Write registry on "Save" button click | Windows convention is immediate for startup toggles (matches Windows Settings, Task Manager Startup tab); no Save roundtrip needed |

**Installation:** No new packages required.

---

## Architecture Patterns

### Recommended Project Structure Addition
```
MonitorControl/
├── launch_host.pyw          # NEW — no-console entry point for HKCU Run key
├── control_panel/
│   ├── autostart.py         # NEW — winreg read/write/delete for HKCU Run key
│   └── main_window.py       # MODIFIED — add _build_startup_tab()
├── tests/
│   ├── test_autostart.py    # NEW — unit tests for autostart.py
│   └── test_control_panel_window.py  # MODIFIED — Startup tab presence + behavior
```

### Pattern 1: HKCU Run key read/write module

**What:** A three-function module encapsulating all `winreg` calls, keeping registry logic out of the UI layer.

**When to use:** Any time the control panel needs to read or modify the autostart state.

```python
# control_panel/autostart.py
import os
import sys
import winreg
from shared.paths import get_config_path

_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_VALUE_NAME = "MonitorControl"


def _get_pythonw() -> str:
    """Return the absolute path to pythonw.exe alongside the running python.exe."""
    return os.path.join(os.path.dirname(sys.executable), "pythonw.exe")


def _build_command() -> str:
    """Build the Run key command value: quoted pythonw.exe + quoted launch_host.pyw."""
    pythonw = _get_pythonw()
    project_root = str(get_config_path().parent)
    launch_script = os.path.join(project_root, "launch_host.pyw")
    return f'"{pythonw}" "{launch_script}"'


def is_autostart_enabled() -> bool:
    """Return True if the MonitorControl HKCU Run entry exists."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _VALUE_NAME)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return False


def enable_autostart() -> None:
    """Write the MonitorControl entry to HKCU Run."""
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_WRITE
    ) as key:
        winreg.SetValueEx(key, _VALUE_NAME, 0, winreg.REG_SZ, _build_command())


def disable_autostart() -> None:
    """Remove the MonitorControl entry from HKCU Run. No-ops if absent."""
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_WRITE
        ) as key:
            winreg.DeleteValue(key, _VALUE_NAME)
    except FileNotFoundError:
        pass  # Already absent — no-op is correct
```

### Pattern 2: launch_host.pyw — no-console entry point

**What:** A minimal `.pyw` script at the project root. `pythonw.exe` invokes it by absolute path from the Run key. The script's directory is automatically added to `sys.path[0]` by the interpreter, giving the project root on `sys.path` before any imports.

**Why `.pyw` at project root:** When `pythonw.exe` runs a script by absolute path, `sys.path[0]` is set to the directory containing that script. A `.pyw` at project root means `sys.path[0] = E:\ClaudeCodeProjects\MonitorControl`, which makes `from host.main import main` work. If `host/main.py` were used directly, `sys.path[0]` would be the `host/` subdirectory and all package imports would fail.

```python
# launch_host.pyw — placed at project root
# No-console entry point for HKCU Run key autostart.
# sys.path[0] is set by the interpreter to this file's directory (project root),
# which makes all 'from host.X import Y' and 'from shared.X import Y' imports work.
import sys
import os

# Null-guard: under pythonw.exe sys.stdout and sys.stderr are None.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import multiprocessing

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    from host.main import main
    main()
```

**IMPORTANT:** The `if __name__ == "__main__"` guard is essential. `pythonw.exe launch_host.pyw` sets `__name__ = "__main__"` for the top-level script, so `set_start_method` is called exactly once. The guard also prevents recursive spawn on Windows.

### Pattern 3: Startup tab in ControlPanelWindow

**What:** A new tab added to the existing `QTabWidget` that shows a checkbox and conditional status label.

**When to use:** Adding the Startup tab to the existing tab pattern.

```python
# Inside ControlPanelWindow — add to _build_ui() and extend _load_values()

def _build_startup_tab(self) -> QWidget:
    from PyQt6.QtWidgets import QCheckBox
    container = QWidget()
    layout = QVBoxLayout(container)
    group = QGroupBox("Startup")
    group_layout = QVBoxLayout(group)

    self._autostart_checkbox = QCheckBox("Start MonitorControl at Windows login")
    group_layout.addWidget(self._autostart_checkbox)

    self._autostart_label = QLabel("MonitorControl will start automatically at next login")
    self._autostart_label.setVisible(False)
    group_layout.addWidget(self._autostart_label)

    layout.addWidget(group)
    layout.addStretch()

    self._autostart_checkbox.toggled.connect(self._on_autostart_toggled)
    return container


def _on_autostart_toggled(self, checked: bool) -> None:
    from control_panel.autostart import enable_autostart, disable_autostart
    if checked:
        enable_autostart()
    else:
        disable_autostart()
    self._autostart_label.setVisible(checked)
```

**Reading live state in `_load_values()`:**
```python
# In _load_values() — reads HKCU on every panel open (STRT-03)
from control_panel.autostart import is_autostart_enabled
enabled = is_autostart_enabled()
self._autostart_checkbox.blockSignals(True)   # prevent _on_autostart_toggled during load
self._autostart_checkbox.setChecked(enabled)
self._autostart_checkbox.blockSignals(False)
self._autostart_label.setVisible(enabled)
```

**`blockSignals(True)` is critical:** Without it, `setChecked(True)` during `_load_values()` would fire `toggled`, which would call `enable_autostart()` again — a redundant registry write on every panel open.

### Anti-Patterns to Avoid

- **Storing autostart state in config.json:** The registry is the source of truth. Caching in config.json creates a split-brain state that diverges when the user modifies Windows Startup settings externally.
- **Calling `enable_autostart()` / `disable_autostart()` from the Save button:** Inconsistent with Windows convention and delays feedback. Write the registry immediately on toggle.
- **Running `host/main.py` directly from the Run key:** `sys.path[0]` = `host/` directory, breaking all package imports. Always use a wrapper script at the project root.
- **Not quoting paths in the Run key value:** Windows Run key values with spaces in paths must quote both the interpreter path and script path individually.
- **Catching bare `OSError` for "entry absent" check:** `winreg.QueryValueEx` raises `FileNotFoundError` (a subclass of `OSError`) specifically when the value does not exist. Catch `FileNotFoundError` first (more specific); catch `OSError` as a broader fallback for permission errors.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Autostart mechanism | Task Scheduler wrapper, startup folder copy | HKCU Run key via `winreg` | Decision locked in STATE.md — simpler, appears in Windows Settings, no UAC elevation needed |
| No-console launch | `subprocess.CREATE_NO_WINDOW` wrapper | `pythonw.exe` as the interpreter | `pythonw.exe` is the standard Python no-console launcher; no wrapper process needed |
| Registry error handling | Custom retry logic, error dialogs on every write | `try/except FileNotFoundError` + `try/except OSError` | Registry writes to HKCU Run never require elevation; `OSError` covers all genuine failure modes |

**Key insight:** `winreg` is 10 lines total for the three operations. Task Scheduler or startup folder approaches add 50+ lines of subprocess/COM/file management for zero benefit.

---

## Common Pitfalls

### Pitfall 1: sys.path[0] breaks imports when Run key invokes host/main.py directly
**What goes wrong:** Run key value `"pythonw.exe" "E:\...\host\main.py"` — interpreter sets `sys.path[0] = "E:\...\host"`. The line `from host.window import HostWindow` fails with `ModuleNotFoundError: No module named 'host.window'` because Python looks for `host/host/window.py`.
**Why it happens:** Python sets `sys.path[0]` to the script's parent directory, not the project root.
**How to avoid:** Use a `launch_host.pyw` at the project root. `sys.path[0]` becomes the project root and all `from host.X`, `from shared.X`, `from widgets.X` imports resolve correctly.
**Warning signs:** Host crashes immediately at login with no visible error (no console window).

### Pitfall 2: blockSignals missing when loading registry state in _load_values
**What goes wrong:** `self._autostart_checkbox.setChecked(True)` fires `toggled(True)`, which calls `enable_autostart()`, which writes to the registry — on every panel open. A no-op on the happy path, but causes a superfluous registry write and makes unit testing harder.
**Why it happens:** Qt checkbox signals fire on programmatic state changes as well as user clicks.
**How to avoid:** Wrap the `setChecked` call with `blockSignals(True)` / `blockSignals(False)`.

### Pitfall 3: FileNotFoundError vs OSError for absent registry value
**What goes wrong:** `winreg.QueryValueEx` raises `FileNotFoundError` when the value name does not exist. If you catch only `OSError`, the code works, but semantic intent is lost. If you catch only `FileNotFoundError`, genuine permission errors (unlikely for HKCU but possible) propagate uncaught.
**How to avoid:** In `is_autostart_enabled()`, catch `FileNotFoundError` first, then `OSError` as a broader guard. In `disable_autostart()`, catch `FileNotFoundError` to no-op when already absent. Verified: `winreg.QueryValueEx` raises `FileNotFoundError` (a Python built-in, subclass of `OSError`) for missing values — confirmed on this machine.

### Pitfall 4: Run key command value quoting
**What goes wrong:** If either path contains spaces (common — Python often installs under `C:\Users\username\AppData\...`), a Run key value without quotes causes Windows to mis-parse the command: `C:\Users\silve\AppData...pythonw.exe E:\ClaudeCode...launch_host.pyw` — the space in the username splits the arguments.
**How to avoid:** Always wrap both the interpreter path and the script path in double-quotes in the REG_SZ value: `"C:\path\pythonw.exe" "E:\path\launch_host.pyw"`. Use Python f-string: `f'"{pythonw}" "{launch_script}"'`.

### Pitfall 5: multiprocessing.set_start_method omitted in launch_host.pyw
**What goes wrong:** If `launch_host.pyw` just does `from host.main import main; main()` without the `multiprocessing.set_start_method("spawn")` call, the existing `if __name__ == "__main__"` guard in `host/main.py` is never triggered (its `__name__` is `"host.main"`, not `"__main__"`). The `set_start_method` call is skipped. On Windows, `spawn` is the default anyway, so this likely does not cause immediate failure, but it contradicts the explicit intent in `host/main.py`.
**How to avoid:** Put `multiprocessing.set_start_method("spawn")` inside an `if __name__ == "__main__":` block in `launch_host.pyw`. Since `launch_host.pyw` is the `__main__` script when invoked from the Run key, the guard executes correctly.

### Pitfall 6: Registry write fails silently without KEY_WRITE access flag
**What goes wrong:** `winreg.OpenKey(HKEY_CURRENT_USER, RUN_KEY)` opens with default `KEY_READ` access. Calling `SetValueEx` on a read-only handle raises `PermissionError` (OSError subclass).
**How to avoid:** Always open with explicit access for writes: `winreg.OpenKey(..., 0, winreg.KEY_WRITE)`. Verified: `winreg.KEY_WRITE = 131078`.

---

## Code Examples

Verified against the live registry on this machine:

### Complete winreg read/write/delete cycle (verified)
```python
# Source: direct verification on E:\ClaudeCodeProjects\MonitorControl — 2026-03-27
import winreg

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE_NAME = "MonitorControl"

# Check if enabled
def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
        return True
    except FileNotFoundError:
        return False

# Enable
def enable_autostart(command: str) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as key:
        winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command)

# Disable (no-op if absent)
def disable_autostart() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_WRITE) as key:
            winreg.DeleteValue(key, VALUE_NAME)
    except FileNotFoundError:
        pass
```

### Building the Run key command string
```python
import os, sys
from shared.paths import get_config_path

def _build_command() -> str:
    pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    project_root = str(get_config_path().parent)
    launch_script = os.path.join(project_root, "launch_host.pyw")
    return f'"{pythonw}" "{launch_script}"'
# Result: '"C:\Users\silve\AppData\...\pythonw.exe" "E:\ClaudeCodeProjects\MonitorControl\launch_host.pyw"'
```

### Startup tab in ControlPanelWindow
```python
# _build_ui() addition:
self._tabs.addTab(self._build_startup_tab(), "Startup")

# _load_values() addition (reads live registry — STRT-03):
from control_panel.autostart import is_autostart_enabled
enabled = is_autostart_enabled()
self._autostart_checkbox.blockSignals(True)
self._autostart_checkbox.setChecked(enabled)
self._autostart_checkbox.blockSignals(False)
self._autostart_label.setVisible(enabled)

# Toggle handler (immediate registry write — no Save button):
def _on_autostart_toggled(self, checked: bool) -> None:
    from control_panel.autostart import enable_autostart, disable_autostart
    if checked:
        enable_autostart()
    else:
        disable_autostart()
    self._autostart_label.setVisible(checked)
```

### blockSignals pattern (prevents spurious registry writes during load)
```python
# Source: PyQt6 QObject.blockSignals() — standard Qt pattern
self._autostart_checkbox.blockSignals(True)
self._autostart_checkbox.setChecked(enabled)  # won't fire toggled()
self._autostart_checkbox.blockSignals(False)
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Task Scheduler autostart | HKCU Run key | Decision locked in v1.1 | Simpler, no UAC, appears in Windows Settings |
| BLOCKER: `python.exe` in Run key | `pythonw.exe` in Run key | This phase | Eliminates terminal window on startup |
| Direct `host/main.py` in Run key | `launch_host.pyw` wrapper | This phase | Correct `sys.path[0]` for package imports |
| v2 plan: Host .exe autostart | `launch_host.pyw` (dev) | Future (HPKG-02) | Phase 7+ will replace launcher with host.exe |

**Deprecated/outdated for this context:**
- Task Scheduler: explicitly out of scope (see REQUIREMENTS.md Out of Scope table)
- Startup folder: no mechanism for no-console launch without additional complexity
- HPKG-02 (`autostart entry points to host.exe directly`): deferred to v2 — NOT this phase

---

## Open Questions

1. **Tab position for "Startup"**
   - What we know: Current tabs are Layout / Pomodoro / Calendar / Notification / Shortcuts (5 tabs). Startup is a new sixth tab.
   - What's unclear: Whether it goes at the end (index 5) or at a specific position (e.g., after Shortcuts or before it).
   - Recommendation: Append as the last tab ("Startup" at index 5). It is a system-level setting distinct from widget configuration, so last position reads naturally.

2. **Error handling for failed registry writes**
   - What we know: HKCU Run writes require no elevation and almost never fail. `winreg.OpenKey` with `KEY_WRITE` can raise `PermissionError` in edge cases (corrupted profile, policy restriction).
   - What's unclear: Whether to show a `QMessageBox` on failure or silently swallow the error.
   - Recommendation: Catch `OSError` in `_on_autostart_toggled`, show `QMessageBox.critical` with the error message, and revert the checkbox state with `blockSignals`. This matches the existing `_on_save` error pattern.

3. **launch_host.pyw location and naming**
   - What we know: Must be at the project root for correct `sys.path[0]`. The `.pyw` extension suppresses the console window even without `pythonw.exe` when double-clicked, but the Run key explicitly uses `pythonw.exe` for reliability.
   - What's unclear: Whether to name it `launch_host.pyw` or `MonitorControl.pyw` or similar.
   - Recommendation: `launch_host.pyw` — descriptive, clearly a launcher, not confused with the future `MonitorControl.exe`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, `pytest.ini` at project root) |
| Config file | `pytest.ini` |
| Quick run command | `pytest tests/test_autostart.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| STRT-01 | `enable_autostart()` writes a REG_SZ value under HKCU Run | unit (mocked winreg) | `pytest tests/test_autostart.py::test_enable_autostart_calls_set_value_ex -x` | Wave 0 |
| STRT-02 | `disable_autostart()` deletes the Run value | unit (mocked winreg) | `pytest tests/test_autostart.py::test_disable_autostart_calls_delete_value -x` | Wave 0 |
| STRT-02 | `disable_autostart()` no-ops when entry absent (FileNotFoundError) | unit (mocked winreg) | `pytest tests/test_autostart.py::test_disable_autostart_noop_when_absent -x` | Wave 0 |
| STRT-03 | `is_autostart_enabled()` returns True when value present, False when absent | unit (mocked winreg) | `pytest tests/test_autostart.py::test_is_autostart_enabled_true -x tests/test_autostart.py::test_is_autostart_enabled_false -x` | Wave 0 |
| STRT-03 | Startup tab checkbox reflects registry state on panel open | unit (Qt + mocked winreg) | `pytest tests/test_control_panel_window.py::test_startup_tab_present -x` | ❌ Wave 0 |
| STRT-04 | `_build_command()` returns a string containing `pythonw.exe` (not `python.exe`) | unit | `pytest tests/test_autostart.py::test_build_command_uses_pythonw -x` | Wave 0 |
| STRT-04 | `_build_command()` returns a string containing `launch_host.pyw` | unit | `pytest tests/test_autostart.py::test_build_command_contains_launch_script -x` | Wave 0 |
| STRT-05 | Status label is visible when checkbox is checked, hidden when unchecked | unit (Qt) | `pytest tests/test_control_panel_window.py::test_startup_label_visible_when_checked -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_autostart.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green (except pre-existing `test_e2e_dummy` flaky failure) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_autostart.py` — covers STRT-01, STRT-02, STRT-03, STRT-04 (registry logic, mocked winreg)
- [ ] `control_panel/autostart.py` — the module under test
- [ ] `launch_host.pyw` — no-console entry point (tested by STRT-04 path check)
- [ ] New assertions in `tests/test_control_panel_window.py` — covers STRT-03 (tab presence), STRT-05 (label visibility)

*(All other test infrastructure — `pytest.ini`, `conftest.py`, existing test files — is already in place.)*

---

## Sources

### Primary (HIGH confidence)
- Python stdlib `winreg` module — direct interactive verification on this machine (2026-03-27): `SetValueEx`, `QueryValueEx`, `DeleteValue` cycle executed and confirmed against live HKCU Run key
- Python interpreter behavior — `sys.path[0]` set to script directory; confirmed by running `sys.executable` substitution test on this machine
- `pythonw.exe` — confirmed present at `C:\Users\silve\AppData\Local\Programs\Python\Python311\pythonw.exe` alongside `python.exe`
- `winreg` constants — `KEY_READ = 131097`, `KEY_WRITE = 131078`, `REG_SZ = 1`, `HKEY_CURRENT_USER` confirmed via `python -c "import winreg; print(winreg.KEY_WRITE)"`
- `FileNotFoundError` on absent value — confirmed by live test: `QueryValueEx` with non-existent value name raises `FileNotFoundError` (not generic `OSError`)

### Secondary (MEDIUM confidence)
- Python Windows FAQ — `pythonw.exe` sets `sys.stdout = None`, consistent with Phase 5 research and existing null-guard in `host/main.py`
- PyQt6 `QCheckBox.toggled` signal, `blockSignals()` — project already uses these patterns in `ControlPanelWindow`; consistent with Qt documentation

### Tertiary (LOW confidence)
- None. All critical claims are verified by direct execution on this machine.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib + already-used project libraries; verified with live execution
- Architecture: HIGH — `sys.path[0]` behavior and winreg API verified experimentally; launch wrapper approach directly confirmed
- Pitfalls: HIGH — each pitfall was discovered by reasoning through actual runtime behavior with the actual Python installation on this machine

**Research date:** 2026-03-27
**Valid until:** Stable (stdlib winreg, no version sensitivity; PyQt6 6.10.2 already pinned in project)
