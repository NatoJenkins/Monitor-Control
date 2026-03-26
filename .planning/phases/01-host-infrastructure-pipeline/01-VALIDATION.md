---
phase: 1
slug: host-infrastructure-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (to be installed in Wave 0) |
| **Config file** | `pytest.ini` — Wave 0 gap |
| **Quick run command** | `pytest tests/ -x -q -k "not test_e2e"` |
| **Full suite command** | `pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds (unit only) |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/ -x -q -k "not test_e2e"`
- **After every plan wave:** Run `pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~5 seconds (unit), ~30 seconds (full with e2e)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 1-01-01 | 01 | 1 | HOST-01 | unit | `pytest tests/test_win32_utils.py::test_find_target_screen -x` | ❌ W0 | ⬜ pending |
| 1-01-02 | 01 | 1 | HOST-01 | unit | `pytest tests/test_window.py::test_window_placement -x` | ❌ W0 | ⬜ pending |
| 1-01-03 | 01 | 1 | HOST-02 | unit | `pytest tests/test_window.py::test_window_flags -x` | ❌ W0 | ⬜ pending |
| 1-02-01 | 02 | 2 | HOST-04 | unit | `pytest tests/test_win32_utils.py::test_clip_cursor_rect -x` | ❌ W0 | ⬜ pending |
| 1-02-02 | 02 | 2 | HOST-04 | unit (mock) | `pytest tests/test_win32_utils.py::test_session_unlock_reapply -x` | ❌ W0 | ⬜ pending |
| 1-02-03 | 02 | 2 | HOST-04 | unit (mock) | `pytest tests/test_win32_utils.py::test_displaychange_reapply -x` | ❌ W0 | ⬜ pending |
| 1-03-01 | 03 | 3 | HOST-03 | unit | `pytest tests/test_compositor.py::test_slot_blit -x` | ❌ W0 | ⬜ pending |
| 1-03-02 | 03 | 3 | HOST-03 | unit | `pytest tests/test_compositor.py::test_placeholder_fill -x` | ❌ W0 | ⬜ pending |
| 1-03-03 | 03 | 3 | HOST-05 | static | `pytest tests/test_guard.py::test_main_guard_exists -x` | ❌ W0 | ⬜ pending |
| 1-03-04 | 03 | 3 | IPC-01 | unit | `pytest tests/test_dummy_widget.py::test_nonblocking_put -x` | ❌ W0 | ⬜ pending |
| 1-03-05 | 03 | 3 | IPC-01 | static | `pytest tests/test_dummy_widget.py::test_no_pyqt6_import -x` | ❌ W0 | ⬜ pending |
| 1-03-06 | 03 | 3 | IPC-02 | unit | `pytest tests/test_queue_drain.py::test_drain_loop -x` | ❌ W0 | ⬜ pending |
| 1-03-07 | 03 | 3 | IPC-03 | unit | `pytest tests/test_process_manager.py::test_drain_before_join -x` | ❌ W0 | ⬜ pending |
| 1-03-08 | 03 | 3 | IPC-03 | unit | `pytest tests/test_process_manager.py::test_kill_fallback -x` | ❌ W0 | ⬜ pending |
| 1-03-09 | 03 | 3 | IPC-04 | integration | `pytest tests/test_e2e_dummy.py::test_dummy_frame_received -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_window.py` — stubs for HOST-01, HOST-02
- [ ] `tests/test_win32_utils.py` — stubs for HOST-01, HOST-04
- [ ] `tests/test_compositor.py` — stubs for HOST-03
- [ ] `tests/test_process_manager.py` — stubs for IPC-03
- [ ] `tests/test_queue_drain.py` — stubs for IPC-02
- [ ] `tests/test_dummy_widget.py` — stubs for IPC-01, IPC-04
- [ ] `tests/test_guard.py` — HOST-05 static AST check for `__main__` guard
- [ ] `tests/test_e2e_dummy.py` — IPC-04 end-to-end (mark with `@pytest.mark.integration`)
- [ ] `tests/conftest.py` — shared fixtures (mock QApplication, mock screens, mock Win32 calls)
- [ ] `pytest.ini` — test discovery config, markers for `integration`
- [ ] Framework install: `pip install pytest pytest-mock` added to requirements.txt

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Host window fills Display 3 exactly, no black strip, no overflow | HOST-01 | Requires real hardware with 3-monitor layout | Boot host; visually confirm window fills 1920×515 display; check no taskbar entry |
| Cursor cannot enter Display 3 after startup | HOST-04 | Requires real hardware with physical cursor | Move cursor toward Display 3; confirm it stops at boundary |
| Cursor lockout restored after Win+L unlock | HOST-04 | Requires real Windows session lock/unlock cycle | Lock screen (Win+L); unlock; move cursor toward Display 3; confirm boundary enforced |
| Cursor lockout restored after sleep/wake | HOST-04 | Requires real hardware sleep/wake cycle | Put machine to sleep; wake; confirm cursor boundary enforced |
| Dummy widget colored rectangle visible, updating at drain interval | IPC-04 | Requires real hardware display | Observe Display 3; confirm colored rectangle appears and updates each drain tick |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
