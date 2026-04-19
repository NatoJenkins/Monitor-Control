---
phase: 6
slug: autostart-toggle
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest.ini or pyproject.toml (existing) |
| **Quick run command** | `pytest tests/test_autostart.py -q` |
| **Full suite command** | `pytest tests/ -q --ignore=tests/test_e2e_dummy.py` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_autostart.py -q`
- **After every plan wave:** Run `pytest tests/ -q --ignore=tests/test_e2e_dummy.py`
- **Before `/gsd:verify-work`:** Full suite must be green (excluding pre-existing `test_e2e_dummy` failure)
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | STRT-01, STRT-02 | unit | `pytest tests/test_autostart.py -q` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 1 | STRT-03 | unit | `pytest tests/test_autostart.py -q` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 1 | STRT-04 | unit | `pytest tests/test_autostart.py::test_startup_tab -q` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 1 | STRT-05 | unit | `pytest tests/test_autostart.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_autostart.py` — stubs for STRT-01 through STRT-05
- [ ] `control_panel/autostart.py` — module stub (empty functions)

*Existing pytest infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Registry Run key launches host at login | STRT-01 | Requires logout/login cycle | Enable toggle, log out, log back in, verify host process running |
| No terminal window visible at startup | STRT-01 | Requires visual inspection | Confirm no cmd/terminal window appears after login |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
