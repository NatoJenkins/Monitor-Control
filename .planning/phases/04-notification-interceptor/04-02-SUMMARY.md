---
phase: 04-notification-interceptor
plan: "02"
subsystem: notification-widget
tags: [winrt, pillow, notification, pyqt6, control-panel, polling, subprocess]

dependency_graph:
  requires:
    - phase: 04-01-winrt-spike
      provides: winrt polling architecture validated, get_binding("ToastGeneric") string form, creation_time Python datetime confirmed
    - phase: 03-02-control-panel
      provides: _build_*_tab pattern, _find_widget_settings, _update_widget_settings, _collect_config, _load_values
    - phase: 02-01-config-system
      provides: ConfigLoader, register_widget_type, WIDGET_REGISTRY, ProcessManager
  provides:
    - NotificationWidget class with Pillow rendering (widgets/notification/widget.py)
    - WinRT polling at 2s interval with permission check, app name/title/body/timestamp display
    - Auto-dismiss to bell icon after configurable timeout (default 30s)
    - Blocked apps filtering (per-widget config)
    - Exception-resilient run loop (subprocess does not crash on WinRT or Pillow errors)
    - None-safe text extraction from WinRT IVectorView (coerce None -> "")
    - Host-side RequestAccessAsync before widget spawn
    - config.json notification entry at x=1280 (640x515)
    - Control panel Notification tab with timeout/font/blocklist
  affects: []

tech-stack:
  added: []
  patterns:
    - "Deferred WinRT import inside methods: winrt packages imported only inside _get_winrt_listener() so widget.py is importable in test environments without winrt installed"
    - "list() wrapping WinRT IVectorView before indexing: IVectorView.len() unreliable in winrt 3.2.1; always convert to list first"
    - "None-coercion on WinRT text elements: elem.text can return None for empty toast nodes; use (elem.text or '') pattern"
    - "Resilient subprocess loop: _run_once() extracted from run(); try/except Exception catches WinRT/Pillow errors, logs them, renders idle, and continues — subprocess never crashes on transient errors"
    - "KeyboardInterrupt as test sentinel for infinite loops: StopIteration is a subclass of Exception and gets caught by except Exception; use KeyboardInterrupt (BaseException) to break test loops"

key-files:
  created:
    - widgets/notification/widget.py
    - tests/test_notification_widget.py
  modified:
    - host/main.py
    - config.json
    - control_panel/main_window.py

key-decisions:
  - "list(binding.get_text_elements()) required — WinRT IVectorView does not support len() reliably; convert to list before indexing (hardware regression fix)"
  - "_run_once() separated from run() — enables targeted exception handling so transient WinRT/Pillow errors log and continue rather than crashing the subprocess (prevents dark red slot)"
  - "None text coercion (elem.text or '') — PowerShell AppendChild DOM quirk sends toast nodes with .text=None; coercing prevents Pillow TypeError on render"
  - "KeyboardInterrupt sentinel for infinite-loop tests — StopIteration is caught by except Exception; BaseException subclasses propagate through the guard"

patterns-established:
  - "Resilient widget run loop: always wrap polling iteration in try/except Exception with idle-frame fallback"
  - "WinRT collection access: always list() before indexing; always (value or '') before string operations"

requirements-completed: [NOTF-01, NOTF-02, NOTF-03, NOTF-04, NOTF-05]

duration: ~45min (Tasks 1+2 prior session) + ~30min (Task 3 diagnosis and fix)
completed: "2026-03-26"
---

# Phase 4 Plan 2: Notification Widget Summary

**WinRT polling notification widget with Pillow rendering, auto-dismiss bell icon, control panel tab, and exception-resilient subprocess loop; hardware regression fixed (subprocess crash on empty toast nodes).**

## Performance

- **Duration:** ~75 min total (Tasks 1+2 in prior session; Task 3 diagnosis + fix in continuation)
- **Tasks:** 3 (Tasks 1, 2, and 3 hardware fix)
- **Files modified:** 5

## Accomplishments

- NotificationWidget polls WinRT at 2s intervals, renders app name / title / body / HH:MM timestamp in 640x515 Pillow frame
- Auto-dismisses to bell icon after configurable timeout (default 30s); does NOT call remove_notification per v1 decision
- Exception-resilient run loop: `_run_once()` wrapped in `try/except Exception` so transient WinRT or Pillow errors log and render idle rather than crashing the subprocess (root cause of the dark red slot on hardware)
- None-safe text extraction: `list(get_text_elements())` + `(elem.text or "")` guards against WinRT IVectorView quirks and empty toast nodes
- 17 unit tests pass (3 added as hardware regression tests)

## Hardware Verification (Task 3)

**First test result:** Notification slot on Display 3 turned red.

**Root cause identified:** The widget subprocess crashed on its first poll cycle. The PowerShell test script encountered an `AppendChild` DOM quirk (WinRT live NodeList) which left toast text nodes with `.text = None`. The widget called `text_elements[0].text` (returning `None`), then passed `None` to Pillow's `draw.textbbox()`, which raised `TypeError: expected str, got NoneType`. Since `run()` had no exception handling, the subprocess exited. The drain timer's `is_alive()` check returned False, calling `compositor.mark_crashed()`, which filled the slot with `#8B0000` (dark red).

**Fix applied (65a196c):**
1. `list(binding.get_text_elements())` — convert IVectorView before indexing
2. `(elem.text or "")` — coerce None text values to empty strings
3. `_run_once()` extracted from loop; `run()` wraps it in `try/except Exception` with idle-frame fallback
4. 3 regression tests added

**Corrected PowerShell test command** (works around the AppendChild DOM quirk by using `.InnerText` property assignment instead):

```powershell
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$texts = $xml.GetElementsByTagName("text")
$texts[0].InnerText = "Test Title"
$texts[1].InnerText = "Test body message"
$toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier("MonitorControl Test").Show($toast)
```

Note: The system Windows toast appearing on Monitor 1 is expected behavior — it is the OS notification, not our widget. Our widget reads from the notification history (via WinRT polling) and displays independently in the bar slot.

**Next verification step:** Re-run the host with the fixed widget. The strip monitor should now show the idle bell icon. Fire the corrected PowerShell command above. Within 2-3 seconds, the notification slot should display "MonitorControl Test" / "Test Title" / "Test body message" / HH:MM timestamp. After 30 seconds, it should revert to the bell icon.

## Task Commits

1. **Task 1: Create NotificationWidget and unit tests** — `c159dae` (test), `d373aeb` (feat)
2. **Task 2: Integrate notification widget into host, config, and control panel** — `69fa210` (feat)
3. **Task 3: Hardware fix — subprocess crash on empty/None toast fields** — `65a196c` (fix)

## Files Created/Modified

- `widgets/notification/widget.py` — NotificationWidget class, run loop, Pillow rendering, WinRT polling
- `tests/test_notification_widget.py` — 17 unit tests (14 original + 3 hardware regression)
- `host/main.py` — RequestAccessAsync before widget spawn; notification widget registration
- `config.json` — notification widget entry at x=1280, 640x515, settings with auto_dismiss_seconds and blocked_apps
- `control_panel/main_window.py` — Notification tab with timeout spinbox, font dropdown, blocked apps list widget

## Decisions Made

- `list(get_text_elements())` required — WinRT IVectorView does not reliably support `len()` in winrt 3.2.1
- `(elem.text or "")` coercion — toast nodes from PowerShell AppendChild quirk return `.text = None`
- `_run_once()` extracted from `run()` — enables `try/except Exception` at the loop level without catching `KeyboardInterrupt` or `SystemExit`
- `KeyboardInterrupt` as test sentinel — `StopIteration` is a subclass of `Exception` and would be caught by the guard; `KeyboardInterrupt` (BaseException, not Exception) propagates through

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Subprocess crash on None text elements from empty toast nodes**
- **Found during:** Task 3 (hardware verification)
- **Issue:** PowerShell AppendChild DOM quirk sent toast with `.text = None` on text nodes. Pillow's `draw.textbbox()` raised `TypeError: expected str, got NoneType`, crashing the subprocess.
- **Fix:** `(elem.text or "")` coercion on all text element access
- **Files modified:** `widgets/notification/widget.py`
- **Verification:** `test_fetch_latest_none_text_coerced_to_empty_string` + `test_render_notification_with_empty_strings` pass
- **Committed in:** 65a196c

**2. [Rule 2 - Missing Critical] No exception handling in run() loop**
- **Found during:** Task 3 (hardware verification — dark red slot diagnosis)
- **Issue:** Any exception in the polling cycle crashed the subprocess silently. The drain timer detected `is_alive() = False` and called `compositor.mark_crashed()` → dark red slot.
- **Fix:** Extracted `_run_once()` from `run()`; wrapped in `try/except Exception` with idle-frame fallback and stderr logging
- **Files modified:** `widgets/notification/widget.py`, `tests/test_notification_widget.py`
- **Verification:** `test_run_once_exception_does_not_kill_subprocess` passes; subprocess loop continues after simulated WinRT error
- **Committed in:** 65a196c

**3. [Rule 1 - Bug] WinRT IVectorView indexing without list() conversion**
- **Found during:** Task 3 (code review during diagnosis)
- **Issue:** `len(text_elements)` on a WinRT IVectorView is not guaranteed to work in winrt 3.2.1; converting to `list()` first is the safe pattern
- **Fix:** `text_elements = list(binding.get_text_elements()) if binding else []`
- **Files modified:** `widgets/notification/widget.py`
- **Verification:** `test_fetch_latest_none_text_coerced_to_empty_string` (exercises this code path) passes
- **Committed in:** 65a196c

---

**Total deviations:** 3 auto-fixed (2 bugs, 1 missing critical)
**Impact on plan:** All three fixes required for hardware correctness. Without them the widget crashes on first notification event. No scope creep.

## Issues Encountered

- PowerShell `AppendChild` on a WinRT live NodeList (`XmlNodeList`) is a known DOM quirk where the node is inserted but the `.text` attribute remains None. Workaround: use `.InnerText =` property assignment instead (see corrected test command above).

## User Setup Required

None — notification permission is handled by `RequestAccessAsync` in `host/main.py` before widget spawn. User only needs to grant the Windows permission dialog on first run (already done).

## Next Phase Readiness

Phase 4 is the final phase of v1. All requirements met:
- NOTF-01: Host calls RequestAccessAsync from Qt main thread before widget spawn
- NOTF-02: Widget checks GetAccessStatus and renders permission placeholder if not ALLOWED
- NOTF-03: Notification polling every 2 seconds via GetNotificationsAsync
- NOTF-04: Auto-dismiss to idle bell icon after configurable timeout; no remove_notification call
- NOTF-05: Most recent notification displayed with app name, title, body, HH:MM timestamp

Remaining: hardware re-verification after the subprocess crash fix (use corrected PowerShell command).

## Self-Check: PASSED

- `widgets/notification/widget.py`: FOUND
- `tests/test_notification_widget.py`: FOUND
- `host/main.py`: FOUND (contains request_access_async and register_widget_type("notification"))
- `config.json`: FOUND (contains notification widget entry at x=1280)
- `control_panel/main_window.py`: FOUND (contains _build_notification_tab)
- `.planning/phases/04-notification-interceptor/04-02-SUMMARY.md`: FOUND
- Commit c159dae (test RED): FOUND
- Commit d373aeb (feat GREEN): FOUND
- Commit 69fa210 (feat integration): FOUND
- Commit 65a196c (fix hardware regression): FOUND
- 105 tests passing

---
*Phase: 04-notification-interceptor*
*Completed: 2026-03-26*
