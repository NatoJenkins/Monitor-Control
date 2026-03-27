# Roadmap: MonitorControl

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-27)
- 🚧 **v1.1 Startup & Distribution** — Phases 5–7 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-27</summary>

- [x] Phase 1: Host Infrastructure + Pipeline (3/3 plans) — completed 2026-03-26
- [x] Phase 2: Config System + Control Panel (2/2 plans) — completed 2026-03-27
- [x] Phase 3: Pomodoro + Calendar Widgets (2/2 plans) — completed 2026-03-27
- [x] Phase 4: Notification Interceptor (2/2 plans) — completed 2026-03-27

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

### 🚧 v1.1 Startup & Distribution (In Progress)

**Milestone Goal:** Make MonitorControl feel like finished software — autostart on login and a distributable control panel .exe.

- [x] **Phase 5: Path Resolution & Freeze Safety** - Fix config path resolution and console-null-guard so both entry points work from any launch context (completed 2026-03-27)
- [x] **Phase 6: Autostart Toggle** - Control panel Startup tab that reads/writes HKCU Run key to enable host autostart at Windows login (completed 2026-03-27)
- [ ] **Phase 7: Control Panel Packaging** - PyInstaller --onedir --noconsole build producing a standalone MonitorControl.exe

## Phase Details

### Phase 5: Path Resolution & Freeze Safety
**Goal**: Config resolution is correct regardless of launch context, and the host is safe to run without a console window
**Depends on**: Phase 4 (v1.0 complete)
**Requirements**: INFRA-01, INFRA-02
**Success Criteria** (what must be TRUE):
  1. Host and control panel each find config.json correctly when launched from any directory (e.g., double-clicked from Desktop or launched via registry Run key from C:\Windows\System32 cwd)
  2. Host process starts without crashing when run via pythonw.exe (sys.stdout and sys.stderr are None — all print() calls must not raise AttributeError)
  3. `shared/paths.py` provides `get_config_path()` consumed by both `host/main.py` and `control_panel/__main__.py` — no bare "config.json" strings remain in either entry point
**Plans:** 1 plan

Plans:
- [x] 05-01-PLAN.md — TDD: shared/paths.py + startup null-guard + entry point updates (completed 2026-03-27)

### Phase 6: Autostart Toggle
**Goal**: Users can enable and disable host autostart at Windows login from the control panel, with no terminal visible at launch
**Depends on**: Phase 5
**Requirements**: STRT-01, STRT-02, STRT-03, STRT-04, STRT-05
**Success Criteria** (what must be TRUE):
  1. Checking the Startup tab toggle registers the host under HKCU\Software\Microsoft\Windows\CurrentVersion\Run; logging out and back in launches the host with no terminal window
  2. Unchecking the toggle removes the HKCU Run entry; host no longer launches at login
  3. Opening the control panel always reflects the live registry state of the toggle (not cached — re-reads HKCU on every panel open)
  4. The Startup tab displays "MonitorControl will start automatically at next login" when the toggle is checked
**Plans:** 1/1 plans complete

Plans:
- [ ] 06-01-PLAN.md — Registry module + launcher script + Startup tab with live HKCU toggle

### Phase 7: Control Panel Packaging
**Goal**: The control panel runs as a standalone .exe on any Windows machine with no Python environment required
**Depends on**: Phase 5
**Requirements**: PKG-01, PKG-02, PKG-03, PKG-04
**Success Criteria** (what must be TRUE):
  1. MonitorControl.exe launches from any directory and the control panel opens correctly, loading config.json from the exe's directory
  2. MonitorControl.exe shows no terminal or console window on launch
  3. MonitorControl.exe displays a custom .ico application icon in Windows Explorer and Task Manager (not the generic Python icon)
  4. Running `pyinstaller build/control_panel.spec` from the project root reproduces the distributable build from a clean checkout
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

## Progress

**Execution Order:** 5 → 6 → 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Host Infrastructure + Pipeline | v1.0 | 3/3 | Complete | 2026-03-26 |
| 2. Config System + Control Panel | v1.0 | 2/2 | Complete | 2026-03-27 |
| 3. Pomodoro + Calendar Widgets | v1.0 | 2/2 | Complete | 2026-03-27 |
| 4. Notification Interceptor | v1.0 | 2/2 | Complete | 2026-03-27 |
| 5. Path Resolution & Freeze Safety | v1.1 | 1/1 | Complete | 2026-03-27 |
| 6. Autostart Toggle | 1/1 | Complete   | 2026-03-27 | - |
| 7. Control Panel Packaging | v1.1 | 0/? | Not started | - |

---
*Roadmap created: 2026-03-26*
*Last updated: 2026-03-27 after Phase 6 planning (1 plan created)*
