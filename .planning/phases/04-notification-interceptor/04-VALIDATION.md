---
phase: 4
slug: notification-interceptor
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >= 8.0 (currently 89 tests collected) |
| **Config file** | `pytest.ini` — `testpaths = tests` |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | NOTF-01 | unit (AST check) | `python -m pytest tests/test_notification_widget.py::test_no_request_access_async_in_widget -x` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 0 | NOTF-01 | unit (AST check) | `python -m pytest tests/test_notification_widget.py::test_no_pyqt6_import -x` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 0 | - | manual (spike) | `python spike_winrt_subprocess.py` | ❌ W0 | ⬜ pending |
| 4-02-01 | 02 | 1 | NOTF-02 | unit (mock WinRT) | `python -m pytest tests/test_notification_widget.py::test_permission_placeholder_when_denied -x` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 1 | NOTF-02 | unit | `python -m pytest tests/test_notification_widget.py::test_placeholder_frame_dimensions -x` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 1 | NOTF-03 | unit (mock WinRT) | `python -m pytest tests/test_notification_widget.py::test_renders_notification_content -x` | ❌ W0 | ⬜ pending |
| 4-02-04 | 02 | 1 | NOTF-03 | unit | `python -m pytest tests/test_notification_widget.py::test_idle_state_frame -x` | ❌ W0 | ⬜ pending |
| 4-02-05 | 02 | 1 | NOTF-04 | unit | `python -m pytest tests/test_notification_widget.py::test_auto_dismiss_does_not_remove_from_action_center -x` | ❌ W0 | ⬜ pending |
| 4-02-06 | 02 | 1 | NOTF-05 | unit | `python -m pytest tests/test_notification_widget.py::test_most_recent_notification_selected -x` | ❌ W0 | ⬜ pending |
| 4-02-07 | 02 | 1 | NOTF-05 | unit | `python -m pytest tests/test_notification_widget.py::test_auto_dismiss_timer -x` | ❌ W0 | ⬜ pending |
| 4-02-08 | 02 | 1 | NOTF-05 | unit | `python -m pytest tests/test_notification_widget.py::test_new_notification_resets_timer -x` | ❌ W0 | ⬜ pending |
| 4-02-09 | 02 | 1 | NOTF-05 | unit | `python -m pytest tests/test_notification_widget.py::test_blocklist_filters_app -x` | ❌ W0 | ⬜ pending |
| 4-02-10 | 02 | 1 | NOTF-03 | unit | `python -m pytest tests/test_notification_widget.py::test_config_update_applied -x` | ❌ W0 | ⬜ pending |
| 4-02-11 | 02 | 1 | All | unit (AST check) | `python -m pytest tests/test_notification_widget.py::test_nonblocking_put -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_notification_widget.py` — stubs covering all NOTF-0x test cases above
- [ ] `spike_winrt_subprocess.py` — standalone spike script (not a pytest file; validates asyncio/WinRT in spawn subprocess)
- [ ] `widgets/notification/__init__.py` — empty module init
- [ ] `widgets/notification/widget.py` — NotificationWidget class skeleton
- [ ] `widgets/notification/fonts/` — Inter-Regular.ttf and ShareTechMono-Regular.ttf (copy from `widgets/calendar/fonts/`)
- [ ] `requirements.txt` additions: `winrt-Windows.UI.Notifications.Management==3.2.1` and `winrt-runtime==3.2.1`

*Note on WinRT mocking:* All WinRT API calls must be mocked in unit tests via `unittest.mock.patch` on `UserNotificationListener.current` and async return values. Tests must be runnable without Display 3 or notification permission.

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Permission dialog appears on first run | NOTF-01 | Requires interactive Windows dialog; cannot be automated in CI | Run `python host/main.py` with a fresh user profile (no prior notification access granted); verify a Windows permission dialog appears |
| Toast notification appears in slot within a few seconds | NOTF-03 | Requires a real Windows toast to be sent; no reliable way to inject one in tests | Send a toast from another app (e.g., Teams, or `powershell New-BurntToastNotification`); verify it appears in the Display 3 notification slot |
| Notification slot shows placeholder when access denied | NOTF-02 | Requires notification access to be denied in Windows Settings | Deny notification access in Settings > Privacy > Notifications; restart host; verify placeholder renders |
| asyncio.run() works in spawn subprocess (spike) | NOTF-03 | Validates WinRT/subprocess compatibility; automated test cannot reproduce this environment | Run `python spike_winrt_subprocess.py` and review printed output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
