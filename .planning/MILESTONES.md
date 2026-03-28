# Milestones

## v1.2 Configurable Colors (Shipped: 2026-03-28)

**Phases completed:** 4 phases, 6 plans, 0 tasks

**Key accomplishments:**
- (none recorded)

---

## v1.1 Startup & Distribution (Shipped: 2026-03-27)

**Phases completed:** 3 phases, 3 plans, 0 tasks

**Key accomplishments:**
- (none recorded)

---

## v1.0 MVP (Shipped: 2026-03-27)

**Phases:** 1–4 | **Plans:** 9 | **Timeline:** 2026-03-26 → 2026-03-27
**Code:** ~4,578 Python LOC across 95 files
**Git range:** feat(01-01) → fix(04-02)

**Key accomplishments:**
1. PyQt6 host process claims Display 3 as a borderless always-on-top 1920×515 window with ClipCursor() enforcement, WTS session-unlock recovery, and WM_DISPLAYCHANGE re-apply
2. IPC pipeline: WidgetBase, ProcessManager, QueueDrainTimer, and Compositor enable zero-Qt widget subprocesses pushing RGBA frames via non-blocking multiprocessing.Queue at 50ms drain rate
3. config.json hot-reload system with QFileSystemWatcher atomic-replace handling, 100ms debounce, and live widget reconciliation (start/stop/CONFIG_UPDATE) without host restarts
4. Pomodoro timer widget with full IDLE→WORK→SHORT_BREAK→LONG_BREAK state machine, configurable durations, Pillow rendering, and command-file IPC for Start/Pause/Reset from the control panel
5. Calendar widget showing locale-aware day/date and 12h/24h configurable time at 1Hz via Pillow
6. WinRT notification interceptor surfacing Windows toast title/body/app name with auto-dismiss (30s default); backed by a hardware-validated WinRT spike confirming asyncio/spawn subprocess compatibility

**Delivered:** A fully operational 1920×515 utility bar on Display 3 with Pomodoro, Calendar, and Notification widgets — all config-driven, hot-reloadable, and cursor-lockout safe.

**Test coverage:** 88+ automated tests pass across all phases.

### Known Gaps

- **Phase 1 VERIFICATION.md missing**: No formal `01-VERIFICATION.md` was created. All Phase 1 requirements (HOST-01..05, IPC-01..04) are confirmed wired in code by integration checker and hardware-verified in 01-03-SUMMARY.md.
- **IPC-03 spec deviation**: `ProcessManager.stop_widget` uses `proc.terminate()` only (no drain-before-join, no 5s kill fallback). Deliberate design to avoid Qt main thread deadlock on Windows. IPC-03 requirement language needs amendment in v1.x.

---

