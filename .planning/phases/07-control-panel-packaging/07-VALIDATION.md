---
phase: 7
slug: control-panel-packaging
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.0 |
| **Config file** | `pytest.ini` (exists at project root) |
| **Quick run command** | `pytest tests/ -x -q` |
| **Full suite command** | `pytest tests/` |
| **Estimated runtime** | ~10 seconds (unit tests only; smoke tests are manual) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q`
- **After every plan wave:** Run `pytest tests/`
- **Before `/gsd:verify-work`:** Full suite must be green + manual smoke of `MonitorControl.exe`
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 7-01-01 | 01 | 0 | PKG-03, PKG-04 | unit | `pytest tests/test_packaging.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-02 | 01 | 1 | PKG-02 | unit + manual | `pytest tests/test_packaging.py -x -q` | ❌ W0 | ⬜ pending |
| 7-01-03 | 01 | 1 | PKG-04 | unit | `pytest tests/test_packaging.py::test_spec_file_exists -x` | ❌ W0 | ⬜ pending |
| 7-01-04 | 01 | 1 | paths | unit | `pytest tests/test_packaging.py::test_frozen_path_guard -x` | ❌ W0 | ⬜ pending |
| 7-01-05 | 01 | 2 | PKG-01, PKG-02, PKG-03, PKG-04 | smoke (manual) | Launch `dist/MonitorControl/MonitorControl.exe` visually | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_packaging.py` — stubs for PKG-04 (spec file exists, icon file exists), frozen path guard unit test
- [ ] No new framework install needed — pytest already present

*Wave 0 creates test stubs before any implementation work begins.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Exe launches, control panel opens | PKG-01 | Requires real GUI on Windows; no headless automation | Run `dist/MonitorControl/MonitorControl.exe` from a different directory; control panel must open and load config |
| No console window appears | PKG-02 | Console window visibility is OS-level; cannot assert from pytest | Launch exe and visually confirm no black terminal window appears |
| Icon visible in Explorer/Task Manager | PKG-03 | Windows shell/icon cache; cannot assert from pytest | After build, open Explorer, navigate to `dist/MonitorControl/`, confirm custom icon (not generic Python) |
| Build reproducible from clean checkout | PKG-04 | Full build requires pyinstaller installed and Qt binaries available | Run `pyinstaller build/control_panel.spec` from project root; dist output must be structurally equivalent |
| Autostart read-only works from exe | STRT-03 | Registry read requires running exe context | Launch exe, open Startup tab, verify current autostart state displays correctly |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (unit tests ~10s; manual smokes documented)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
