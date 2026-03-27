# Architecture Research

**Domain:** Python desktop widget bar — autostart and standalone .exe packaging for Windows
**Researched:** 2026-03-27
**Confidence:** HIGH (Task Scheduler and registry approaches), HIGH (PyInstaller one-folder), MEDIUM (PyInstaller winrt hidden imports), HIGH (path resolution patterns)

---

## Context: What Is Already Built

This document extends the v1.0 architecture research with v1.1-specific integration analysis. The existing system is:

- **Host process** (`host/main.py`): PyQt6 app, spawns widget subprocesses via `multiprocessing.Process`, watches `config.json` via `QFileSystemWatcher`, enforces `ClipCursor()` on Display 3. Entry guard: `multiprocessing.set_start_method("spawn")` + `if __name__ == "__main__"`.
- **Control panel process** (`control_panel/__main__.py`): Separate PyQt6 `QMainWindow`, sole writer of `config.json`. Launched independently.
- **Config.json resolution**: Both host and control panel currently resolve `config.json` via a bare `"config.json"` string, which resolves against the process working directory. This is the core breakage risk when either process moves into a packaged `.exe`.

---

## v1.1 System Overview

```
┌──────────────────────────────────────────────────────────────────┐
│  WINDOWS LOGIN EVENT                                              │
│  Task Scheduler (ONLOGON trigger)                                 │
│       │                                                           │
│       └──► host\host.exe  (no console, hidden window style)      │
│                │                                                  │
│                ├── resolves config.json from exe directory        │
│                ├── spawns widget subprocesses via sys.executable  │
│                └── watches config.json via QFileSystemWatcher     │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│  USER LAUNCHES MANUALLY                                           │
│       │                                                           │
│       └──► control_panel\MonitorControl.exe  (standalone .exe)   │
│                │                                                  │
│                ├── resolves config.json from exe directory        │
│                ├── reads/writes config.json (sole writer)         │
│                └── "Startup" tab: enables/disables host autostart │
└──────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────┐
                    │    config.json       │
                    │  (shared on disk)    │
                    │  + autostart flag    │
                    └─────────────────────┘
```

---

## New Components Required

### Component 1: `autostart` module (new, shared or host)

**Responsibility:** Create and delete a Windows Task Scheduler entry for the host executable. Expose a simple two-function interface: `enable(exe_path)` and `disable()`.

**Location:** `host/autostart.py` or `shared/autostart.py`. Place in `host/` if only the control panel calls it via `config.json` toggle. Place in `shared/` if any future component also needs it. `host/autostart.py` is sufficient for v1.1.

**Interface:**
```python
def enable_autostart(exe_path: str) -> None:
    """Register host.exe as a Task Scheduler ONLOGON task."""

def disable_autostart() -> None:
    """Remove the Task Scheduler task if it exists."""

def is_autostart_enabled() -> bool:
    """Return True if the task exists in Task Scheduler."""
```

**Implementation approach:** Call `schtasks.exe` via `subprocess.run()` using the existing `subprocess` module — no new dependencies. This avoids `win32com.taskscheduler` complexity and does not require pywin32 to be imported in the control panel's frozen context. The `schtasks /query` call is the status check, `schtasks /create` enables, and `schtasks /delete` disables.

### Component 2: Autostart toggle UI in control panel (modified: `control_panel/main_window.py`)

**Responsibility:** A new "Startup" tab (or group within the Layout tab) containing a checkbox "Start MonitorControl host automatically at login". On change it calls `autostart.enable()` or `autostart.disable()`. The checkbox initial state is populated by `autostart.is_autostart_enabled()`.

**Does NOT require saving to config.json.** Autostart state lives in Task Scheduler, not in config. The toggle acts immediately — no Save button required for this control.

### Component 3: `build/` directory and PyInstaller spec files (new)

**Responsibility:** Reproducible build scripts for both executables.

```
build/
├── control_panel.spec    # PyInstaller spec for MonitorControl.exe
├── host.spec             # PyInstaller spec for host.exe (if packaged)
└── build.py              # Optional: orchestrates both builds
```

---

## Autostart Implementation: Task Scheduler vs Registry Run Key

### Decision: Use Task Scheduler (ONLOGON trigger)

**Rationale:**

| Criterion | Task Scheduler | Registry HKCU\Run |
|-----------|---------------|-------------------|
| No console window | Controlled by `/f` flag + `pythonw` / windowed exe | Requires `pythonw.exe` wrapper; does not apply to `.exe` |
| Implementation complexity | 3 `schtasks` subprocess calls | 3 `winreg` calls |
| Already requires pywin32? | No — `schtasks.exe` is a system utility | Yes — or stdlib `winreg` (no new dep) |
| User visibility | Visible in Task Scheduler UI (transparent) | Hidden unless user checks registry |
| UAC required? | No — ONLOGON with `/ru <current user>` does not require elevation | No — HKCU does not require elevation |
| Startup delay control | Yes — `/delay 0:05` to wait 5s after login | No |
| Working directory control | Yes — `/tr "\"path\to\host.exe\"" /sd <workdir>` | Command string only; no separate workdir |
| Antivirus sensitivity | Lower (system-blessed mechanism) | Higher (HKCU Run keys are an ATT&CK technique T1547.001) |

Task Scheduler wins on working directory control (critical for config.json resolution — see below) and on working directory being settable in the task definition itself.

**Registry Run key is viable** and simpler code, but the working directory problem makes it harder: the process working directory from a HKCU Run launch is typically `%WINDIR%\System32` or the user profile, not the exe directory, requiring the code to fall back to `sys.executable` path resolution regardless.

### schtasks Command Pattern

```
# Enable (run as current user, at logon, no interactive requirement)
schtasks /create /tn "MonitorControl Host" /tr "\"C:\path\to\host.exe\"" /sc ONLOGON /ru <username> /f /rl HIGHEST

# Disable
schtasks /delete /tn "MonitorControl Host" /f

# Query status (returns non-zero exit if task does not exist)
schtasks /query /tn "MonitorControl Host"
```

The `/rl HIGHEST` flag is optional for a windowed app but prevents UAC prompts if the host ever needs elevation for ClipCursor on locked-down machines. For this app it is not required — ClipCursor via pywin32 works at normal user privilege.

The `/f` flag on `/create` overwrites an existing task of the same name silently — safe to call on every "enable" toggle.

**No console window** is handled by the exe itself (PyInstaller `--windowed` flag), not by the task definition. A `--windowed` exe never shows a console regardless of how it is launched.

---

## PyInstaller Packaging: Which Executables Need It

### Control Panel: Needs packaging (EXEC-01..04)

The control panel is a standalone PyQt6 app intended for users who do not have Python installed. It must be packaged as a `.exe`. This is the primary packaging target.

### Host: Does NOT need packaging for v1.1

The autostart requirement (STRT-01..04) only specifies that the host launches without a visible terminal/console window. This can be achieved without packaging by:
- Running `pythonw.exe host\main.py` from the Task Scheduler task (no console, just like a `.exe`)
- Or packaging it as a secondary goal (EXEC scope only mentions control panel)

**However:** If the control panel `.exe` calls `autostart.enable()` and needs to specify the host executable path, the path it registers depends on whether the host is a `.py` (requires Python) or a `.exe` (standalone). For clean distribution (the milestone goal of "no Python environment required"), the host should also be packaged. The PROJECT.md scope is ambiguous — "Control panel packaged as standalone .exe" is specified but the host requirement is only "no terminal required."

**Build order implication:** Package host first (its spec is simpler — no PyQt6 plugin complexity), then control panel, so the control panel's autostart `enable()` can hardcode the path to `host.exe` in the same distribution directory.

---

## PyInstaller Path Resolution: The Critical Problem

### The Problem

Both `host/main.py` and `control_panel/__main__.py` currently reference `config.json` as a bare filename:

```python
# host/main.py line 87
config_loader = ConfigLoader("config.json", pm, window.compositor, after_reload=reapply_clip)

# control_panel/__main__.py line 9
window = ControlPanelWindow(config_path="config.json")
```

A bare `"config.json"` resolves against `os.getcwd()` — the process working directory at launch time. When launched from Task Scheduler or by double-clicking a `.exe`, the working directory is **not** guaranteed to be the directory containing the `.exe`.

### The Fix: exe-relative path resolution

The correct pattern uses `sys.executable` (frozen) or `__file__` (source) to anchor the path:

```python
import sys
import os

def get_config_path() -> str:
    """Return absolute path to config.json next to the executable (or script root)."""
    if getattr(sys, 'frozen', False):
        # PyInstaller frozen: sys.executable is the .exe path
        base = os.path.dirname(sys.executable)
    else:
        # Development: resolve relative to project root
        # __file__ here is host/main.py; go up one level
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")
```

This function can live in `shared/paths.py` and be called by both host and control panel.

### PyInstaller 6.x Path Details

- **One-folder build (recommended):** `sys.executable` points to the `.exe` inside the output folder. `os.path.dirname(sys.executable)` is the folder containing the `.exe` and all bundled DLLs. `config.json` should be placed beside the `.exe` at distribution time — it is NOT bundled (it is user-mutable).
- **One-file build (avoid for this project):** The `.exe` extracts to a temp directory on each run. `sys._MEIPASS` points to the temp dir, `sys.executable` points to the single `.exe`. An external `config.json` would need to be alongside the single `.exe`, resolved via `os.path.dirname(sys.executable)`. The temp dir extraction on each run also causes a startup delay and makes `multiprocessing` subprocess spawning more complex.

**Recommendation: Use one-folder (`--onedir`) for both executables.** Reasoning:
1. Faster startup (no extraction step).
2. `sys.executable` directory equals the bundle directory — `config.json` can live beside the exe.
3. Multiprocessing subprocess spawning is straightforward: child processes re-use the already-unpacked `_internal/` directory.
4. Easier to verify and debug (files are visible on disk).

---

## Subprocess Spawning from Frozen Host

### The Problem

`host/main.py` uses `multiprocessing.Process(target=run_pomodoro_widget, ...)` with `set_start_method("spawn")`. Under `spawn`, Python serializes the target function reference and re-executes `sys.executable` with special arguments to locate the target.

In a frozen `.exe`, `sys.executable` is the frozen executable itself (not `python.exe`). The child processes will re-execute the `.exe` with multiprocessing bootstrap arguments. This works correctly **if**:

1. `multiprocessing.freeze_support()` is called at the top of the `if __name__ == "__main__"` block — PyInstaller 3.3+ adds this automatically via a runtime hook, but calling it explicitly in `main.py` is defensive and harmless.
2. The target functions (`run_pomodoro_widget`, `run_calendar_widget`, `run_notification_widget`) are importable from the frozen executable's module namespace.
3. The widget functions do NOT import PyQt6 (already satisfied — they use Pillow only).

**No code change is required** for multiprocessing to work in one-folder mode. The existing `multiprocessing.set_start_method("spawn")` + target function references are already compatible with PyInstaller's frozen multiprocessing support.

**If the host is also packaged as a `.exe`:** The child widget processes will use `sys.executable` (the host exe) as their interpreter. This is correct — they re-enter the exe via the multiprocessing bootstrap and call the target function. The widget processes do NOT unpack the `.exe` again; they reuse the already-unpacked `_internal/` directory from the parent (PyInstaller 6.9+ behavior).

---

## PyInstaller spec: Control Panel

### Hidden Imports to Declare

PyInstaller's static import analysis may miss the following:

| Import | Reason it may be missed | Declaration |
|--------|-------------------------|-------------|
| `winreg` | Only used in `autostart.py` which is new | `--hidden-import winreg` |
| `win32api`, `win32con`, `win32security` | pywin32 DLLs have their own loader; PyInstaller has a hook for `pywin32` but older versions needed explicit hidden imports | Test at build time; add if needed |
| `PyQt6.QtWidgets`, `PyQt6.QtCore`, `PyQt6.QtGui` | Usually auto-detected; verify | Auto |
| `control_panel.*`, `shared.*` | Local packages — must be on the module path at analysis time | Ensure `pathex` includes project root in spec |

### Data Files to Bundle

`config.json` must **NOT** be bundled inside the exe. It is user-mutable and must exist alongside the `.exe` in the distribution folder. Do not add it to `datas` in the spec.

Font files (if any are bundled as assets) would go in `datas`. Check `widgets/` for any asset files at build time.

### Recommended Spec Skeleton

```python
# build/control_panel.spec
a = Analysis(
    ['control_panel/__main__.py'],
    pathex=['.'],                         # project root on analysis path
    binaries=[],
    datas=[],                             # no bundled data files for v1.1
    hiddenimports=['winreg'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='MonitorControl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                        # --windowed: no console window
    icon=None,                            # set to .ico path when available
)
coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    name='MonitorControl',
)
```

The `console=False` flag is equivalent to `--windowed` and is the correct setting for the control panel.

---

## Data Flow Changes for v1.1

### New: Autostart Toggle Flow

```
User checks/unchecks "Start at login" in control_panel Startup tab
    │
    ├── is_checked = True
    │       └── autostart.enable(host_exe_path)
    │               └── subprocess.run(["schtasks", "/create", ...])
    │
    └── is_checked = False
            └── autostart.disable()
                    └── subprocess.run(["schtasks", "/delete", ...])

# No config.json write needed — state lives in Task Scheduler
# Checkbox initial state on panel open:
autostart.is_autostart_enabled()
    └── subprocess.run(["schtasks", "/query", ...])
    └── returncode == 0  →  enabled
```

### Modified: Config Path Resolution Flow

```
# Before v1.1 (broken in packaged context):
config_path = "config.json"                    # resolves against cwd

# After v1.1 (correct in all contexts):
config_path = shared.paths.get_config_path()   # resolves against exe dir or project root
```

This change touches:
- `host/main.py` — `ConfigLoader("config.json", ...)` → `ConfigLoader(get_config_path(), ...)`
- `host/main.py` — `config_dir = os.path.dirname(os.path.abspath("config.json"))` → `config_dir = os.path.dirname(get_config_path())`
- `control_panel/__main__.py` — `ControlPanelWindow(config_path="config.json")` → `ControlPanelWindow(config_path=get_config_path())`

### Modified: Command File Path

The pomodoro command file path in `host/main.py` is derived from `config.json`'s directory:

```python
config_dir = os.path.dirname(os.path.abspath("config.json"))
cmd_path = os.path.join(config_dir, "pomodoro_command.json")
```

This automatically becomes correct once `config.json` is resolved to the exe directory — `config_dir` will be the exe's folder and `pomodoro_command.json` will be written there. No separate fix needed beyond fixing the config path resolution.

---

## Component Map: New vs Modified

| Component | Status | Location | Change |
|-----------|--------|----------|--------|
| `shared/paths.py` | **New** | `shared/paths.py` | `get_config_path()` helper |
| `host/autostart.py` | **New** | `host/autostart.py` | Task Scheduler enable/disable/query |
| `control_panel/main_window.py` | **Modified** | existing | Add Startup tab with autostart toggle |
| `host/main.py` | **Modified** | existing | Use `get_config_path()` instead of bare `"config.json"` |
| `control_panel/__main__.py` | **Modified** | existing | Use `get_config_path()` instead of bare `"config.json"` |
| `build/control_panel.spec` | **New** | `build/` | PyInstaller spec for control panel exe |
| `build/host.spec` | **New** (optional) | `build/` | PyInstaller spec for host exe |

---

## Anti-Patterns for v1.1

### Anti-Pattern 1: Storing Autostart State in config.json

**What people do:** Add an `"autostart": true` key to config.json and read it on startup.

**Why it's wrong:** config.json is the host's hot-reload config. The host would need to read a flag telling it to start itself — circular. The actual autostart state is a Windows system concern, not an app config concern. Task Scheduler is the ground truth; polling config.json to mirror it adds a synchronization surface that can drift.

**Do this instead:** Call `schtasks /query` to get the current state. State lives in exactly one place: Task Scheduler. No flag in config.json.

### Anti-Pattern 2: Bundling config.json Inside the .exe

**What people do:** Add `config.json` to PyInstaller's `datas` list so it gets bundled into `_internal/`.

**Why it's wrong:** config.json is the sole IPC channel between control panel and host. If it is bundled read-only inside the exe, the control panel cannot write to it (it would write next to the exe while the host reads from the read-only bundle path). Users cannot manually edit it either.

**Do this instead:** Keep config.json external to both executables, alongside the executables in the distribution directory. Both processes locate it via `get_config_path()` anchored to `sys.executable`'s directory.

### Anti-Pattern 3: One-File Build for the Host

**What people do:** Use `--onefile` for the host exe to produce a single portable file.

**Why it's wrong:** One-file builds extract to a temp directory on each run. Multiprocessing child processes (widget subprocesses) also use `sys.executable` which points to the single `.exe`, causing each child spawn to attempt extraction into another temp dir. This compounds startup latency and can cause race conditions where the parent's extraction hasn't finished when the first child tries to reuse the temp dir.

**Do this instead:** Use `--onedir` (the default). The `_internal/` directory is extracted once at install time, not at runtime. Widget subprocesses reuse it immediately.

### Anti-Pattern 4: Calling schtasks with a Relative Path in /tr

**What people do:** Register `schtasks /create /tr "host.exe"` without an absolute path.

**Why it's wrong:** Task Scheduler resolves the program path relative to `System32` or the user profile, not the exe's directory. The task will fail to find the executable.

**Do this instead:** Always pass `sys.executable` (the absolute path to the host exe at the time the control panel registers the task) as the `/tr` argument. Quote it to handle spaces in the path.

### Anti-Pattern 5: Resolving config.json Relative to `__file__` in the Spec

**What people do:** In production code, use `os.path.dirname(__file__)` to find config.json.

**Why it's wrong:** In a frozen exe, `__file__` for `host/main.py` points inside `sys._MEIPASS/_internal/`, which is the bundle directory — not the directory beside the exe. `config.json` is external (not bundled) and lives beside the exe.

**Do this instead:** Use `os.path.dirname(sys.executable)` when `sys.frozen` is set. Use `__file__`-relative paths only for files that ARE bundled (e.g., fonts, images in `datas`). For user-mutable external files, always anchor to `sys.executable`.

---

## Build Order Recommendation

Phase ordering for v1.1 implementation:

```
Step 1: shared/paths.py
    Reason: Both host and control panel depend on it.
    Risk: None — pure Python, no new dependencies.

Step 2: host/main.py + control_panel/__main__.py path fix
    Reason: Fix config.json resolution before any packaging work.
             If this is broken in packaged context, everything downstream fails.
    Risk: Low — well-understood change, can be validated in source mode first.

Step 3: host/autostart.py (Task Scheduler integration)
    Reason: Must be written and testable in source mode before control panel
            UI is wired up. schtasks calls can be validated in isolation.
    Risk: Medium — subprocess.run(schtasks) parsing exit codes; test with
            /query for an existing and non-existing task name.

Step 4: control_panel/main_window.py Startup tab
    Reason: Wires the autostart module into the UI. Depends on Step 3.
    Risk: Low — UI work only.

Step 5: PyInstaller build for control_panel (control_panel.spec)
    Reason: The main packaging deliverable. Depends on Steps 1-4 being correct.
    Risk: High — likely requires iteration on hidden imports; run pyi-makespec
            first to generate base spec, then refine.

Step 6 (optional): PyInstaller build for host (host.spec)
    Reason: If clean distribution without Python is required for the host.
            Not strictly required by STRT spec; required by distribution goal.
    Risk: High — multiprocessing + winrt + pywin32 in a single frozen exe
            is the most complex build; test widget subprocess spawning
            explicitly after packaging.
```

---

## Integration Points

### Internal Boundaries (v1.1 changes)

| Boundary | Communication | v1.1 Change |
|----------|---------------|-------------|
| Control panel ↔ Task Scheduler | `subprocess.run(["schtasks", ...])` | New — via `host/autostart.py` |
| Control panel ↔ Host (autostart path) | `sys.executable` path passed to `schtasks /create /tr` | New — control panel must know host exe path |
| Host ↔ config.json | `get_config_path()` anchored to exe dir | Modified path resolution |
| Control panel ↔ config.json | `get_config_path()` anchored to exe dir | Modified path resolution |
| PyInstaller ↔ multiprocessing | `freeze_support()` + `sys.executable` bootstrap | Existing pattern; verified compatible |

### Knowing the Host Exe Path from the Control Panel

This is a practical concern: when the control panel calls `autostart.enable()`, it needs to know the path to `host.exe`. Options:

1. **Assume co-location (recommended for v1.1):** `host.exe` lives in the same distribution directory as `MonitorControl.exe`. The control panel computes `os.path.join(os.path.dirname(sys.executable), "host.exe")`. Simple and correct for the intended distribution layout.
2. **Configurable path in config.json:** Store `"host_exe_path"` in config.json. More flexible, but adds a config key that must be set at install time.
3. **Registry lookup:** Read the host path from a registry install key. Requires an installer.

Option 1 is correct for v1.1 given the distribution model is "copy both exes to same folder."

---

## Sources

- PyInstaller runtime information (`sys._MEIPASS`, `sys.frozen`): [PyInstaller 6.19.0 — Run-time Information](https://pyinstaller.org/en/stable/runtime-information.html)
- PyInstaller multiprocessing recipe: [PyInstaller Wiki — Recipe Multiprocessing](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing)
- PyInstaller common issues (one-file + multiprocessing): [PyInstaller 6.19.0 — Common Issues](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
- PyInstaller PyQt6 packaging tutorial: [Python GUIs — Packaging PyQt6 for Windows with PyInstaller](https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/)
- schtasks create reference: [Microsoft Learn — schtasks create](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create)
- Registry Run keys reference: [Microsoft Learn — Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys)
- Task Scheduler vs Registry Run key comparison: [Windows Automatic Startup Locations — gHacks](https://www.ghacks.net/2016/06/04/windows-automatic-startup-locations/)

---
*Architecture research for: MonitorControl v1.1 — Autostart and Distribution*
*Researched: 2026-03-27*
