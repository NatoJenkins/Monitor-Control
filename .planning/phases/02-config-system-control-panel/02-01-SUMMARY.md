---
phase: 02-config-system-control-panel
plan: 01
subsystem: config
tags: [PyQt6, QFileSystemWatcher, QTimer, multiprocessing, config, hot-reload]

# Dependency graph
requires:
  - phase: 01-host-infrastructure-ipc-pipeline
    provides: ProcessManager, WidgetBase, DummyWidget, Compositor, QueueDrainTimer, FrameData

provides:
  - config.json schema (layout + widgets array)
  - ConfigUpdateMessage dataclass in shared/message_schema.py
  - ProcessManager with bidirectional queues (in_q per widget) and send_config_update
  - WidgetBase with in_queue param and poll_config_update method
  - Compositor.add_slot / remove_slot for dynamic slot management
  - host/config_loader.py: ConfigLoader with QFileSystemWatcher, 100ms debounce, _reconcile
  - WIDGET_REGISTRY + register_widget_type for extensible widget type dispatch
  - config-driven host/main.py replacing hardcoded widget startup

affects: [03-pomodoro-calendar-widgets, 04-notifications-widget, 02-02-control-panel]

# Tech tracking
tech-stack:
  added: [QFileSystemWatcher, QTimer (debounce)]
  patterns:
    - bidirectional-ipc-queues (out_q widget->host, in_q host->widget)
    - config-reconcile-diff (stop removed, start added, CONFIG_UPDATE changed)
    - atomic-replace-watcher-readd (re-add path on fileChanged to survive rename)
    - widget-registry (type_name -> target_fn dispatch table)

key-files:
  created:
    - config.json
    - host/config_loader.py
    - tests/test_config_loader.py
  modified:
    - shared/message_schema.py
    - host/process_manager.py
    - host/main.py
    - widgets/base.py
    - widgets/dummy/widget.py
    - host/compositor.py
    - tests/test_process_manager.py
    - tests/test_dummy_widget.py
    - tests/test_e2e_dummy.py

key-decisions:
  - "WIDGET_REGISTRY as module-level dict lets register_widget_type be called before ConfigLoader construction, enabling main.py to register all types upfront"
  - "in_q maxsize=5 (vs out_q maxsize=10) — config updates are infrequent; small buffer prevents unbounded memory if widget subprocess falls behind"
  - "reconcile: stop before start — prevents transient duplicate widget_id state if a widget ID is repurposed across reload"
  - "QFileSystemWatcher re-add on fileChanged — atomic file replacement (editor write pattern) drops the watched path; re-add is mandatory for hot-reload to survive"

patterns-established:
  - "Bidirectional IPC: out_q (widget->host frames) + in_q (host->widget config updates) stored as 3-tuple in ProcessManager._widgets"
  - "poll_config_update() in WidgetBase render loop: non-blocking get_nowait, returns config dict or None"
  - "Config reconcile pattern: diff old/new widget lists, stop removed first, start added second, CONFIG_UPDATE changed"

requirements-completed: [CFG-01, CFG-02, CFG-03]

# Metrics
duration: 6min
completed: 2026-03-26
---

# Phase 2 Plan 1: Config System Summary

**config.json schema + ConfigLoader with QFileSystemWatcher hot-reload, bidirectional IPC queues, and config-reconcile diff wiring the host to react to runtime config changes**

## Performance

- **Duration:** 6 min (331s)
- **Started:** 2026-03-26T07:26:12Z
- **Completed:** 2026-03-26T07:32:03Z
- **Tasks:** 2/2
- **Files modified:** 10

## Accomplishments
- config.json created with layout.display + widgets array schema (single source of truth for widget layout/settings)
- ProcessManager extended with per-widget inbound queues and send_config_update for host->widget config delivery
- WidgetBase updated with in_queue param and poll_config_update() non-blocking getter
- Compositor gains add_slot/remove_slot for dynamic slot management at runtime
- ConfigLoader implements QFileSystemWatcher watch, 100ms debounce, and reconcile diff logic
- host/main.py replaced hardcoded dummy widget setup with config-driven ConfigLoader + WIDGET_REGISTRY pattern
- 18 unit tests covering all new functionality

## Task Commits

Each task was committed atomically:

1. **Task 1: Config schema, ConfigUpdateMessage, bidirectional queue extension** - `90d336c` (feat)
2. **Task 2: ConfigLoader with QFileSystemWatcher, debounce, reconcile; config-driven main.py** - `47745e9` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD tasks had combined RED+GREEN commits per task_

## Files Created/Modified
- `config.json` - Default config with layout.display (1920x515) and dummy widget entry
- `shared/message_schema.py` - Added ConfigUpdateMessage dataclass alongside FrameData
- `host/process_manager.py` - Bidirectional queues (3-tuple), send_config_update, updated stop_widget drain
- `host/config_loader.py` - ConfigLoader: load(), apply_config(), _on_file_changed(), _do_reload(), _reconcile(); WIDGET_REGISTRY + register_widget_type
- `host/main.py` - Config-driven startup via ConfigLoader; removed hardcoded set_slots/start_widget
- `widgets/base.py` - in_queue param + poll_config_update() method
- `widgets/dummy/widget.py` - Updated to 4-arg signature (widget_id, config, out_queue, in_queue)
- `host/compositor.py` - add_slot() and remove_slot() methods
- `tests/test_config_loader.py` - 18 unit tests (10 Task 1 + 8 Task 2)
- `tests/test_process_manager.py` - Updated worker functions to 4-arg signatures
- `tests/test_dummy_widget.py` - Updated DummyWidget instantiation to 4-arg
- `tests/test_e2e_dummy.py` - Updated subprocess call to 4-arg

## Decisions Made
- WIDGET_REGISTRY as module-level dict enables upfront type registration before ConfigLoader construction
- in_q maxsize=5 keeps config update buffer small (config changes are infrequent)
- reconcile: stop removed widgets before starting added ones, preventing transient widget_id conflicts
- QFileSystemWatcher re-add on every fileChanged event to survive atomic file replacement by editors

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed unpicklable local function in test_process_manager_creates_inbound_queue**
- **Found during:** Task 1 (TDD GREEN phase, running tests)
- **Issue:** Test used a local function `_worker` inside the test body; multiprocessing spawn mode cannot pickle local functions, causing AttributeError
- **Fix:** Replaced local function with import of `_simple_worker` from `tests.test_process_manager` (module-level, picklable)
- **Files modified:** tests/test_config_loader.py
- **Verification:** Test passes after fix
- **Committed in:** 90d336c (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (Rule 1 - bug)
**Impact on plan:** Minor test implementation fix. No scope creep. All functional requirements met exactly as specified.

## Issues Encountered
- Pre-existing: `tests/test_e2e_dummy.py::test_dummy_frame_received` was already failing before this plan (confirmed by git stash verification). Integration test marked `@pytest.mark.integration`; subprocess on Windows spawn path doesn't receive frames in that test harness. Out of scope for this plan — logged to deferred-items.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Config system foundation complete: config.json is the single source of truth
- ConfigLoader watches config.json and reconciles running widgets on change
- WIDGET_REGISTRY ready for Phase 3 widgets (Pomodoro, Calendar) to register their types
- Plan 02-02 (control panel) can write to config.json knowing ConfigLoader will hot-reload it
- All non-integration tests pass (36 tests)

---
*Phase: 02-config-system-control-panel*
*Completed: 2026-03-26*

## Self-Check: PASSED

- config.json: FOUND
- host/config_loader.py: FOUND
- tests/test_config_loader.py: FOUND
- 02-01-SUMMARY.md: FOUND
- commit 90d336c (Task 1): FOUND
- commit 47745e9 (Task 2): FOUND
