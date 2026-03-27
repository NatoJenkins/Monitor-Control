# Stack Research

**Domain:** Python desktop widget/dashboard framework — Windows, dedicated secondary display
**Researched:** 2026-03-27
**Confidence:** HIGH (packaging), HIGH (autostart mechanism), MEDIUM (winrt bundling hooks)

---

## Scope

This file covers ONLY the new stack additions needed for v1.1. The existing validated stack
(PyQt6 6.10.2, Pillow, pywin32 311, winrt-* 3.2.1, multiprocessing.Queue, config.json
hot-reload) is not re-researched here.

The two new capabilities are:
1. Host autostart at Windows login (no terminal window)
2. Control panel packaged as a standalone .exe (no Python environment required)

---

## Recommended Stack

### New Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| PyInstaller | 6.19.0 | Package control_panel into standalone .exe | Defacto standard for Python .exe distribution. Has explicit PyQt6 hooks in pyinstaller-hooks-contrib. Works out-of-the-box with PyQt6 — no spec-file customization needed for a pure PyQt6+pywin32 app. Does not require a C toolchain. Latest release Feb 14 2026 confirms active maintenance. |
| winreg (stdlib) | built-in | Read/write HKCU Run key for autostart | Already available — no new install. Python's built-in `winreg` module provides direct access to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. Zero new dependencies. Simpler and more predictable than win32com.client for this single-purpose task. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pyinstaller-hooks-contrib | auto (bundled with PyInstaller) | Community hooks that tell PyInstaller what to collect for PyQt6, pywin32, and other packages | Automatically installed as a PyInstaller dependency; no explicit install needed. Provides the PyQt6 hook that handles Qt plugin DLLs and platform plugins. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| PyInstaller CLI | Build the standalone .exe | `pyinstaller --onedir --noconsole --name MonitorControlPanel control_panel/__main__.py` |
| pyi-makespec | Generate a .spec file for custom build configuration | Use if hidden imports for winrt packages need to be specified manually |

---

## Installation

```bash
# Packaging tool (build-time only, not shipped with users)
pip install pyinstaller==6.19.0

# winreg is stdlib — no install needed
```

---

## Autostart Mechanism: HKCU Run Key (Recommended)

**Use `winreg` to set `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.**

### Why HKCU Run Key over Task Scheduler

| Criterion | HKCU Run Key | Task Scheduler |
|-----------|-------------|----------------|
| Requires admin rights | No — HKCU is user-writable | No for logon trigger; Yes for some settings |
| Console window suppression | Trivial: point entry at pythonw.exe | Requires "Run whether user is logged on or not" / window-station config |
| Implementation complexity | ~15 lines of stdlib winreg | ~60+ lines of win32com.client COM automation |
| User can toggle in Settings | Yes — Windows Settings > Apps > Startup shows Run-key entries | Partially — Task Scheduler UI only, not in Settings |
| Dependencies needed | None (stdlib winreg) | win32com.client (already have via pywin32, but more fragile API) |
| Reliability | High for user-session apps | High; preferred for system-level or scheduled tasks |
| Windows Settings visibility | Windows 11 Startup apps page shows Run-key entries | Does not appear in Startup apps page |

**Verdict:** HKCU Run key is the correct choice for a user-session desktop app. It requires no admin elevation, suppresses the console window by pointing at `pythonw.exe`, appears in Windows Settings Startup apps (familiar UX), and needs only stdlib `winreg`. Task Scheduler adds complexity with no benefit for this use case.

### No-Console Launch Pattern

To launch the host without a terminal window, the Run key value must point to `pythonw.exe` (not `python.exe`). `pythonw.exe` is the Windows subsystem variant that starts with `CREATE_NO_WINDOW` — no console is ever created.

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
"MonitorControl" = "C:\path\to\pythonw.exe C:\path\to\project\host\main.py"
```

The control panel uses `winreg` to write/delete this entry based on the autostart toggle. The host path should be resolved at toggle-time using `sys.executable` (which resolves to the active Python interpreter) and `__file__`.

### winreg Implementation Pattern

```python
import winreg
import sys
from pathlib import Path

APP_NAME = "MonitorControl"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"

def _pythonw_exe() -> str:
    # sys.executable is python.exe; pythonw.exe lives alongside it
    return str(Path(sys.executable).parent / "pythonw.exe")

def enable_autostart(host_main: Path) -> None:
    value = f'"{_pythonw_exe()}" "{host_main}"'
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                        winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, value)

def disable_autostart() -> None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0,
                            winreg.KEY_SET_VALUE) as key:
            winreg.DeleteValue(key, APP_NAME)
    except FileNotFoundError:
        pass  # already absent

def is_autostart_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, APP_NAME)
            return True
    except FileNotFoundError:
        return False
```

---

## Packaging: PyInstaller for Control Panel .exe

### Why PyInstaller Over Alternatives

| Tool | Status | Why Not |
|------|--------|---------|
| PyInstaller 6.19.0 | Actively maintained, released Feb 2026 | Recommended |
| cx_Freeze 8.6.0 | Actively maintained (Feb 2026 release) | More manual spec configuration needed; hook ecosystem smaller than PyInstaller-hooks-contrib; PyInstaller is the community standard for PyQt apps |
| Nuitka | Actively maintained, compiles to C++ | Requires MSVC or MinGW C toolchain; longer build times; overkill for a personal tool where startup performance is not critical; False-positive improvement is irrelevant for internal distribution |
| PyOxidizer | Last release Dec 2022 | Effectively unmaintained; use only if single-binary Rust embedding is a hard requirement |

### PyInstaller + PyQt6 Integration

PyInstaller 6.x ships with `pyinstaller-hooks-contrib`, which provides the PyQt6 hook. This hook automatically:
- Collects Qt platform plugins (`platforms/qwindows.dll`)
- Collects Qt6 DLLs (Core, Gui, Widgets)
- Handles the `PyQt6.sip` module

No `--hidden-import PyQt6` or `collect_submodules` is needed for standard PyQt6 usage.

### pywin32 Bundling Note

pyinstaller-hooks-contrib includes a pywin32 runtime hook that manages `pywin32_system32` DLL placement. A known issue exists where the pywin32 runtime hook modifies PATH in a way that conflicts with Qt's OpenSSL DLL resolution (fixed in PyInstaller 6.x for the `pywin32_system32` subdirectory interaction — see changelog). If Qt SSL errors appear in the packaged .exe, the fix is using PyInstaller >= 6.5.0.

The control panel does NOT use pywin32 (`winreg` is stdlib). This means the pywin32 hook interaction is not a concern for the control panel .exe.

### winrt Bundling

No hook for `winrt-*` packages exists in `pyinstaller-hooks-contrib`. However, the **control panel does not use winrt**. winrt is only used by the host's notification widget subprocess. The control panel only uses PyQt6 + stdlib (json, winreg, os, pathlib). No winrt hidden imports are needed for the control panel build.

If the host were ever packaged (not in scope for v1.1), winrt bundling would require a custom hook or `--collect-all winrt` flags and testing.

### multiprocessing and freeze_support

The control panel (`control_panel/__main__.py`) does not use `multiprocessing`. It is a pure PyQt6 + stdlib app. `freeze_support()` is not required. The packaging path is straightforward.

### Build Mode: onedir (Recommended)

Use `--onedir` (the default), not `--onefile`.

- `--onefile` extracts to a temp directory on each launch, causing slower startup and more frequent antivirus false positives (extraction pattern resembles malware unpacking behavior).
- `--onedir` produces a folder with the .exe and its DLLs; the .exe launches directly with no extraction step.
- For a personal tool distributed by copying a folder, `--onedir` is simpler and more reliable.

### Console Suppression: --noconsole

Use `--noconsole` (alias: `--windowed`) so no black terminal window flashes when the user opens the control panel. With `--noconsole`, `sys.stdin`, `sys.stdout`, and `sys.stderr` become `None` in the packaged exe. Any code that accesses these directly (e.g., `print()` to console) will raise `AttributeError`. The control panel has no console output so this is not a concern, but note it for future debugging: use file logging rather than print statements in packaged builds.

### Canonical Build Command

```bash
pyinstaller \
  --onedir \
  --noconsole \
  --name MonitorControlPanel \
  --icon assets/icon.ico \
  control_panel/__main__.py
```

Or via a `.spec` file for reproducible builds (preferred):

```python
# MonitorControlPanel.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['control_panel/__main__.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MonitorControlPanel',
    console=False,  # --noconsole
    icon='assets/icon.ico',
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='MonitorControlPanel',
)
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| HKCU Run key (winreg) | Task Scheduler via win32com.client | Use Task Scheduler if: (a) elevated privileges are needed at launch, (b) the task must run before user logon, (c) the task needs retry-on-failure or execution time limits. None of these apply to a user-session GUI app. |
| HKCU Run key (winreg) | Windows Startup folder shortcut | Startup folder is a valid simple alternative. Requires creating a .lnk shortcut file programmatically (needs `winshell` or win32com.client shell dispatch). More file system coupling than registry. Appears in the same Windows Settings Startup apps page as Run keys. Choose only if you want to avoid registry writes on principle. |
| HKCU Run key (winreg) | HKLM Run key | Use HKLM if the app must start for ALL users on the machine. Requires admin elevation to write. Not appropriate here — this is a single-user personal tool. |
| PyInstaller --onedir | PyInstaller --onefile | Use --onefile only if distributing via a single-file download where folder complexity is a problem. The single-file extraction step hurts startup time and antivirus reputation. For a personal tool, onedir is strictly better. |
| PyInstaller | Nuitka | Use Nuitka if you need smaller exe size, faster runtime, or significantly lower antivirus false positive rates (e.g., enterprise distribution with strict endpoint security). Build complexity and C toolchain requirement make it overkill for a personal project. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `winsdk` (monolithic) | Archived October 2024 — confirmed in PROJECT.md out-of-scope list | Modular `winrt-*` packages (already in use) |
| Task Scheduler for user-session autostart | Overkill; COM API complexity; does not appear in Windows Settings Startup apps list | HKCU Run key via `winreg` |
| win32com.client for registry writes | win32com.client is for COM automation; `winreg` is stdlib and purpose-built for registry access | `winreg` (stdlib) |
| PyInstaller `--onefile` | Slower startup, higher antivirus false-positive rate due to extraction pattern | `--onedir` |
| `schtasks.exe` subprocess calls | Requires shell=True or subprocess call to external binary; fragile CLI parsing; no error objects | `winreg` for user autostart, `win32com.client` only if full Task Scheduler feature set is needed |
| PyOxidizer | Last release Dec 2022; effectively unmaintained | PyInstaller 6.x |
| Hardcoding Python paths in the Run key | Breaks if Python is reinstalled, env changes, or project moves | Resolve paths dynamically at toggle-time using `sys.executable` and `Path(__file__).resolve()` |

---

## Stack Patterns by Variant

**If autostart is being set from a packaged control_panel.exe (future v1.2+):**

When the control panel is a standalone .exe, `sys.executable` resolves to `MonitorControlPanel.exe`, not `pythonw.exe`. In that case, the autostart Run key must point to the host's `pythonw.exe` path, which cannot be derived from `sys.executable` inside a packaged control panel. The host Python path must be stored in `config.json` at install time or resolved via the registry (`HKCU\Software\Python\PythonCore`).

For v1.1, the autostart feature is expected to be set while running in a Python environment (not from the packaged .exe), so `sys.executable` works correctly. Document this limitation for the future.

**If PyInstaller build fails due to missing imports:**

Run the built .exe from a terminal (temporarily remove `--noconsole`) to see the `ModuleNotFoundError`. Add the missing module to `hiddenimports` in the .spec file. Common candidates for PyQt6 apps: `PyQt6.sip`, `PyQt6.QtPrintSupport`.

**If Windows Defender flags the built .exe:**

Build PyInstaller's bootloader from source (documented in PyInstaller docs). This replaces the shared bootloader binary that antivirus databases recognize. For a personal tool never distributed publicly, this step is optional — just add an exclusion in Windows Defender.

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| PyInstaller 6.19.0 | Python 3.8–3.14 | Current as of Feb 14 2026; confirmed on PyPI |
| PyInstaller 6.19.0 | PyQt6 6.10.2 | PyQt6 hook in pyinstaller-hooks-contrib covers Qt6; no version conflict |
| PyInstaller 6.19.0 | pywin32 311 | pywin32 runtime hook in pyinstaller-hooks-contrib; known PATH interaction with Qt SSL fixed in 6.x |
| winreg (stdlib) | Python 3.x, Windows only | No version to pin; always available on Windows Python |
| PyInstaller 6.x | winrt-* 3.2.1 | No hook exists in pyinstaller-hooks-contrib; moot for control panel (does not import winrt) |

---

## Sources

- [PyPI — PyInstaller](https://pypi.org/project/pyinstaller/) — version 6.19.0, release date Feb 14 2026 confirmed — HIGH confidence
- [PyInstaller docs 6.19.0 — Common Issues and Pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) — noconsole stdout/stderr None, multiprocessing freeze_support requirements — HIGH confidence
- [Qt for Python — Deployment with PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html) — official Qt endorsement of PyInstaller for PyQt6/PySide6 packaging — HIGH confidence
- [PyInstaller changelog 6.19.0](https://pyinstaller.org/en/stable/CHANGES.html) — pywin32 PATH interaction with Qt SSL DLL fix confirmed in 6.x — HIGH confidence
- [Python docs — winreg](https://docs.python.org/3/library/winreg.html) — stdlib module, Windows-only, HKCU/HKLM access — HIGH confidence
- [PyInstaller GitHub issue #8857](https://github.com/pyinstaller/pyinstaller/issues/8857) — Qt OpenSSL DLL conflict with pywin32 runtime hook details — MEDIUM confidence
- [PyInstaller Wiki — Recipe Multiprocessing](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing) — freeze_support requirement details — HIGH confidence
- [pyinstaller-hooks-contrib GitHub](https://github.com/pyinstaller/pyinstaller-hooks-contrib) — confirmed community hooks repository; no winrt hook found — MEDIUM confidence (browse-based verification)
- WebSearch — PyOxidizer last release Dec 2022 confirmed via GitHub — HIGH confidence
- WebSearch — cx_Freeze 8.6.0 released Feb 2026 (actively maintained alternative) — MEDIUM confidence
- WebSearch — Nuitka antivirus false positive improvement vs PyInstaller comparison — MEDIUM confidence (community articles, not official benchmarks)
- WebSearch — HKCU Run key vs Task Scheduler tradeoffs, Windows Settings Startup app visibility — MEDIUM confidence (multiple consistent community sources)

---

*Stack research for: MonitorControl v1.1 — Windows autostart and standalone .exe packaging additions*
*Researched: 2026-03-27*
