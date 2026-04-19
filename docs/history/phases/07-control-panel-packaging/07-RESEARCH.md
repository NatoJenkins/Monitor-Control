# Phase 7: Control Panel Packaging - Research

**Researched:** 2026-03-27
**Domain:** PyInstaller 6 / PyQt6 / Windows .exe packaging
**Confidence:** HIGH

## Summary

Phase 7 packages the control panel (`control_panel/__main__.py`) as a standalone Windows `.exe` using PyInstaller 6 in `--onedir` mode. This is the established v1.1 decision: `--onedir` was chosen over `--onefile` for faster startup, no AV temp-extraction, and multiprocessing compatibility (documented in STATE.md Accumulated Context).

The primary technical risk is a **PyInstaller 6 path resolution breaking change**: all bundled files are placed inside a `_internal/` subdirectory by default, which means `Path(__file__).resolve().parent.parent` inside `shared/paths.py` resolves to `_internal/` — not the exe directory. This breaks `get_config_path()` in the frozen app. The cleanest mitigation is to set `contents_directory='.'` in the `EXE()` call of the `.spec` file, which restores the flat layout where `Path(__file__).parent.parent` correctly resolves to the exe's directory.

The secondary risk is a **`winreg` import path in `autostart.py`**: at module level, `autostart.py` imports `winreg` directly (not via function-level import). `winreg` is a Windows stdlib built-in; PyInstaller collects it automatically. No hidden import declaration is needed.

**Primary recommendation:** Generate spec with `pyi-makespec`, edit EXE() to add `console=False`, `icon=build/icon.ico`, `contents_directory='.'`, then verify frozen `config.json` resolution. Create a 256x256 `.ico` file and commit it at `build/icon.ico`.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PKG-01 | Control panel packaged as standalone .exe (no Python environment required) | PyInstaller 6.19.0 bundles PyQt6 + all deps with auto-hooks; `pip install pyinstaller` then `pyinstaller build/control_panel.spec` |
| PKG-02 | Control panel .exe launches without a terminal or console window | `console=False` in EXE() spec call; confirmed supported parameter in PyInstaller 6.x |
| PKG-03 | Control panel .exe displays application icon in Explorer/Task Manager | `icon='build/icon.ico'` in EXE() spec call; `.ico` must include 16x16, 32x32, 48x48, 256x256 sizes |
| PKG-04 | PyInstaller build is reproducible via a committed `.spec` file | `.spec` file committed at `build/control_panel.spec`; rebuild with `pyinstaller build/control_panel.spec` from project root |
</phase_requirements>

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pyinstaller | 6.19.0 | Bundle Python app + deps into standalone exe | Industry standard for Python exe packaging; official PyQt6 hooks built-in |
| pyinstaller-hooks-contrib | latest | PyInstaller hooks for 3rd-party packages | Maintained alongside PyInstaller; auto-updated hooks for Qt, pywin32, etc. |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow (already in env) | current | Create/convert .ico files from PNG | Generating multi-size .ico during build tooling |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| --onedir | --onefile | --onefile slower startup, AV false positives, incompatible with multiprocessing; already rejected in v1.1 decisions |
| pyi-makespec + edit spec | direct CLI flags | .spec file is required for PKG-04 reproducibility; CLI flags alone cannot be committed |

**Installation:**
```bash
pip install pyinstaller pyinstaller-hooks-contrib
```

**Version verification (run before writing spec):**
```bash
pip show pyinstaller
```
Verified current: 6.19.0 (released 2026-02-14, confirmed from PyPI).

## Architecture Patterns

### Recommended Project Structure

```
MonitorControl/
├── build/
│   ├── control_panel.spec    # committed, reproducible build config
│   └── icon.ico              # committed application icon
├── dist/
│   └── MonitorControl/       # output — gitignored
│       ├── MonitorControl.exe
│       └── (Qt DLLs, _internal/ or flat)
├── control_panel/
│   └── __main__.py           # entry point
└── shared/
    └── paths.py              # must work frozen
```

### Pattern 1: Minimal onedir Windowed Spec (Flat Layout)

**What:** A `.spec` file that produces a windowed, iconified, flat onedir build from the project root.

**When to use:** Single-file control panel with no embedded resources; config.json lives beside the exe and is user-editable.

**Example:**
```python
# build/control_panel.spec
# Source: PyInstaller 6.x official docs + pythonguis.com PyQt6 guide
import sys
from pathlib import Path

block_cipher = None
project_root = str(Path(SPECPATH).parent)

a = Analysis(
    [str(Path(project_root) / 'control_panel' / '__main__.py')],
    pathex=[project_root],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MonitorControl',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(Path(project_root) / 'build' / 'icon.ico'),
    contents_directory='.',   # CRITICAL: disables _internal/ subdirectory
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='MonitorControl',
)
```

### Pattern 2: Frozen-Aware Path Resolution in `shared/paths.py`

**What:** Guard using `sys.frozen` + `sys.executable` as fallback for PyInstaller 6 onedir mode.

**When to use:** If `contents_directory='.'` is NOT used (i.e., `_internal/` is present), `Path(__file__).parent.parent` resolves to `_internal/`, not the exe directory.

**Example:**
```python
# shared/paths.py — frozen-aware variant (use if not using contents_directory='.')
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    # PyInstaller frozen: exe directory is sys.executable's parent
    _PROJECT_ROOT = Path(sys.executable).resolve().parent
else:
    # Development: paths.py is at shared/paths.py, project root is parent.parent
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
```

**Note:** The `contents_directory='.'` spec approach (Pattern 1) is preferred because it requires no code changes to `shared/paths.py` and keeps the frozen/dev distinction invisible. Use Pattern 2 only if the spec approach is blocked.

### Anti-Patterns to Avoid

- **`--onefile` mode:** Slower startup due to temp extraction; AV false positives; incompatible with multiprocessing. Already rejected in project decisions.
- **Bare `pyinstaller control_panel/__main__.py` without a spec:** CLI invocation is not reproducible (PKG-04 requires a committed `.spec`).
- **Relying on `sys._MEIPASS` for config.json:** `sys._MEIPASS` points inside `_internal/`, where config.json is NOT placed (it lives beside the exe, user-editable).
- **UPX compression:** Causes AV false positives on Windows; disabled with `upx=False`.
- **Bundling `config.json` into the exe via `datas`:** Config is user-editable and must live beside the exe, not frozen inside the bundle.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dependency collection | Manual DLL copying | PyInstaller 6.19.0 | PyInstaller walks the import graph, handles Qt platform plugins, VC runtimes, pywin32 DLLs automatically |
| Icon embedding | Resource hacker / rc files | `icon=` param in EXE() | PyInstaller links the .ico directly into the exe PE resources during build |
| Console suppression | Subprocess detach / FreeConsole() | `console=False` in EXE() | PyInstaller compiles with the WIN32 subsystem flag; no runtime workaround needed |
| .ico creation | PIL scripting in spec | Any image editor or `pillow` + `ico` library | .ico must embed multiple sizes (16, 32, 48, 256); editors handle this correctly |

**Key insight:** PyInstaller's hooks for PyQt6 are battle-tested. The only hand-rolling needed is the path-resolution fix (Pattern 1 or 2 above) — everything else is automatic.

## Common Pitfalls

### Pitfall 1: `_internal/` Subdirectory Breaks `Path(__file__).parent.parent`

**What goes wrong:** PyInstaller 6.0+ places all bundled modules inside `_internal/` by default. `shared/paths.py` is bundled as `_internal/shared/paths.py`. So `Path(__file__).parent.parent` resolves to `_internal/`, not the exe's directory. `get_config_path()` then looks for `_internal/config.json`, which does not exist.

**Why it happens:** PyInstaller 6.0 introduced `_internal/` as the contents directory (configurable via `--contents-directory`). The old assumption that `os.path.dirname(sys.executable) == sys._MEIPASS` no longer holds.

**How to avoid:** Set `contents_directory='.'` in `EXE()` to flatten the layout (all files land beside the exe), OR add a `sys.frozen` guard in `shared/paths.py` (Pattern 2).

**Warning signs:** `FileNotFoundError` or `config.json not found` when launching the exe; the error appears if the app shows any dialog or crashes silently (windowed mode hides tracebacks).

### Pitfall 2: Silent Crashes in Windowed Mode

**What goes wrong:** `console=False` suppresses the console window. Unhandled exceptions that would normally print a traceback crash the process silently — nothing visible to the user.

**Why it happens:** `sys.stdout` and `sys.stderr` are `None` in windowed mode. `host/main.py` already null-guards these (INFRA-02), but `control_panel/__main__.py` does not have this guard.

**How to avoid:** Add null-guard for stdout/stderr at the top of `control_panel/__main__.py` before any imports that might print. The same pattern from `host/main.py` applies. Alternatively, wrap `main()` in a try/except that uses `QMessageBox` to surface uncaught exceptions.

**Warning signs:** Exe appears in Task Manager briefly then disappears; no error dialog shown.

### Pitfall 3: pywin32 DLL Conflict with PyQt6

**What goes wrong:** Using both `pywin32` and `PyQt6` in the same frozen app could cause `ImportError: DLL load failed while importing pywintypes` due to VCRUNTIME140_1.dll search path conflicts.

**Why it happens:** PyInstaller < 6.1.0 randomized library search path ordering, causing the Qt-provided VCRUNTIME to shadow Python's copy. `winreg` is a stdlib built-in; `pywin32` (pywin32==311) provides `win32api`, etc.

**How to avoid:** Use PyInstaller >= 6.1.0 (use 6.19.0). The control panel's `autostart.py` uses only `winreg` (stdlib built-in, always collected), not `pywin32` extensions directly. If `pywin32` is collected as a transitive dep, PyInstaller 6.1.0+ handles DLL ordering correctly.

**Warning signs:** `ImportError: DLL load failed while importing pywintypes` in test launch of the exe.

### Pitfall 4: Build Environment Has Multiple Qt Bindings

**What goes wrong:** If `PySide6` or `PyQt5` is installed alongside `PyQt6` in the build venv, PyInstaller aborts the build: "Attempting to collect multiple Qt bindings."

**Why it happens:** PyInstaller 6.x added an explicit guard; it cannot safely bundle two Qt bindings.

**How to avoid:** Build in a clean virtual environment containing only the packages in `requirements.txt`. Add `pip check` to the build workflow.

**Warning signs:** Build aborts with "Cannot mix Qt bindings" error message.

### Pitfall 5: Icon Not Visible in Explorer/Task Manager After First Build

**What goes wrong:** Icon appears as generic Python icon even though `icon=` was set.

**Why it happens:** Windows icon cache (`IconCache.db`) may be stale. Also: the `.ico` file must contain multiple sizes; a single-size .ico may appear blurry or default.

**How to avoid:** Create a multi-size `.ico` (16x16, 32x32, 48x48, 256x256). After build, kill `explorer.exe` or run `ie4uinit.exe -show` to refresh icon cache.

**Warning signs:** Exe has the correct icon embedded (verifiable with Resource Hacker) but Explorer still shows the old icon.

### Pitfall 6: `disable_windowed_traceback=False` Should Stay False

**What goes wrong:** Setting `disable_windowed_traceback=True` completely suppresses the Windows error dialog on crash — useful only for production, harmful during development.

**How to avoid:** Keep `disable_windowed_traceback=False` so Windows shows the unhandled exception dialog during testing. Only set to `True` if a completely silent failure is required.

## Code Examples

### Generating the .spec File (Starting Point)

```bash
# Source: PyInstaller 6.19.0 official docs
# Run from project root to generate initial spec
pyi-makespec \
  --onedir \
  --windowed \
  --name MonitorControl \
  --icon build/icon.ico \
  --specpath build \
  control_panel/__main__.py
```

Then edit `build/control_panel.spec` to add `pathex=[project_root]` and `contents_directory='.'`.

### Rebuilding from Spec

```bash
# Source: PyInstaller 6.19.0 official docs
pyinstaller build/control_panel.spec
# Output: dist/MonitorControl/MonitorControl.exe
```

### Verifying Frozen Path Resolution (Smoke Test)

```bash
# After build, run from a different directory to verify path independence
cd C:\Temp
"E:\ClaudeCodeProjects\MonitorControl\dist\MonitorControl\MonitorControl.exe"
# Must open the control panel, loading config.json from the exe's own directory
```

### Creating a Multi-Size .ico with Pillow

```python
# build/make_icon.py — run once, commit icon.ico
from PIL import Image

# Source image: provide a 256x256 PNG
img = Image.open("build/icon_source.png").convert("RGBA")
sizes = [(16, 16), (32, 32), (48, 48), (256, 256)]
icons = [img.resize(s, Image.LANCZOS) for s in sizes]
icons[0].save("build/icon.ico", format="ICO", append_images=icons[1:], sizes=sizes)
```

### Null-Guard for Windowed Mode (control_panel/__main__.py)

```python
# Pattern from host/main.py — apply same guard to control panel entry point
import sys, os
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| onedir: all files beside exe | onedir: files in `_internal/` subdirectory | PyInstaller 6.0 (2023) | `Path(__file__).parent.parent` no longer resolves to exe directory; fix with `contents_directory='.'` |
| `os.path.dirname(sys.executable) == sys._MEIPASS` | These are now different paths | PyInstaller 6.0 | Code relying on equality breaks silently |
| Multiple Qt bindings silently bundled (one wins) | Build aborts if multiple Qt bindings present | PyInstaller 6.x | Requires clean venv with one Qt binding |
| pywin32 + PyQt DLL conflict (PyInstaller < 6.1) | Fixed in 6.1.0+ | PyInstaller 6.1 (2024) | No longer need workaround; use 6.19.0 |

**Deprecated/outdated:**
- `--onefile`: Still available but rejected for this project (multiprocessing, AV, startup).
- `sys.path.insert(0, ...)` hacks in spec: Replaced by `pathex=` in Analysis.

## Open Questions

1. **Does `control_panel/autostart.py`'s `_get_pythonw()` need to change for the packaged exe?**
   - What we know: `_get_pythonw()` returns `pythonw.exe` beside `sys.executable`. In the frozen exe, `sys.executable` is `MonitorControl.exe`, so `pythonw.exe` will not be found there. This breaks the autostart registry entry when set from the packaged exe.
   - What's unclear: The autostart feature (Phase 6) was designed for the development/pythonw.exe workflow. Host packaging is deferred to v2. Should the packaged control panel's autostart button point to the exe or to `launch_host.pyw`?
   - Recommendation: This is a v2 concern (HPKG-02). For Phase 7, the Startup tab in the packaged exe will still function for reading registry state (STRT-03). Writing a new autostart entry from a packaged exe that points to `launch_host.pyw` requires finding Python separately — out of scope. The planner should add a task to verify that `is_autostart_enabled()` works from the frozen exe (read-only registry access via stdlib `winreg` — should work fine), and document that enable/disable from the exe is a v2 concern.

2. **Does the project need a source `.png` for the icon, or can a placeholder `.ico` be used?**
   - What we know: PKG-03 requires a custom icon distinguishable from generic Python. An icon file must exist at build time.
   - What's unclear: No icon asset currently exists in the project.
   - Recommendation: The plan should include a task to create `build/icon.ico`. A simple placeholder (solid color with "MC" text, or a monitor glyph) is sufficient for PKG-03. The planner should task this explicitly.

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest >= 8.0 |
| Config file | `pytest.ini` (exists at project root) |
| Quick run command | `pytest tests/ -x -q` |
| Full suite command | `pytest tests/` |

### Phase Requirements -> Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PKG-01 | Exe exists and launches, control panel opens | smoke (manual) | `dist/MonitorControl/MonitorControl.exe` launches visually | N/A — Wave 0 |
| PKG-02 | No console window on launch | smoke (manual) | Launch exe; verify no black window appears | N/A — manual |
| PKG-03 | Icon visible in Explorer/Task Manager | smoke (manual) | Visual check after refresh of icon cache | N/A — manual |
| PKG-04 | Spec file exists and is committed | unit | `pytest tests/test_packaging.py::test_spec_file_exists -x` | ❌ Wave 0 |
| PKG-04 | Build is reproducible from spec | smoke (manual) | `pyinstaller build/control_panel.spec` from clean checkout | N/A — manual |
| paths | get_config_path() resolves to exe dir in frozen context | unit | `pytest tests/test_packaging.py::test_frozen_path_guard -x` | ❌ Wave 0 |

**Note:** PKG-01, PKG-02, PKG-03 are fundamentally manual smoke tests — they require a real GUI launch on Windows. Automated tests can only verify preconditions (spec exists, icon file exists, dist output exists after build).

### Sampling Rate

- **Per task commit:** `pytest tests/ -x -q`
- **Per wave merge:** `pytest tests/`
- **Phase gate:** Full suite green + manual smoke of `MonitorControl.exe` before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_packaging.py` — covers PKG-04 (spec file exists, icon file exists, dist dir postcondition)
- [ ] `build/` directory — must exist with `control_panel.spec` and `icon.ico` before build task

## Sources

### Primary (HIGH confidence)

- PyInstaller 6.19.0 official docs (spec-files.html) — EXE() parameters, contents_directory, SPECPATH
- PyInstaller 6.19.0 official docs (runtime-information.html) — sys._MEIPASS, __file__ in frozen apps, sys.executable
- PyInstaller 6.19.0 official docs (common-issues-and-pitfalls.html) — windowed mode, sys.stdout/stderr None
- PyPI pyinstaller page — version 6.19.0, released 2026-02-14

### Secondary (MEDIUM confidence)

- https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/ — PyQt6 packaging tutorial (updated Dec 2025); confirmed PyInstaller auto-hooks for PyQt6, windowed mode, icon setup
- PyInstaller changelog 6.0.0 — _internal directory introduction; changelog 6.1.0 — pywin32/PyQt DLL fix

### Tertiary (LOW confidence)

- Community reports: icon cache refresh required after first build (Windows-specific behavior, not officially documented)
- Community reports: `pyinstaller-hooks-contrib` should be updated alongside PyInstaller (standard practice, not enforced)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — PyInstaller 6.19.0 confirmed on PyPI; auto-hooks for PyQt6 confirmed in official docs and tutorial
- Architecture: HIGH — spec file structure from official docs; `contents_directory='.'` behavior confirmed from changelog and official usage docs
- Pitfalls: HIGH (paths), MEDIUM (icon cache) — path issue confirmed by official runtime docs; icon cache is empirical community knowledge
- `_internal` breaking change: HIGH — PyInstaller 6.0 changelog + runtime-information.html both confirm behavior

**Research date:** 2026-03-27
**Valid until:** 2026-06-27 (PyInstaller stable; Qt6 hooks stable; 90-day window reasonable)
