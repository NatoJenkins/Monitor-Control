---
phase: 11
slug: layout-tab-bg-color-picker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 11 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/test_control_panel_window.py -q` |
| **Full suite command** | `python -m pytest tests/ -q -m "not integration" --ignore=tests/test_autostart.py` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_control_panel_window.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q -m "not integration" --ignore=tests/test_autostart.py`
- **Before `/gsd:verify-work`:** Full suite must be green (30 tests in test_control_panel_window.py)
- **Max feedback latency:** ~5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 11-01-01 | 01 | 0 | BG-04 | unit | `python -m pytest tests/test_control_panel_window.py::test_bg_color_picker_is_widget -x` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 0 | BG-04 | unit | `python -m pytest tests/test_control_panel_window.py::test_bg_color_picker_loads_from_config -x` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 0 | BG-04 | unit | `python -m pytest tests/test_control_panel_window.py::test_collect_config_includes_bg_color -x` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | BG-04 | unit | `python -m pytest tests/test_control_panel_window.py -q` | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_control_panel_window.py` — add 3 failing tests: `test_bg_color_picker_is_widget`, `test_bg_color_picker_loads_from_config`, `test_collect_config_includes_bg_color`

*No new test files or fixtures needed — pytest + qapp fixture already present.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Adjusting picker and clicking Save causes bar background to change immediately | BG-04 | End-to-end hot-reload requires running host + widgets; cannot trigger QFileSystemWatcher from tests | Open Layout tab, move hue slider, click Save, observe bar background color changes within ~1s |
| Reopening control panel shows picker restored to previously saved color | BG-04 | Requires closing and reopening the exe; cannot automate in unit tests | Save a color, close Settings, reopen Settings, verify Layout tab picker shows the saved color |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
