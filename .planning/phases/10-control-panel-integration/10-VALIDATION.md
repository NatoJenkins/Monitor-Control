---
phase: 10
slug: control-panel-integration
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `python -m pytest tests/test_control_panel_window.py -q` |
| **Full suite command** | `python -m pytest tests/ -q -m "not integration"` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_control_panel_window.py -q`
- **After every plan wave:** Run `python -m pytest tests/ -q -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 0 | POMO-06 | unit | `python -m pytest tests/test_control_panel_window.py::test_pomodoro_color_pickers_are_widgets -x` | ❌ W0 | ⬜ pending |
| 10-01-02 | 01 | 0 | POMO-06 | unit | `python -m pytest tests/test_control_panel_window.py::test_pomodoro_color_pickers_load_from_config -x` | ❌ W0 | ⬜ pending |
| 10-01-03 | 01 | 0 | POMO-06 | unit | `python -m pytest tests/test_control_panel_window.py::test_collect_config_includes_pomo_colors -x` | ❌ W0 (update) | ⬜ pending |
| 10-01-04 | 01 | 0 | CAL-06 | unit | `python -m pytest tests/test_control_panel_window.py::test_calendar_color_pickers_are_widgets -x` | ❌ W0 | ⬜ pending |
| 10-01-05 | 01 | 0 | CAL-06 | unit | `python -m pytest tests/test_control_panel_window.py::test_calendar_color_pickers_load_from_config -x` | ❌ W0 | ⬜ pending |
| 10-01-06 | 01 | 0 | CAL-06 | unit | `python -m pytest tests/test_control_panel_window.py::test_collect_config_includes_cal_colors -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_control_panel_window.py` — add 6 new test functions (listed in table above)
- [ ] `tests/test_control_panel_window.py` — update `test_pomodoro_accent_colors_load` (currently asserts `.text()` on QLineEdit; rewrite to assert `.color()` on ColorPickerWidget)
- [ ] `tests/test_control_panel_window.py` — verify `test_collect_config_includes_new_fields` still passes after attribute type changes

*Existing infrastructure covers all phase requirements — no new test files or conftest changes needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Color picker is visually correct (swatch + sliders render) in Pomodoro tab | POMO-06 | PyQt6 rendering requires display | Open control panel → Pomodoro tab → confirm 3 pickers visible with correct colors |
| Color picker is visually correct in Calendar tab | CAL-06 | PyQt6 rendering requires display | Open control panel → Calendar tab → confirm 2 pickers visible with correct colors |
| Live hot-reload after Save (Pomodoro) | POMO-06 | Requires running host + widget subprocess | Change work color → Save → verify Pomodoro widget updates accent color without restart |
| Live hot-reload after Save (Calendar) | CAL-06 | Requires running host + widget subprocess | Change time/date color → Save → verify Calendar text updates without restart |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
