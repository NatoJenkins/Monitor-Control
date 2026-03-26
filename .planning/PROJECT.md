# MonitorControl

## What This Is

A modular widget framework that drives a dedicated 1920x515 secondary display (Display 3, positioned below two primary monitors) as a persistent utility bar. A host Python/PyQt6 app owns the display as a borderless always-on-top window, compositing rendered output from individual widget processes that communicate via multiprocessing queues. A separate PyQt6 control panel manages widget layout and per-widget configuration via a config.json the host watches.

## Core Value

Keep productivity tooling off the primary monitors — widgets run persistently in a dedicated display the cursor cannot enter, requiring zero window management from the user.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Host app claims Display 3 as a borderless always-on-top PyQt6 window at 1920x515
- [ ] Windows ClipCursor() prevents the cursor from entering Display 3
- [ ] Widget processes communicate with host via multiprocessing queues (widgets push state/draw data; host renders)
- [ ] Host slots each widget into a defined region of the display and composites them
- [ ] Widgets can be added or swapped without modifying host code
- [ ] PyQt6 control panel reads/writes config.json to configure layout and per-widget settings
- [ ] Dummy widget validates the full host pipeline end-to-end
- [ ] Pomodoro timer widget: start/pause/reset, work/break cycles, visible countdown
- [ ] Calendar widget: styled date and time display (no external calendar integration)
- [ ] Notification interceptor widget: suppress Windows toast popups on primary monitors, surface them in the utility bar on demand

### Out of Scope

- External calendar integration (Google, Outlook, ICS) — date/time display only for v1
- Non-Windows platforms — ClipCursor() and notification hooks are Windows-specific
- GPU-accelerated compositing — standard Qt painting is sufficient at this resolution
- Widget sandboxing / crash isolation beyond process boundaries

## Context

- Display 3 is physically positioned below two primary monitors; it is a landscape strip, not a tall display
- Widget processes are long-running; they own their own state and push updates to the host
- The host is the single renderer — widgets never create their own windows
- The control panel is a separate always-accessible UI (not embedded in Display 3)
- Notification interception on Windows requires hooking into the Windows notification system (likely via win32api / Windows.UI.Notifications COM interface or a toast listener)

## Constraints

- **Platform**: Windows only — ClipCursor(), notification APIs, and multi-monitor positioning assumptions are Windows-specific
- **Display**: Hardcoded target of Display 3 at 1920x515 for v1; configurable display selection deferred
- **Language**: Python throughout (PyQt6 for host and control panel)
- **IPC**: multiprocessing.Queue only — no sockets, shared memory, or external message brokers
- **Build order**: Host + dummy widget → Pomodoro → Calendar → Notification interceptor

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Host renders, widgets push data | Keeps widget processes simple; single rendering context avoids Z-order/transparency issues with multiple windows | — Pending |
| ClipCursor() for cursor lockout | Simplest reliable Win32 approach; no third-party driver needed | — Pending |
| Separate control panel process | Keeps configuration UI decoupled from the always-on display; avoids restarting the host to reconfigure | — Pending |
| config.json as config store | Simple, human-readable, easy to hand-edit; host watches for file changes | — Pending |

---
*Last updated: 2026-03-26 after initialization*
