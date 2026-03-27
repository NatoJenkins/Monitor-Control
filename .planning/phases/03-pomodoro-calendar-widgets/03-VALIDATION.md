---
phase: 3
slug: pomodoro-calendar-widgets
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (>=8.0, verified working — 53 tests pass) |
| **Config file** | `pytest.ini` (testpaths = tests, integration marker defined) |
| **Quick run command** | `python -m pytest tests/ -m "not integration" -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds (unit), ~30 seconds (full with integration) |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -m "not integration" -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 0 | POMO-01..05, CAL-01..03 | unit stub | `python -m pytest tests/test_pomodoro_widget.py tests/test_calendar_widget.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | POMO-01 | unit | `python -m pytest tests/test_pomodoro_widget.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | POMO-02 | unit | `python -m pytest tests/test_pomodoro_widget.py::test_state_machine -x` | ❌ W0 | ⬜ pending |
| 03-01-04 | 01 | 1 | POMO-03 | unit | `python -m pytest tests/test_pomodoro_widget.py::test_frame_content -x` | ❌ W0 | ⬜ pending |
| 03-01-05 | 01 | 1 | CAL-01 | unit | `python -m pytest tests/test_calendar_widget.py -x -q` | ❌ W0 | ⬜ pending |
| 03-01-06 | 01 | 1 | CAL-02 | unit | `python -m pytest tests/test_calendar_widget.py::test_date_formats -x` | ❌ W0 | ⬜ pending |
| 03-02-01 | 02 | 2 | POMO-04 | unit | `python -m pytest tests/test_pomodoro_widget.py::test_control_signals -x` | ❌ W0 | ⬜ pending |
| 03-02-02 | 02 | 2 | POMO-05 | unit | `python -m pytest tests/test_pomodoro_widget.py::test_config_update -x` | ❌ W0 | ⬜ pending |
| 03-02-03 | 02 | 2 | CAL-03 | unit | `python -m pytest tests/test_calendar_widget.py::test_config_update -x` | ❌ W0 | ⬜ pending |
| 03-02-04 | 02 | 2 | POMO-04 | integration | `python -m pytest tests/test_pomodoro_command_file.py -m integration -x` | ❌ W0 | ⬜ pending |
| 03-02-05 | 02 | 2 | POMO-01..05+CAL-01..03 | integration | `python -m pytest tests/test_e2e_widgets.py -m integration -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pomodoro_widget.py` — stubs for POMO-01 through POMO-05
- [ ] `tests/test_calendar_widget.py` — stubs for CAL-01 through CAL-03
- [ ] `tests/test_e2e_widgets.py` — integration test: both widgets spawn and push frames
- [ ] `tests/test_pomodoro_command_file.py` — integration test: command-file → ControlSignal dispatch
- [ ] `widgets/pomodoro/__init__.py` — package marker
- [ ] `widgets/calendar/__init__.py` — package marker
- [ ] `widgets/pomodoro/fonts/` — bundled TTF directory (Inter, Digital-7, Share Tech Mono)
- [ ] `widgets/calendar/fonts/` — bundled TTF directory (same three fonts)

Note: `conftest.py` (session-scoped `qapp` fixture) already exists; no conftest changes needed.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Pomodoro visual renders correctly on actual hardware bar | POMO-03 | Pixel-perfect layout on 515px tall screen requires visual inspection | Run host, observe Pomodoro slot shows label + countdown in correct accent color |
| Calendar time updates every second visually | CAL-01 | Timing continuity hard to assert in unit tests | Run host, watch calendar slot for 3 seconds, confirm seconds digit increments |
| Shortcut keys trigger control panel buttons | POMO-04 | QShortcut behavior in windowed app not easily testable headlessly | Launch control panel, press Ctrl+S, observe Start button activates and command file written |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
