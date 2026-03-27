---
phase: 04-notification-interceptor
plan: "01"
subsystem: winrt-spike
tags: [winrt, asyncio, subprocess, spike, notifications]
dependency_graph:
  requires: []
  provides: [winrt-packages-installed, notification-widget-package-skeleton, spike-validation-results]
  affects: [04-02-notification-widget]
tech_stack:
  added:
    - winrt-Windows.UI.Notifications.Management==3.2.1
    - winrt-Windows.UI.Notifications==3.2.1
    - winrt-Windows.Foundation==3.2.1
    - winrt-Windows.Foundation.Collections==3.2.1
    - winrt-Windows.ApplicationModel==3.2.1
    - winrt-runtime==3.2.1
  patterns:
    - asyncio.run() with WinRT IAsyncOperation in spawn subprocess
    - UserNotificationListener.current (property, not method)
    - get_binding("ToastGeneric") string form (KnownNotificationBindings.TOAST_GENERIC absent in 3.2.1)
    - creation_time is standard Python datetime (UTC timezone-aware)
key_files:
  created:
    - requirements.txt (WinRT package pins added)
    - widgets/notification/__init__.py (empty package init)
    - tests/spike_winrt_subprocess.py (standalone spike validation script)
  modified: []
decisions:
  - Use POLLING (get_notifications_async at 2s interval) for notification fetching -- add_notification_changed raises OSError WinError -2147023728 on python.org Python (confirmed on real hardware)
  - get_binding("ToastGeneric") string form required -- KnownNotificationBindings.TOAST_GENERIC constant does not exist in winrt-Windows.UI.Notifications==3.2.1
  - creation_time is Python datetime (UTC-aware) -- format with n.creation_time.astimezone().strftime("%H:%M") for local time display
  - Five winrt packages required (not two) -- Management + Notifications + Foundation + Foundation.Collections + ApplicationModel + runtime
metrics:
  duration_seconds: 419
  completed_date: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 3
  files_modified: 1
---

# Phase 4 Plan 1: WinRT Subprocess Spike Summary

**One-liner:** WinRT asyncio.run() in spawn subprocess confirmed working; polling architecture validated on real hardware with 20 live notifications; creation_time is Python datetime (UTC).

## Spike Results

### Concern 1: asyncio.run() in spawn subprocess
**Status: PASSED**

`asyncio.run()` with a WinRT IAsyncOperation (`get_notifications_async`) completes successfully in a `multiprocessing.Process(spawn)` subprocess. No `RuntimeError`, no silent hang. The ProactorEventLoop correctly bridges WinRT async operations.

### Concern 2: GetAccessStatus() cross-process visibility
**Status: PASSED**

`GetAccessStatus()` returns `ALLOWED` in a fresh spawn subprocess after `RequestAccessAsync()` was called in the host process. Permission is user-level system state, confirmed persistent across process boundaries.

- Host `RequestAccessAsync()` result: **ALLOWED**
- Subprocess `GetAccessStatus()` result: **ALLOWED**
- Matches host: **yes**

### Concern 3: Polling GetNotificationsAsync() from subprocess
**Status: PASSED**

`GetNotificationsAsync(NotificationKinds.TOAST)` returns a list of `UserNotification` objects. Tested with 20 live notifications.

- Notification count: **20**
- App name extraction: **OK** (e.g., "Snipping Tool")
- Text extraction via `get_binding("ToastGeneric")`: **OK**
- Event subscription (`add_notification_changed`): **FAILED** (expected on python.org Python — OSError WinError -2147023728)

## Key Findings for Plan 04-02

### creation_time Python type
`UserNotification.creation_time` is a standard Python **`datetime.datetime`** object with UTC timezone info.

Format for local HH:MM display:
```python
n.creation_time.astimezone().strftime("%H:%M")
```
No `.to_datetime()` call needed — it's already a Python datetime.

### API Naming Corrections Discovered
| Research Assumption | Actual 3.2.1 Behavior |
|--------------------|-----------------------|
| `KnownNotificationBindings.TOAST_GENERIC` constant | Does not exist; use `get_binding("ToastGeneric")` string |
| `str(UserNotificationListenerAccessStatus.ALLOWED)` returns "ALLOWED" | Returns integer "1"; compare enum directly |
| Two winrt packages sufficient | Six packages required: Management + Notifications + Foundation + Foundation.Collections + ApplicationModel + runtime |

### Polling vs Event Subscription Recommendation
**Use POLLING** at a 2-second interval via `get_notifications_async(NotificationKinds.TOAST)`.

`add_notification_changed()` raises `OSError: [WinError -2147023728] Element not found` on python.org Python installations (confirmed on this machine). This matches the known reliability issue documented in RESEARCH.md.

### Package Requirements (updated from initial plan)
The plan specified 2 packages; 6 are actually required at runtime:

```
winrt-Windows.UI.Notifications.Management==3.2.1  # UserNotificationListener
winrt-Windows.UI.Notifications==3.2.1             # NotificationKinds
winrt-Windows.Foundation==3.2.1                   # DateTimeOffset -> datetime
winrt-Windows.Foundation.Collections==3.2.1       # IVector (notification list)
winrt-Windows.ApplicationModel==3.2.1             # app_info.display_info.display_name
winrt-runtime==3.2.1                               # WinRT async bridging
```

## Artifacts Delivered

| Artifact | Path | Purpose |
|----------|------|---------|
| WinRT package pins | `requirements.txt` | Pinned 6 packages for reproducible install |
| Package init | `widgets/notification/__init__.py` | Empty Python package for notification widget |
| Spike script | `tests/spike_winrt_subprocess.py` | Standalone validation (232 lines, exits 0 on PASS) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] KnownNotificationBindings.TOAST_GENERIC does not exist in winrt 3.2.1**
- **Found during:** Task 2 execution (running spike)
- **Issue:** Plan specified `get_binding(KnownNotificationBindings.TOAST_GENERIC)` but this constant is absent from the 3.2.1 package
- **Fix:** Changed to `get_binding("ToastGeneric")` using the template name string directly
- **Files modified:** `tests/spike_winrt_subprocess.py`
- **Commit:** 728e4e1

**2. [Rule 1 - Bug] Status enum str() returns integer not string label**
- **Found during:** Task 2 execution (spike output showed "1" not "ALLOWED")
- **Issue:** `str(UserNotificationListenerAccessStatus.ALLOWED)` returns "1"; host/subprocess comparison used string matching
- **Fix:** Import enum in host section, compare directly against `UserNotificationListenerAccessStatus.ALLOWED`, format display string explicitly
- **Files modified:** `tests/spike_winrt_subprocess.py`
- **Commit:** 728e4e1

**3. [Rule 2 - Missing dependencies] Four additional winrt peer packages required**
- **Found during:** Task 1 verification and Task 2 spike execution
- **Issue:** `NotificationKinds` requires `winrt-Windows.UI.Notifications`; `get_notifications_async` return type requires `winrt-Windows.Foundation` and `winrt-Windows.Foundation.Collections`; `app_info` requires `winrt-Windows.ApplicationModel`
- **Fix:** Added all four packages to requirements.txt and installed them
- **Files modified:** `requirements.txt`
- **Commit:** 728e4e1

### Deferred Items
- `test_e2e_dummy.py::test_dummy_frame_received` was already failing before this plan (pre-existing flaky integration test, timing-dependent subprocess spawn). Out of scope — not caused by this plan's changes.

## Success Criteria

- [x] WinRT packages installed and importable from Python
- [x] Spike script syntactically valid and covers all three validation concerns
- [x] Notification widget package skeleton exists for plan 04-02 to build on
- [x] No existing tests broken (88 passed, 1 pre-existing flaky excluded)

## Self-Check: PASSED
