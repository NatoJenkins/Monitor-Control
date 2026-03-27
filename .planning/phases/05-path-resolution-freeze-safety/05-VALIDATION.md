---
phase: 5
slug: path-resolution-freeze-safety
status: active
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-27
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing, pytest.ini present) |
| **Config file** | `pytest.ini` at project root |
| **Quick run command** | `pytest tests/test_paths.py -x` |
| **Full suite command** | `pytest -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_paths.py -x`
- **After every plan wave:** Run `pytest -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | INFRA-01 | unit | `pytest tests/test_paths.py::test_get_config_path_is_absolute -x` | W0 (created in task) | pending |
| 05-01-01 | 01 | 1 | INFRA-01 | unit | `pytest tests/test_paths.py::test_get_config_path_cwd_independent -x` | W0 | pending |
| 05-01-01 | 01 | 1 | INFRA-01 | unit | `pytest tests/test_paths.py::test_get_config_path_parent_contains_host_dir -x` | W0 | pending |
| 05-01-01 | 01 | 1 | INFRA-01 | unit (source check) | `pytest tests/test_paths.py::test_no_bare_config_strings_in_host_main -x` | W0 | pending |
| 05-01-01 | 01 | 1 | INFRA-01 | unit (source check) | `pytest tests/test_paths.py::test_no_bare_config_strings_in_control_panel -x` | W0 | pending |
| 05-01-01 | 01 | 1 | INFRA-02 | unit | `pytest tests/test_paths.py::test_null_guard_stdout -x` | W0 | pending |
| 05-01-01 | 01 | 1 | INFRA-02 | unit | `pytest tests/test_paths.py::test_null_guard_stderr -x` | W0 | pending |
| 05-01-02 | 01 | 1 | INFRA-01, INFRA-02 | regression | `pytest -x` | existing | pending |

*Status: pending -- green -- red -- flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_paths.py` -- covers INFRA-01 and INFRA-02; created as first step of Task 1

*(All other test infrastructure -- pytest.ini, conftest.py, existing test files -- is already in place.)*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
