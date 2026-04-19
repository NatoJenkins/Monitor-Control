---
phase: 2
slug: config-system-control-panel
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` or `pyproject.toml` (Wave 0 installs if absent) |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 2-01-01 | 01 | 0 | CFG-01 | unit | `python -m pytest tests/test_config_loader.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-02 | 01 | 1 | CFG-01 | unit | `python -m pytest tests/test_config_loader.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-03 | 01 | 1 | CFG-02 | unit | `python -m pytest tests/test_config_loader.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-04 | 01 | 1 | CFG-02 | integration | `python -m pytest tests/test_config_loader.py -x -q` | ❌ W0 | ⬜ pending |
| 2-01-05 | 01 | 1 | CFG-03 | integration | `python -m pytest tests/test_process_manager.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-01 | 02 | 2 | CTRL-01 | unit | `python -m pytest tests/test_control_panel_window.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-02 | 02 | 2 | CTRL-02 | integration | `python -m pytest tests/test_config_io.py -x -q` | ❌ W0 | ⬜ pending |
| 2-02-03 | 02 | 2 | CTRL-03 | integration | `python -m pytest tests/test_control_panel_window.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config_loader.py` — stubs for CFG-01 (schema validation, ConfigLoader.load())
- [ ] `tests/test_config_loader.py` — stubs for CFG-02 (QFileSystemWatcher re-add, debounce; watcher tests co-located with ConfigLoader tests)
- [ ] `tests/test_process_manager.py` — stubs for CFG-03 (inbound queue, CONFIG_UPDATE delivery)
- [ ] `tests/test_control_panel_window.py` — stubs for CTRL-01, CTRL-03 (QMainWindow launches, form fields)
- [ ] `tests/test_config_io.py` — stubs for CTRL-02 (atomic write via os.replace)
- [ ] `tests/conftest.py` — shared fixtures (tmp config path, fake widget process)

*If pytest not installed: `pip install pytest`*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| QFileSystemWatcher re-add after atomic replace fires twice | CFG-02 | Requires real filesystem, two sequential saves | Launch host, save config.json twice from control panel, verify both trigger hot-reload in host logs |
| Control panel window renders correctly on HDMI monitor | CTRL-01 | GUI rendering requires visual inspection | Launch `python -m control_panel`, verify window appears with layout and per-widget sections |
| Widget process stops cleanly on removal | CFG-03 | Process lifecycle requires OS-level inspection | Remove widget from config, verify process no longer in `ps` output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
