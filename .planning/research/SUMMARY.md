# Project Research Summary

**Project:** MonitorControl v1.1 — Windows autostart and standalone .exe packaging
**Domain:** Python/PyQt6 desktop widget bar — Windows, single-user persistent utility
**Researched:** 2026-03-27
**Confidence:** HIGH

---

## Executive Summary

MonitorControl v1.1 adds two "finished software" features to an already-working v1.0 application: host autostart at Windows login (no terminal window), and the control panel packaged as a standalone `.exe` requiring no Python installation. The existing validated stack (PyQt6 6.10.2, Pillow, pywin32 311, winrt-* 3.2.1, multiprocessing.Queue, config.json hot-reload) is unchanged. The two new additions are PyInstaller 6.19.0 for packaging and a Windows autostart mechanism. Research is high confidence on both: PyInstaller has official Qt endorsement and an active hook ecosystem; the Windows autostart mechanisms are well-documented Win32/registry patterns.

The recommended approach is to build in strict dependency order. Path resolution must be fixed first — both `host/main.py` and `control_panel/__main__.py` currently use bare `"config.json"` strings that resolve against the process working directory, which is wrong when launched from any non-project-root context. Only after that fix is validated in source mode should packaging begin. Packaging the control panel is the primary v1.1 deliverable; packaging the host is optional but required for clean no-Python distribution. For autostart, use the `HKCU` registry Run key via stdlib `winreg` (see conflict resolution below).

The principal risk category is PyInstaller packaging of complex dependencies: pywin32 and winrt-* both need explicit bundling because PyInstaller's static analysis cannot trace their DLL and namespace-package loading. Expect 2-3 iteration cycles when building the host `.exe` for the first time. The control panel `.exe` is simpler (PyQt6 + stdlib only, no winrt) and should build cleanly on the first attempt with a minimal spec file. A second category of risk is the `console=False` flag silently breaking `print()`-based diagnostics in the host; mitigate with a stdout null-guard and file-based logging before packaging.

---

## Key Findings

### Recommended Stack

The new stack additions for v1.1 are minimal. PyInstaller 6.19.0 (released Feb 14 2026, actively maintained) is the only new runtime build-tool dependency; it is not shipped with users. It has official Qt for Python endorsement and the `pyinstaller-hooks-contrib` package bundled with it provides PyQt6 and pywin32 hooks automatically. No C toolchain is required. The stdlib `winreg` module handles the autostart registry interaction with no new dependencies.

**Core technologies (new for v1.1):**
- **PyInstaller 6.19.0**: Package control panel (and optionally host) as standalone Windows `.exe` — only tool with official PyQt6 hook support, active maintenance, and no C toolchain requirement.
- **winreg (stdlib)**: Read/write HKCU Run key for autostart toggle — zero new dependencies, purpose-built for registry access, correct tool for per-user user-session apps.
- **`--onedir` build mode**: Produces an exe + DLL folder; faster startup than `--onefile`, no antivirus temp-extraction trigger, multiprocessing-compatible.

**Critical version note:** PyInstaller >= 6.5.0 required to avoid a known pywin32/Qt OpenSSL DLL PATH conflict; 6.19.0 satisfies this.

### Expected Features

**Must have (table stakes for v1.1):**
- Autostart toggle in the control panel Startup group — reads live HKCU registry state on every panel open; writes/deletes registry key immediately on toggle change; no "Save" button needed.
- No terminal window at login — `pythonw.exe` reference in Run key (or packaged `.exe` with `--noconsole`).
- Control panel packaged as `MonitorControl.exe` via PyInstaller `--onedir --noconsole`.
- `config.json` path resolved from `sys.executable` directory in all build contexts, not `cwd`.
- Reproducible `.spec` file committed to repo.
- `freeze_support()` called first in `if __name__ == "__main__":` block in host before any other multiprocessing call.

**Should have (polish, v1.1 if time allows):**
- Status label below the toggle: "MonitorControl will start automatically at next login."
- `.ico` icon for `MonitorControl.exe` — distinguishes it from generic Python apps in Explorer and Task Manager.
- Autostart points directly to the `.exe` once both executables are packaged (decouples from Python install location).

**Defer to v2+:**
- Installer (NSIS, Inno Setup) — only needed if distributing to non-developers needing Start Menu entries or file associations.
- Auto-update mechanism — significant engineering; defer until stable release cadence exists.
- Package host as a separate `.exe` — adds `freeze_support` + multiprocessing + winrt complexity; control panel packaging first establishes the pattern.

### Architecture Approach

v1.1 adds three new components and modifies two existing files. A new `shared/paths.py` module provides a `get_config_path()` helper that anchors config resolution to `sys.executable`'s directory when frozen or to the project root when running from source; this must be adopted by both `host/main.py` and `control_panel/__main__.py` before any packaging work begins. A new autostart module provides `enable_autostart()`, `disable_autostart()`, and `is_autostart_enabled()` functions called from the control panel's new Startup tab. A new `build/` directory holds `.spec` files for reproducible builds. `config.json` must never be bundled inside the `.exe`; it is user-mutable and lives beside the executables in the distribution directory as the sole IPC channel between host and control panel.

**Major components:**
1. `shared/paths.py` (new) — `get_config_path()` exe-relative path resolver; used by host and control panel.
2. `host/autostart.py` (new) — autostart enable/disable/query via `winreg`; consumed by control panel Startup tab.
3. `control_panel/main_window.py` (modified) — new Startup tab with autostart toggle; reads live state on open.
4. `build/control_panel.spec` (new) — PyInstaller spec for `MonitorControl.exe`; `hiddenimports=['winreg']`, `pathex=['.']`.
5. `build/host.spec` (new, optional) — PyInstaller spec for `host.exe`; requires `collect_submodules("winrt")`, `collect_dynamic_libs("win32")`.

### Critical Pitfalls

1. **`multiprocessing.freeze_support()` missing or called after `set_start_method()`** — In a frozen `.exe`, absence of `freeze_support()` causes an exponential spawn bomb: the exe re-invokes itself infinitely, exhausting handles within seconds. Must be the very first call inside `if __name__ == "__main__":`, before `set_start_method("spawn")`. Add and validate before building any host `.exe`.

2. **`config.json` relative path resolves to wrong directory from autostart** — Both entry points currently use bare `"config.json"`, which resolves from `os.getcwd()`. Under the registry Run key or Task Scheduler, cwd is typically `C:\Windows\System32` or the user home. Fix with `_exe_dir()` pattern using `sys.executable` when `sys.frozen` is set. This fix is required before packaging; validate by launching from a non-project-root directory.

3. **`console=False` makes `sys.stdout` and `sys.stderr` None — any `print()` call crashes the frozen app** — The host uses `print()` extensively. With `--noconsole`, `sys.stdout` is `None` and `print()` raises `AttributeError` immediately on startup. Add a null-guard for stdout/stderr and add file-based logging before switching to `console=False` in the spec.

4. **winrt-* namespace packages not auto-detected by PyInstaller** — The six `winrt-*` packages use Python namespace package mechanics and deferred imports. PyInstaller's static analysis misses them entirely. No community hooks exist for winrt-* 3.2.1. Explicitly add `collect_submodules("winrt")` and `collect_dynamic_libs("winrt")` to the host spec. Expect 2-3 build-test-fix iterations.

5. **pywin32 DLLs not found in frozen build** — pywin32 loads `pywintypes311.dll` via a custom post-install PATH registration that the frozen app lacks. The `pyinstaller-hooks-contrib` pywin32 hook handles most of this automatically in PyInstaller 6.x, but verify it collects `pywintypes311.dll`; add `collect_dynamic_libs("win32")` explicitly if `win32api` import fails in the built `.exe`.

6. **Task Scheduler "Run whether user is logged on or not" makes GUI invisible** — This mode runs in Session 0, a non-interactive session where no window is visible. Always configure "Run only when user is logged on" for GUI tasks. Validate by logging out and back in, not by running the task manually from the Task Scheduler UI. (Relevant only if Task Scheduler is chosen over the Run key; see conflict resolution.)

---

## CONFLICT RESOLUTION: Autostart Mechanism

**Research conflict:** STACK.md and FEATURES.md recommend the `HKCU` registry Run key via stdlib `winreg`. ARCHITECTURE.md and PITFALLS.md recommend Windows Task Scheduler via `schtasks.exe` subprocess calls.

**Resolution: Use the HKCU registry Run key (`winreg`).**

**Rationale:**

The Task Scheduler arguments rest on two claims: (a) working directory control, and (b) future elevation support. Both are moot given the `_exe_dir()` path fix that v1.1 requires regardless of autostart mechanism:

- **Working directory control:** The `_exe_dir()` pattern (`os.path.dirname(sys.executable)` when frozen) correctly resolves `config.json` regardless of how the process is launched — from the Run key, Task Scheduler, or a double-click. The "no Start In field on Run key" limitation is fully mitigated by the mandatory path fix. This was the strongest argument for Task Scheduler; it disappears once the code fix is in place.

- **Elevation (future):** `ClipCursor()` works at normal user privilege and has done so throughout v1.0. No feature in the roadmap requires elevation. Deferring to Task Scheduler on the grounds of a hypothetical future elevation need adds complexity now for no present benefit.

**The HKCU Run key wins on every practical dimension:**

| Criterion | HKCU Run key | Task Scheduler |
|-----------|-------------|----------------|
| Implementation | ~15 lines, stdlib `winreg` | ~3 `schtasks` subprocess calls + exit-code parsing |
| User visibility | Windows Settings > Apps > Startup shows entry | Task Scheduler UI only; not in Settings |
| No-console suppression | Point to `pythonw.exe`; or packaged `.exe` handles it | Correct with right flags; wrong flags cause invisible window (BLOCKER) |
| Dependencies | None (stdlib) | External subprocess call to `schtasks.exe` |
| Risk of invisible-window bug | None | HIGH — wrong logon mode silently produces an invisible window (Pitfall 13, BLOCKER severity) |

The Task Scheduler "invisible window" pitfall (Pitfall 13, BLOCKER severity) does not exist in the Run key path. For a personal tool in a controlled environment, the Run key is the safer and simpler implementation choice.

**Final implementation pattern:**

```
HKCU\Software\Microsoft\Windows\CurrentVersion\Run
"MonitorControl" = "\"C:\path\to\pythonw.exe\" \"E:\path\to\host\main.py\""
```

Once the host is also packaged as a `.exe`, update the registry value to point directly to `host.exe`. The `autostart.py` module interface should accept an arbitrary exe path from Phase 2 onward to support this transition.

---

## Implications for Roadmap

Based on combined research, the dependency chain is strict: path resolution must be correct before packaging; packaging must be validated before the autostart toggle can write the final exe-pointing registry value. The suggested phase structure for v1.1 follows this dependency order.

### Phase 1: Path Resolution and Freeze Safety

**Rationale:** Both packaging and autostart fail if config.json is not found. This is the single highest-leverage fix: one helper function unblocks everything downstream. The `freeze_support()` ordering fix is similarly load-bearing — without it, the first host `.exe` test will produce a spawn bomb with no useful error message.
**Delivers:** `shared/paths.py` with `get_config_path()`; updated `host/main.py` and `control_panel/__main__.py` to use it; `multiprocessing.freeze_support()` moved to first position in `if __name__ == "__main__":`; `sys.stdout`/`sys.stderr` null-guard added to host entry point.
**Addresses:** config.json path fix (table stakes); freeze_support ordering; stdout null-guard prerequisite for `console=False`.
**Avoids:** Pitfalls 8 (freeze_support spawn bomb), 9 (config path resolves to System32), 10 (stdout crash in noconsole build).
**Research flag:** Standard patterns — no additional research needed. Well-documented stdlib and PyInstaller documented patterns.

### Phase 2: Autostart Toggle (HKCU Registry Run Key)

**Rationale:** Implements the autostart feature using the resolved mechanism (HKCU Run key via `winreg`). Can be built and tested in source mode before packaging. The toggle reads live state from the registry on panel open and writes/deletes immediately on change — no config.json involvement, no Save button.
**Delivers:** `host/autostart.py` with `enable_autostart(exe_path)`, `disable_autostart()`, `is_autostart_enabled()`; new Startup tab in control panel with checkbox and error feedback via `QMessageBox.warning` on registry write failure; autostart entry points to `pythonw.exe + host/main.py` in Phase 2 (updated to `host.exe` in Phase 4).
**Addresses:** Autostart toggle (table stakes); toggle reads live registry state (differentiator); graceful toggle failure feedback.
**Avoids:** Storing autostart state in config.json (anti-pattern); HKLM Run key (elevation not needed); Task Scheduler invisible-window BLOCKER.
**Research flag:** Standard pattern — `winreg` is fully documented stdlib. No research needed.

### Phase 3: Control Panel Packaging

**Rationale:** The control panel is PyQt6 + stdlib only (no winrt, no pywin32 in its own code — `winreg` is stdlib). This is the simpler of the two packaging targets and is the primary v1.1 deliverable. Phase 1's path fix must be in place first.
**Delivers:** `build/control_panel.spec` with `hiddenimports=['winreg']`, `pathex=['.']`, `console=False`; `MonitorControlPanel/MonitorControl.exe` distributable folder; validated by launching from Desktop confirming config.json loads and autostart toggle works correctly.
**Addresses:** Standalone `.exe` (table stakes); reproducible `.spec` file (differentiator); icon (P2 polish).
**Avoids:** `--onefile` (AV trigger, multiprocessing complications); bundling config.json in the exe.
**Research flag:** Well-documented PyInstaller + PyQt6 patterns. Skip research-phase; iterate on hidden imports if needed at build time.

### Phase 4: Host Packaging (Optional but Recommended)

**Rationale:** Required for true no-Python distribution. Significantly more complex than control panel due to winrt namespace packages and pywin32 DLL loading. Once host is packaged, the autostart Run key value is updated to point to `host.exe` directly, decoupling the user from any Python installation.
**Delivers:** `build/host.spec` with `collect_submodules("winrt")`, `collect_dynamic_libs("win32")`, freeze_support verified; `host/host.exe` distributable; updated `autostart.py` `enable_autostart()` call site pointing to `host.exe`.
**Addresses:** "Autostart points to .exe, not pythonw.exe" (differentiator); full no-Python distribution.
**Avoids:** Pitfalls 11 (pywin32 DLLs not found), 12 (winrt hidden imports), 16 (DLL search path in child processes).
**Research flag:** Needs iteration — winrt hidden imports have no community hooks; expect 2-3 build cycles. Consider moving winrt imports to module level in `notification/widget.py` as the first mitigation attempt before adding custom collection to the spec.

### Phase Ordering Rationale

- Path resolution (Phase 1) is a hard prerequisite for both packaging phases and the autostart launch path. It must be validated in source mode before any exe build.
- Autostart (Phase 2) can be built and validated in source mode independently of packaging, allowing the feature to ship before investing in PyInstaller iteration cycles.
- Control panel packaging (Phase 3) comes before host packaging (Phase 4) because it is simpler and proves the PyInstaller pipeline before adding winrt/pywin32 complexity.
- The autostart Run key value transitions from `pythonw.exe host\main.py` (Phase 2) to `host.exe` (Phase 4) — a deliberate two-step that allows the autostart feature to ship before host packaging is complete.

### Research Flags

**Phases needing deeper iteration during execution:**
- **Phase 4 (host packaging):** winrt-* hidden imports are the highest-risk unknown. No community hooks exist for winrt-* 3.2.1. The `collect_submodules("winrt")` approach is the correct starting point but needs live iteration against the installed package structure. Budget for 2-3 build-test-fix cycles. First alternative: move winrt imports to module level in `notification/widget.py` to make them visible to static analysis.
- **Phase 4 (host packaging):** Multiprocessing worker subprocess DLL path inheritance (Pitfall 16) may require `SetDllDirectoryW(None)` reset in each widget subprocess entry point. Needs empirical validation in the built `.exe`.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** `sys.frozen` / `sys.executable` path resolution is canonical PyInstaller documented pattern.
- **Phase 2:** `winreg` HKCU Run key is fully documented stdlib with no known edge cases for per-user GUI apps.
- **Phase 3:** PyQt6 + stdlib. `pyinstaller-hooks-contrib` handles PyQt6 automatically; `winreg` needs only `hiddenimports=['winreg']`.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack (PyInstaller, winreg) | HIGH | Official PyInstaller docs; stdlib module; Qt for Python official deployment guide; verified version compatibility |
| Features (autostart UX, packaging deliverables) | HIGH | Verified against mainstream Windows app patterns (Discord, Slack, 1Password); official Windows autostart docs |
| Architecture (component boundaries, path resolution) | HIGH | PyInstaller runtime-information docs; multiprocessing recipe; all cross-verified across multiple sources |
| Pitfalls (packaging, freeze_support, winrt) | HIGH for freeze_support / config path / console=False; MEDIUM for winrt hidden imports and pywin32 DLL inheritance in subprocesses | winrt-* 3.2.1 PyInstaller bundling has no published hook; behavior inferred from namespace package mechanics |

**Overall confidence: HIGH**

The well-documented areas (PyInstaller + PyQt6, multiprocessing freeze_support, registry Run key) are HIGH confidence from official sources. The only MEDIUM-confidence area — winrt hidden imports and child process DLL paths — is scoped to Phase 4 (host packaging), which is optional for the v1.1 milestone. The control panel packaging (Phase 3) and autostart (Phase 2) paths are HIGH confidence.

### Gaps to Address

- **winrt-* PyInstaller collection**: No community hooks exist for winrt-* 3.2.1. The `collect_submodules("winrt")` + `collect_dynamic_libs("winrt")` approach is the correct starting point but needs live iteration against the installed package. An alternative — moving winrt imports to module level in `notification/widget.py` — should be tried first as it eliminates the need for custom collection entirely and makes the imports visible to PyInstaller's static analysis.

- **DLL search path inheritance in widget subprocesses**: Pitfall 16 describes a scenario where PyInstaller's `SetDllDirectoryW` in the parent's bootloader interferes with DLL loading in spawned child processes. Mitigation (`SetDllDirectoryW(None)` reset) is documented but needs empirical validation in the built `.exe` since the interaction depends on the specific DLL load order of Pillow and winrt in each subprocess.

- **Autostart path transition (pythonw.exe to host.exe)**: If Phase 4 is deferred, the autostart entry will continue to reference `pythonw.exe`. Design `autostart.py` from Phase 2 to accept an arbitrary exe path so Phase 4 can update the registered path without changing the module interface.

---

## Sources

### Primary (HIGH confidence)
- [PyInstaller 6.19.0 — Run-time Information](https://pyinstaller.org/en/stable/runtime-information.html) — `sys.frozen`, `sys._MEIPASS`, `sys.executable` in frozen context
- [PyInstaller 6.19.0 — Common Issues and Pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html) — `console=False` stdout/stderr, `--onefile` + multiprocessing, freeze_support ordering
- [PyInstaller Wiki — Recipe: Multiprocessing](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing) — freeze_support placement, spawn mode in frozen exe
- [Qt for Python — Deployment with PyInstaller](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html) — official Qt endorsement, hook coverage
- [Python docs — winreg](https://docs.python.org/3/library/winreg.html) — HKCU/HKLM access, KEY_SET_VALUE, SetValueEx, DeleteValue
- [PyPI — PyInstaller](https://pypi.org/project/pyinstaller/) — version 6.19.0, release date Feb 14 2026
- [Microsoft Learn — schtasks create](https://learn.microsoft.com/en-us/windows-server/administration/windows-commands/schtasks-create) — Task Scheduler CLI reference
- [Microsoft Learn — Run and RunOnce Registry Keys](https://learn.microsoft.com/en-us/windows/win32/setupapi/run-and-runonce-registry-keys) — HKCU Run key semantics and behavior

### Secondary (MEDIUM confidence)
- [PyInstaller GitHub issue #8857](https://github.com/pyinstaller/pyinstaller/issues/8857) — Qt OpenSSL DLL conflict with pywin32 runtime hook (fixed in 6.x)
- [pyinstaller-hooks-contrib GitHub](https://github.com/pyinstaller/pyinstaller-hooks-contrib) — confirmed no winrt hook exists for winrt-* 3.2.1
- [Python GUIs — Packaging PyQt6 for Windows with PyInstaller](https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/) — packaging tutorial with hidden import guidance
- [Windows Automatic Startup Locations — gHacks](https://www.ghacks.net/2016/06/04/windows-automatic-startup-locations/) — Run key vs Task Scheduler behavioral comparison
- cx_Freeze 8.6.0 (Feb 2026), Nuitka — evaluated and rejected; PyInstaller selected as standard for PyQt6 apps

### Tertiary (LOW confidence)
- Nuitka vs PyInstaller AV false positive comparison — community articles, not official benchmarks; specific false-positive rates not independently verified

---
*Research completed: 2026-03-27*
*Ready for roadmap: yes*
