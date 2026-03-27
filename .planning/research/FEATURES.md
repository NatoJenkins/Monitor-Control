# Feature Research

**Domain:** Desktop widget bar / persistent utility display framework (Windows, Python/PyQt6)
**Researched:** 2026-03-27 (v1.1 addendum — autostart and .exe packaging)
**Confidence:** HIGH for autostart mechanics and PyInstaller flags (verified against official docs and community sources); MEDIUM for PyInstaller/multiprocessing interaction (known issue class, needs integration testing); HIGH for UX expectations (common desktop app patterns)

---

## v1.1 Scope Context

v1.0 ships the core host app, control panel, Pomodoro, Calendar, and Notification widgets. v1.1 adds two "finished software" features:

1. **Host autostart** — host launches automatically at Windows login, configurable from the control panel, no terminal visible
2. **Control panel .exe** — `control_panel` packaged as `MonitorControl.exe` requiring no Python environment

These are the two features between "developer tool" and "finished software." Both are table stakes for any persistent utility app.

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features a persistent Windows utility app must have. Missing these = product feels like a prototype.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Autostart toggle in settings | Every persistent utility (Discord, Slack, Spotify, 1Password, YASB) puts "Launch at startup" in settings. Absence means users must manually start the app on every login or maintain their own Task Scheduler entry. | LOW | `winreg` write to `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`. No elevation needed. The existing control panel already has a tab-based settings UI to host this. |
| No terminal window on autostart | Users who see a cmd.exe window flash or stay open on login immediately assume something is broken or that they installed "developer software." Every mainstream Windows utility suppresses the console. | LOW | Python: use `pythonw.exe` instead of `python.exe`, or package as `.exe` with `--noconsole`. For the packaged .exe this is handled by PyInstaller `--windowed`. For unpackaged script-based autostart, the registry value must point to `pythonw.exe`. |
| Standalone .exe for control panel | Users who share this app or want to run it on a machine without Python installed expect a double-clickable file. No `pip install`, no virtualenv, no PATH setup. | MEDIUM | PyInstaller is the standard tool. Produces either a single `.exe` (--onefile) or a folder with an `.exe` entry point (--onedir). |
| Toggle reflects actual system state on open | When users open settings, the "Start at login" checkbox/toggle must read the real current state, not a cached value. If the user manually deleted the registry key, the toggle should show "off." | LOW | On control panel startup, read `HKCU\...\Run` for the app's key name and set the toggle accordingly. Do not rely solely on a config.json flag. |
| Autostart survives app updates | If a new version is placed at a different path, or the .exe is renamed, the old autostart entry breaks silently. The app should update its own registry entry when the path changes. | LOW | Write the registry entry at the path of the currently-running executable (`sys.executable` or `os.abspath(sys.argv[0])`). Re-register on every enable or whenever the path has changed. |
| Graceful toggle failure feedback | If the registry write fails (unlikely for HKCU, but possible on managed systems), users need a clear error, not silent failure where the toggle appears enabled but autostart never runs. | LOW | Wrap `winreg` calls in try/except. Show `QMessageBox.warning` on failure. Reset the toggle to its previous state. |

---

### Differentiators (Competitive Advantage)

Features beyond the bare minimum for autostart + packaging, aligned with the "finished software" goal.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Toggle reads live registry state | Most apps store autostart state in their own config and may desync from Windows. Reading the actual registry on each panel open means the UI is always correct even if the user changed state via Task Manager or registry editor. | LOW | Use `winreg.QueryValueEx` at control panel startup. Fall back to "disabled" if the key is missing. |
| .exe correctly handles config.json path | A packaged .exe must locate `config.json` relative to its own location, not `cwd`. Apps that hardcode relative paths silently fail when launched from autostart (working directory is system root or user home, not the app directory). | MEDIUM | In the frozen .exe, use `sys.executable`'s directory as the config root. `os.path.dirname(os.path.abspath(sys.executable))` is the reliable approach for both frozen and unfrozen execution. |
| Autostart points to the .exe, not pythonw.exe | Once a distributable .exe exists, the autostart entry should point to it directly. This decouples the user from requiring Python to be installed and avoids the `pythonw.exe` path variation across Python versions and install locations. | LOW | Only applicable if packaging is done. The registry value becomes `C:\path\to\MonitorControl.exe`. |
| Build reproducibility via .spec file | A committed `.spec` file means the build is reproducible from any machine with PyInstaller installed, without memorizing command-line flags. Professional open-source Python apps (e.g., Calibre, Mu Editor) all ship with spec files. | LOW | Generate once with `pyinstaller --name MonitorControl ...`, then commit `MonitorControl.spec`. Subsequent builds use `pyinstaller MonitorControl.spec`. |

---

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| HKLM (system-wide) autostart | Seems "more robust" — starts for all users. | Requires UAC elevation on write. Most utility apps have no reason to start for all users. Causes confusion when one user disables and another is surprised it still starts. | Use HKCU. No elevation needed. Correct scope for a per-user utility. |
| Task Scheduler instead of registry for autostart | Task Scheduler allows delay, priority, conditions. | Significantly more complex API (`schtasks.exe` or XML-based COM interface). No UI benefit to the user. For a GUI utility with no elevated-privilege needs, HKCU Run is the standard and sufficient. | HKCU Run key. Simple, user-visible in Task Manager Startup tab, deletable by the user if desired. |
| --onefile PyInstaller for the packaged .exe | Single `.exe` is simpler to share. | Slow first-launch: --onefile extracts its bundle to a temp directory on every run before executing. **Critical conflict with this project:** MonitorControl uses `multiprocessing` with the `spawn` start method (Windows default). `--onefile` + `multiprocessing` on Windows has documented issues with subprocess re-launches (each spawned subprocess re-extracts the bundle, or fails). --onedir avoids this entirely. | Use `--onedir`. Produces a folder; the entry-point `.exe` is still a double-click. Users interact only with the `.exe`. If a single-file distribution is required, wrap in an installer (NSIS, Inno Setup) that installs the onedir bundle. |
| Packaging the host and control panel as one .exe | Fewer files to distribute. | The host (`host/main.py`) uses `multiprocessing.Process` to spawn widget subprocesses. In a frozen .exe, every spawned subprocess re-enters the frozen executable's `__main__`, requiring `multiprocessing.freeze_support()` and careful entry point separation. Combining host + control panel into one .exe adds complexity with no user benefit — the two processes have different roles and lifecycles. | Package the control panel as `MonitorControl.exe`. The host runs as a Python script (or separate exe) pointed to by the autostart registry key. v1.1 scope is control panel packaging only. |
| Auto-update mechanism | Users want the latest version automatically. | Out-of-scope complexity: code signing, update server, rollback, delta updates, UAC for HKLM installs. Every serious update system (Squirrel, WinSparkle, MSIX) is a significant engineering investment. | Provide a GitHub Releases page. Users download and replace the folder manually. Note the new path in your release notes so they can re-run the autostart enable toggle. |
| Embedding config.json inside the .exe | Simplifies distribution — truly single-file. | config.json is mutable user data. Embedding it means user settings would be wiped on every app update (the .exe is replaced, the embedded config is replaced). | config.json lives alongside the .exe (or in a well-known user data directory like `%APPDATA%\MonitorControl`). On first run, create a default if absent. |
| Installer (NSIS, Inno Setup, WiX) for v1.1 | "Real" software has an installer. | Installer toolchain adds a build step, requires learning a DSL (NSIS/Inno Setup script), and produces a UAC-elevating setup.exe that antivirus tools sometimes flag. For a personal utility, a portable folder + README is faster to ship and easier to update. | Deliver as a portable onedir folder. Autostart toggle handles the startup registration from inside the app. No installer needed until there is demand for HKLM installation or file associations. |

---

## Feature Dependencies

```
[Autostart toggle in control panel]
    └──requires──> [winreg write to HKCU Run]
    └──requires──> [Absolute path to host executable]
    └──requires──> [Toggle reads live registry state on panel open]
    └──enhanced by──> [.exe packaging] (autostart can point to .exe instead of pythonw.exe)

[.exe packaging (PyInstaller --onedir --noconsole)]
    └──requires──> [multiprocessing.freeze_support() in host entry point]
    └──requires──> [config.json path resolved relative to sys.executable, not cwd]
    └──requires──> [.spec file for reproducible builds]
    └──requires──> [Hidden imports declared for winrt and pywin32]
    └──conflicts with──> [--onefile mode] (multiprocessing spawn issues on Windows)

[No terminal window on autostart]
    └──requires──> [--noconsole / --windowed flag in PyInstaller build]
    └──OR requires──> [pythonw.exe as interpreter in HKCU Run value (non-packaged path)]

[config.json path resolution in frozen .exe]
    └──required by──> [.exe packaging usable from any working directory]
    └──required by──> [Autostart (working dir at login is not app dir)]
```

### Dependency Notes

- **Autostart path and .exe packaging are sequenced:** The autostart feature can be built independently of packaging (pointing to `pythonw.exe`), but the final autostart registry value should be updated once packaging is done to point to the `.exe`. Build packaging first in v1.1 so the autostart toggle can write the correct final value.
- **freeze_support() is non-negotiable:** The host uses `multiprocessing` with spawn. Without `multiprocessing.freeze_support()` at the very top of the frozen entry point, spawning widget subprocesses from a frozen `.exe` causes an infinite spawn loop (each child re-enters `__main__` and tries to spawn again). This must be in place before the host's `.exe` is ever tested.
- **config.json path resolution must be fixed before packaging:** The current `control_panel/__main__.py` hardcodes `config_path="config.json"` (relative). This resolves correctly when run from the project root but silently fails when the `.exe` is launched from autostart or any other working directory. The fix must happen at the code level before packaging.
- **winrt hidden imports:** The six `winrt-*` packages (winrt-runtime, winrt-Windows.UI.Notifications, etc.) use dynamic import patterns that PyInstaller cannot auto-detect. Each must be declared as a hidden import in the `.spec` file. Expect to iterate: run the built `.exe`, check for `ModuleNotFoundError`, add the missing module to `hiddenimports`, rebuild.
- **pywin32 is handled automatically:** Recent PyInstaller versions (5.x+) include hooks for pywin32 that handle DLL path bootstrapping. No manual hidden imports needed for pywin32 311.

---

## MVP Definition

### Launch With (v1.1)

Minimum for this milestone to feel like "finished software."

- [ ] Autostart toggle in control panel "Startup" group (checkbox or toggle button) — reads live HKCU registry state on open
- [ ] Enable writes `HKCU\Software\Microsoft\Windows\CurrentVersion\Run\MonitorControl` pointing to absolute host path; disable deletes the key
- [ ] No terminal visible when host launches from autostart (pythonw.exe reference or packaged .exe)
- [ ] Control panel packaged as `MonitorControl.exe` via PyInstaller `--onedir --noconsole`
- [ ] config.json path resolved from `sys.executable` directory in frozen build, not `cwd`
- [ ] Reproducible `.spec` file committed to repo

### Add After Validation (v1.1 polish)

- [ ] Status label below the toggle: "MonitorControl will start automatically at next login" / "MonitorControl will not start automatically" — eliminates ambiguity about when the setting takes effect
- [ ] Icon for `MonitorControl.exe` (`.ico` file via `--icon` flag) — distinguishes it from generic Python apps in Explorer and Task Manager

### Future Consideration (v2+)

- [ ] Installer (Inno Setup or NSIS) — only needed if distributing to non-developer users who need Start Menu entries, file associations, or uninstaller support
- [ ] Auto-update — only after establishing a stable release cadence and user base
- [ ] Package host as a separate .exe — adds freeze_support complexity to the multiprocess widget spawn path; defer until control panel packaging is proven

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Autostart toggle (HKCU Run) | HIGH | LOW | P1 |
| No terminal on autostart | HIGH | LOW | P1 |
| Toggle reads live registry state | HIGH | LOW | P1 |
| config.json path fix for frozen exe | HIGH | LOW | P1 |
| Control panel .exe (--onedir --noconsole) | HIGH | MEDIUM | P1 |
| Reproducible .spec file | MEDIUM | LOW | P1 |
| winrt hidden imports in .spec | HIGH | MEDIUM | P1 (blocks packaging) |
| Status label below toggle | MEDIUM | LOW | P2 |
| .exe icon (.ico) | LOW | LOW | P2 |
| Host packaged as .exe | LOW | HIGH | P3 |
| Installer | LOW | HIGH | P3 |

**Priority key:**
- P1: Required for v1.1 milestone completion
- P2: Polish — add if time allows, does not block milestone
- P3: Future milestone or backlog

---

## Autostart UX Patterns (What Users Expect)

Based on patterns from Discord, Slack, 1Password, Spotify, and Windows-native utilities:

### Toggle Location
- A "Startup" section within an existing "General" or dedicated settings tab, not a top-level menu item.
- Label: "Start MonitorControl automatically at login" or "Launch at startup". Avoid technical language ("Write to registry," "HKCU Run key").
- Control: A `QCheckBox` is the most common and recognizable control for a binary persistent setting on Windows. A toggle switch (QToolButton styled as toggle) is acceptable if the control panel adopts a modern look. Avoid radio buttons for a single binary setting.

### Toggle Behavior
- **On enable:** Write registry key immediately (not on "Save" button click). The setting should take effect without requiring a separate save action. Confirmation is the toggle moving to "checked" state.
- **On disable:** Delete registry key immediately. Same rationale — the user acted, the system should respond.
- **On panel open:** Query registry, set toggle state to match. Never trust a stale in-memory value.
- **On failure:** Show an inline error label or `QMessageBox.warning` with the OS error. Reset the toggle to its previous state. Never leave the toggle in a state that does not reflect reality.

### "When does this take effect?" Expectation
- Users know autostart means "next time I log in." No confirmation dialog needed.
- An optional static label ("Changes take effect at next login") is acceptable but not required — the label "at login" in the toggle text itself conveys this.

### What "Finished Software" Looks Like
- Task Manager's Startup tab shows "MonitorControl" (not "python" or "pythonw") with a reasonable startup impact rating.
- The entry's command path is an `.exe`, not a Python script.
- The entry is removable by the user from Task Manager without breaking anything (the control panel will show "disabled" on next open).
- No console window appears at any point during autostart.

---

## PyInstaller Packaging Specifics (Control Panel)

### Recommended Build Command (first run to generate .spec)

```
pyinstaller --name MonitorControl --onedir --noconsole --icon assets/icon.ico control_panel/__main__.py
```

If no icon exists yet, omit `--icon`. After first run, commit `MonitorControl.spec` and use:

```
pyinstaller MonitorControl.spec
```

### Known Requirements for This Project's Dependencies

| Dependency | PyInstaller Handling | Action Required |
|------------|---------------------|-----------------|
| PyQt6 6.10.2 | Auto-detected via hooks in PyInstaller 5.x+ | None |
| pywin32 311 | Auto-handled; pyinstaller includes pywin32 bootstrap hooks | None |
| winrt-runtime 3.2.1 | Dynamic imports not auto-detected | Add each winrt module to `hiddenimports` in .spec |
| winrt-Windows.UI.Notifications | Same | Add to `hiddenimports` |
| winrt-Windows.Foundation | Same | Add to `hiddenimports` |
| winrt-Windows.Foundation.Collections | Same | Add to `hiddenimports` |
| winrt-Windows.ApplicationModel | Same | Add to `hiddenimports` |
| winrt-Windows.UI.Notifications.Management | Same | Add to `hiddenimports` |

Iterative approach: build, run the `.exe`, note any `ModuleNotFoundError`, add to `hiddenimports`, rebuild. Expect 2-3 iterations for the winrt modules.

### --onefile vs --onedir Decision

Use `--onedir` for this project. Rationale:

1. **Multiprocessing compatibility:** The host uses `multiprocessing` with Windows' default `spawn` start method. `--onefile` + `spawn` on Windows has documented issues (child processes re-enter `__main__` and may re-extract the bundle or fail). `--onedir` sidesteps this entirely. The control panel does not spawn subprocesses itself, but the same build should remain safe if the host is ever packaged.
2. **Startup speed:** `--onefile` extracts to a temp directory on every launch. For an app launched at login, unnecessary startup delay is noticeable.
3. **Distribution:** The onedir folder is zip-portable. Users can copy the folder, run `MonitorControl.exe` directly. No installer required.

### config.json Path Resolution (Critical Code Change Required)

The current `control_panel/__main__.py` passes `config_path="config.json"` (relative path). This resolves to `cwd`, which is:
- Correct when run as `python -m control_panel` from the project root
- Wrong when launched from autostart (cwd is typically `C:\Windows\System32` or the user's home directory)
- Wrong when the packaged `.exe` is double-clicked from Explorer from a different directory

The fix must be applied to `control_panel/__main__.py` before packaging:

```python
import os, sys

def _resolve_config_path() -> str:
    # sys.executable is the .exe path when frozen; __file__ otherwise
    base = os.path.dirname(os.path.abspath(
        sys.executable if getattr(sys, "frozen", False) else __file__
    ))
    return os.path.join(base, "config.json")
```

Pass `config_path=_resolve_config_path()` to `ControlPanelWindow`.

---

## Autostart Implementation Pattern (HKCU winreg)

### Registry Key Details

```
Hive:  HKEY_CURRENT_USER
Path:  Software\Microsoft\Windows\CurrentVersion\Run
Name:  MonitorControl
Value: "C:\path\to\host_or_monitor_control.exe"  (REG_SZ)
```

### Read (check current state)

```python
import winreg

def is_autostart_enabled(app_name: str) -> bool:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            winreg.QueryValueEx(key, app_name)
            return True
    except FileNotFoundError:
        return False
    except OSError:
        return False
```

### Write (enable)

```python
def enable_autostart(app_name: str, exe_path: str) -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    with winreg.OpenKey(
        winreg.HKEY_CURRENT_USER, key_path,
        access=winreg.KEY_SET_VALUE
    ) as key:
        winreg.SetValueEx(key, app_name, 0, winreg.REG_SZ, exe_path)
```

### Delete (disable)

```python
def disable_autostart(app_name: str) -> None:
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, key_path,
            access=winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, app_name)
    except FileNotFoundError:
        pass  # Already absent — treat as success
```

### Path to Register

Point to the host executable. For the packaged scenario, this is the `host.exe` (or `MonitorControlHost.exe`). For the non-packaged scenario, this is `pythonw.exe <absolute_path_to_host/main.py>`. For v1.1 where only the control panel is packaged, use `pythonw.exe`:

```
"C:\Users\...\AppData\Local\Programs\Python\Python312\pythonw.exe" "E:\ClaudeCodeProjects\MonitorControl\host\main.py"
```

This must be an absolute path. `pythonw.exe` is used (not `python.exe`) to suppress the console window.

---

## Sources

- [winreg — Python standard library docs](https://docs.python.org/3/library/winreg.html)
- [Packaging PyQt6 applications for Windows, with PyInstaller and InstallForge — pythonguis.com](https://www.pythonguis.com/tutorials/packaging-pyqt6-applications-windows-pyinstaller/)
- [Qt for Python: PyInstaller deployment — doc.qt.io](https://doc.qt.io/qtforpython-6/deployment/deployment-pyinstaller.html)
- [PyInstaller — Using PyInstaller (usage flags)](https://pyinstaller.org/en/stable/usage.html)
- [PyInstaller — Common Issues and Pitfalls](https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html)
- [PyInstaller — Recipe: Multiprocessing (Wiki)](https://github.com/pyinstaller/pyinstaller/wiki/Recipe-Multiprocessing)
- [PyInstaller — Issue #2028: Multiprocessing + --onefile on Windows](https://github.com/pyinstaller/pyinstaller/issues/2028)
- [PyInstaller — Issue #3675: --noconsole flashes CMD window](https://github.com/pyinstaller/pyinstaller/issues/3675)
- [Configure app to start at log-in — Windows Developer Blog (Microsoft)](https://blogs.windows.com/windowsdeveloper/2017/08/01/configure-app-start-log/)
- [Configure Startup Applications in Windows — Microsoft Support](https://support.microsoft.com/en-us/windows/configure-startup-applications-in-windows-115a420a-0bff-4a6f-90e0-1934c844e473)
- [StartupTask Class (WinRT UWP) — Microsoft Learn](https://learn.microsoft.com/en-us/uwp/api/windows.applicationmodel.startuptask?view=winrt-26100)
- [PyInstaller onefile guide 2025 — ahmedsyntax.com](https://ahmedsyntax.com/pyinstaller-onefile/)
- [Nuitka vs PyInstaller — coderslegacy.com](https://coderslegacy.com/nuitka-vs-pyinstaller/)
- [Python Executable Generators — Sparx Engineering](https://sparxeng.com/blog/software/python-standalone-executable-generators-pyinstaller-nuitka-cx-freeze)

---
*Feature research for: Desktop widget bar / utility display framework (MonitorControl)*
*v1.1 addendum: autostart and .exe packaging*
*Researched: 2026-03-27*
