# Feature Research

**Domain:** Desktop widget bar / persistent utility display framework (Windows, Python/PyQt6)
**Researched:** 2026-03-26
**Confidence:** MEDIUM-HIGH (core widget patterns HIGH from ecosystem evidence; notification interception MEDIUM from API docs; Python multiprocess IPC patterns MEDIUM from community sources)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features the product must have. Missing any of these means the host app or a widget feels broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Persistent always-on-top window | The entire value proposition is "off primary monitors but always visible." If the bar can be obscured or dismissed it is just another app window. | LOW | PyQt6 `Qt.WindowStaysOnTopHint` + `Qt.FramelessWindowHint`. Already in project requirements. |
| Deterministic display claiming | Bar must own its target display on startup and recover if the display disconnects/reconnects (e.g., sleep/wake). | MEDIUM | Use `QScreen` enumeration + watch `QApplication.screenAdded/screenRemoved` signals. Display 3 at 1920x515 is hardcoded for v1. |
| Cursor exclusion from display | Without this, the cursor accidentally enters the bar display constantly on a below-monitors layout. | MEDIUM | Win32 `ClipCursor()` to a RECT that excludes Display 3. Already in project requirements. |
| Widget renders without flickering | Any visible flicker or partial-frame tear makes the bar feel broken. Users of Rainmeter, YASB, and similar tools cite this as an immediate dealbreaker. | LOW | Double-buffer via Qt's default paint system. Composite to a single `QWidget` surface; do not use per-widget top-level windows. |
| Config survives restart | Settings and layout must persist. Users of Rainmeter/YASB expect to configure once and never reconfigure after reboot. | LOW | `config.json` read on host startup. Already in project requirements. |
| Widget start/stop without host restart | Users expect to toggle a widget or change its config without rebooting the whole bar. Rainmeter users do this per-skin; YASB does this via config reload. | MEDIUM | Host watches `config.json` for changes via `watchdog` or a polling timer. Spawns/terminates widget subprocess on delta. |
| Visible clock: time and date | Every productivity bar (YASB, Rainmeter Sonder/Monterey, Windows 11 widgets, macOS menu bar) includes a clock. Its absence is immediately noticed. | LOW | Calendar widget: local system clock, formatted string, updates every second or minute depending on seconds display preference. |
| Pomodoro: start / pause / reset | The three canonical controls for any Pomodoro implementation. Zapier, Reclaim, Pomofocus all have these. Missing any one feels broken. | LOW | Widget-internal state machine. Control signals sent from control panel over queue. |
| Pomodoro: work/break cycle progression | Auto-advancing from work → short break → work → long break is the core mechanic. Manual-only cycle control is not acceptable to Pomodoro users. | MEDIUM | Widget tracks cycle count, advances state at countdown zero, pushes new state to host render. |
| Pomodoro: visible countdown | Users must see the current phase and time remaining without ambiguity. This is the only output the widget needs to provide. | LOW | Formatted `MM:SS` string, phase label ("Focus" / "Short Break" / "Long Break"), rendered via host. |
| Notification display area | The notification interceptor must surface intercepted toasts somewhere. An area in the bar that shows notification content is the expected surface. | MEDIUM | Widget renders notification title + body + app icon. Oldest or queue-ordered display. |
| Control panel to configure layout | Rainmeter's Manage dialog, YASB's config.yaml, Stream Deck's drag-and-drop — all provide a separate UI for layout. Direct editing of raw JSON is not ergonomic. | HIGH | Separate PyQt6 process. Reads/writes `config.json`. Host watches for file changes. Already in project requirements. |
| Widget process isolation | A crashing widget must not crash the host bar. Rainmeter's monolithic DLL approach has known stability issues; YASB and WidgetPlatform both moved to per-widget processes for this reason. | MEDIUM | Python `multiprocessing.Process`. Host detects dead queue and marks widget as crashed. Already in project requirements. |

---

### Differentiators (Competitive Advantage)

Features that go beyond what similar products do, directly matching the project's core value (keeping productivity tooling off primary monitors).

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Dedicated display as a permanent canvas | Most alternatives (Rainmeter, YASB, Windows Widgets) overlay the primary desktop. A dedicated physical display below two primaries with cursor lockout eliminates Z-order fights and accidental interactions entirely. | HIGH | Hardcoded 1920x515 for v1. The cursor lockout via `ClipCursor()` is what makes this genuinely different from a floating taskbar. |
| Notification interception and redirect | Instead of suppressing toasts or letting them interrupt workflow, the bar captures them and surfaces them in a dedicated notification widget. macOS Notification Center is closest analog but is pull-based. Windows Action Center is passive. This is active interception + display. | HIGH | Requires `Windows.UI.Notifications` WinRT via `winsdk` or `pythonnet` + `IUserNotificationListener`. Note: `SuppressPopup` is a sender-side API; intercepting third-party app toasts requires `IUserNotificationListener2` COM interface. This is the hardest feature technically. |
| Host renders all widgets, widgets push data | Eliminates per-widget Z-order, transparency, and always-on-top problems. Single rendering context means pixel-perfect compositing. Stream Deck uses a similar model (host display, plugin data). | HIGH | The project's core architectural choice. Differentiates from Rainmeter (each skin is an independent window) and YASB (each widget is a Qt widget in the bar's process). |
| Config hot-reload without restart | YASB has this; Rainmeter requires skin reload. True hot-reload (watchdog detects config.json change → host reconciles running widgets without tearing down bar) is a strong developer/power-user UX. | MEDIUM | `watchdog` library + diff of old/new config to determine which widgets to stop, start, or reconfigure. Do not restart the host process. |
| Pomodoro: configurable work/break durations | Most Pomodoro timers default to 25/5/15 minutes but make these configurable. The control panel sets these per-widget in config.json. | LOW | Config keys: `work_minutes`, `short_break_minutes`, `long_break_minutes`, `cycles_before_long`. Pushed to widget process at startup or on reload. |
| Pomodoro: audio cue at phase transition | Pomofocus, Focus Keeper, and GNOME Pomodoro all play a sound at transition. Silent-only timers are considered incomplete by Pomodoro users. | LOW | `playsound` or Qt's `QSoundEffect`. A single short WAV/OGG bundled with the widget. The host does NOT play sound; the widget process does (audio does not require a render window). |
| Notification queue with dismiss | Surface multiple intercepted notifications, allow one-by-one or all-clear dismiss. Closest analog: Action Center's notification list, but inline in the bar. | MEDIUM | Widget holds a deque of notification payloads. Host renders the top-N depending on available height. Dismiss sends a signal back to the widget process. |
| Graceful widget crash recovery | If a widget process dies, the host should: mark the slot as "crashed," display a visual indicator, and provide a restart action from the control panel. Rainmeter does not do this; it just goes blank. | MEDIUM | Host polls queue liveness (heartbeat message or process `.is_alive()`). On crash: render placeholder, log to file, expose restart button in control panel. |

---

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Per-widget windows (each widget owns a top-level Qt window) | Simpler to implement initially; each widget draws itself. | Z-order collisions, transparency artifacts, cannot guarantee compositing order, defeats the purpose of a unified display. Rainmeter suffers from this — skins fight for Z position. | Host renders everything into a single QWidget surface. Widgets push draw data via queue. |
| GPU-accelerated compositor / OpenGL compositing | Users ask for smooth animations and effects. | Overkill at 1920x515. Adds significant complexity (context sharing, sync), GPU driver dependency, makes Linux/macOS porting harder if ever desired. Standard Qt painter is ample for this resolution. | Qt's default double-buffered paint system. Already in project scope notes as out-of-scope. |
| External calendar integration (Google, Outlook, ICS) | Users want their calendar events in the bar. | OAuth flows, token refresh, rate limits, network dependency, error handling surface — large scope for v1. Distraction from validating the core host/widget pipeline. | v1: styled date/time display only. Defer calendar integration to post-validation. Already out-of-scope in PROJECT.md. |
| Widget sandboxing beyond process boundaries | Security-conscious users may want widgets to have no filesystem or network access. | Requires OS-level sandboxing (AppContainer, seccomp, etc.) — major complexity with no immediate user-facing payoff for a single-user local tool. | Process isolation (already designed) provides crash containment without full sandboxing. Document the limitation. |
| In-bar widget configuration UI | Clicks or touch targets inside the display surface to configure widgets inline. | The bar display explicitly has cursor lockout (`ClipCursor()`). Users cannot click inside Display 3. Any in-bar interaction model directly contradicts the design. | All configuration goes through the separate control panel process. |
| Real-time system resource monitoring widgets (CPU, GPU, RAM, network) | Rainmeter/YASB prominently feature these; users will expect them. | High polling frequency (1s interval) is the #1 cause of Windows Widgets high CPU usage complaints. Out of scope for v1; scope creep risk. | Build the plugin framework correctly in v1 so these can be added as third-party widgets later without modifying the host. |
| Cross-platform support (macOS, Linux) | Python/PyQt6 is nominally cross-platform. | ClipCursor() is Win32-only. Multi-monitor positioning below two monitors assumes Windows display enumeration. Notification interception APIs are Windows-specific. Supporting other platforms requires rearchitecting the cursor lockout and notification subsystems. | Windows-only for v1. State this constraint explicitly. Already in project constraints. |
| Live widget drag-and-drop layout | Rainmeter lets users drag skins anywhere. Intuitive but hard to implement given cursor lockout. | You cannot drag widgets in Display 3 because the cursor cannot enter it. Even if cursor lockout were lifted, drag-and-drop within a headless composited surface requires hit-testing and layout engine work. | Control panel defines layout regions by name (e.g., "left", "center", "right", "full"). Positions are configured, not dragged. |
| Notification sound passthrough | Playing the original notification's sound when intercepting toasts. | Windows notification sounds are played by the notification platform before the interception hook fires. Replaying them separately risks double-sound or wrong-sound issues. | Display the notification visually in the bar. Optionally play a single generic "new notification" chime from the widget process. |

---

## Feature Dependencies

```
[Host window + display claiming]
    └──required by──> [All widget rendering]
                          └──required by──> [Pomodoro widget]
                          └──required by──> [Calendar widget]
                          └──required by──> [Notification widget]

[Widget process lifecycle (spawn/kill/monitor)]
    └──required by──> [Widget hot-swap without host restart]
    └──required by──> [Widget crash recovery]

[multiprocessing.Queue IPC]
    └──required by──> [Widget data → host render pipeline]
    └──required by──> [Control signals → widget (Pomodoro start/pause/reset)]
    └──required by──> [Notification payloads → notification widget]

[config.json schema + file watcher]
    └──required by──> [Control panel writes → host reads]
    └──required by──> [Config hot-reload without restart]
    └──required by──> [Per-widget settings (Pomodoro durations, clock format)]

[Control panel process]
    └──required by──> [Widget layout configuration]
    └──required by──> [Per-widget settings]
    └──required by──> [Widget crash recovery restart action]

[ClipCursor() cursor lockout]
    └──conflicts with──> [In-bar widget configuration UI]
    └──conflicts with──> [Live drag-and-drop layout]

[Windows IUserNotificationListener2 COM]
    └──required by──> [Notification interception]
    └──required by──> [Notification widget rendering]
    └──blocks on──> [pythonnet or winsdk Python bindings working reliably for this COM interface]

[Notification interception]
    └──enhances──> [Notification widget display]
    └──requires──> [Notification widget] (somewhere to display captured toasts)

[Pomodoro state machine]
    └──required by──> [Pomodoro countdown display]
    └──required by──> [Work/break cycle progression]
    └──enhanced by──> [Pomodoro audio cue at phase transition]
    └──configured by──> [config.json per-widget settings]
```

### Dependency Notes

- **Host window required by all widgets:** The host must be running and have claimed the display before any widget can render. Dummy widget validates this pipeline before real widgets are built.
- **multiprocessing.Queue IPC is bidirectional:** Widgets push render data up to host; host (or control panel via host) pushes control signals down to widgets. Design the queue protocol to handle both directions from the start.
- **Config hot-reload requires schema stability:** If config.json schema changes between versions, the file watcher reload logic must handle schema migration or the user's existing config breaks silently. Define the schema carefully before building hot-reload.
- **Notification interception is technically independent:** The IUserNotificationListener2 COM interface can be prototyped without the rest of the host pipeline. However, it feeds the notification widget, so the widget's render format must be defined before the interceptor is finalized.
- **ClipCursor conflicts with in-bar interaction:** This is the most important anti-feature to enforce. Any feature request that assumes the user can click inside Display 3 is architecturally impossible given the cursor lockout.

---

## MVP Definition

### Launch With (v1)

Minimum viable product — validates the core host/widget pipeline with real, useful widgets.

- [ ] Host process claims Display 3 (1920x515), borderless, always-on-top — validates the display ownership model
- [ ] ClipCursor() prevents cursor from entering Display 3 — validates the core UX premise
- [ ] Dummy widget end-to-end: process spawned, pushes colored rect via queue, host renders it — validates full IPC + render pipeline
- [ ] Widget process isolation: dummy widget crash does not crash host — validates stability model
- [ ] config.json watched and hot-reloaded: add/remove/swap widgets without restarting host — validates the lifecycle model
- [ ] Control panel PyQt6 process: reads/writes config.json for layout and per-widget settings — validates configuration UX
- [ ] Pomodoro widget: start/pause/reset, work/break cycle auto-advance, MM:SS countdown, phase label, configurable durations — validates real widget development
- [ ] Calendar widget: styled date and time, local clock, no external integrations — validates simplest real widget
- [ ] Notification interceptor widget: captures Windows toast popups from other apps, displays title + body in bar, dismiss action — validates the hardest feature

### Add After Validation (v1.x)

Features to add once the core pipeline is proven with real usage.

- [ ] Pomodoro audio cue at phase transition — add when users report the silent transition is disorienting
- [ ] Widget crash recovery UI: visual "crashed" placeholder in the host + restart button in control panel — add if widget instability is observed in daily use
- [ ] Notification queue: display multiple intercepted notifications in order, not just the latest — add if single-notification display proves insufficient
- [ ] Clock seconds display toggle — add if users want sub-minute precision

### Future Consideration (v2+)

Features to defer until product-market fit and core pipeline stability are established.

- [ ] System resource widgets (CPU, RAM, GPU, network) — high polling CPU cost; defer until plugin framework is proven stable
- [ ] Additional widget types (weather, media player control, notes) — defer; build the plugin framework first
- [ ] Configurable display selection (not hardcoded to Display 3) — defer; single-display assumption simplifies v1 enormously
- [ ] External calendar integration (Google, Outlook, ICS) — explicitly deferred per PROJECT.md; large scope

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Host window + display claiming | HIGH | LOW | P1 |
| ClipCursor cursor lockout | HIGH | LOW | P1 |
| Dummy widget validates pipeline | HIGH | LOW | P1 |
| Widget process isolation | HIGH | MEDIUM | P1 |
| config.json hot-reload | HIGH | MEDIUM | P1 |
| Pomodoro timer (full cycle) | HIGH | MEDIUM | P1 |
| Calendar / clock widget | HIGH | LOW | P1 |
| Notification interception + display | HIGH | HIGH | P1 |
| Control panel PyQt6 | HIGH | HIGH | P1 |
| Widget crash recovery indicator | MEDIUM | MEDIUM | P2 |
| Pomodoro audio cue | MEDIUM | LOW | P2 |
| Notification queue (multi-toast) | MEDIUM | MEDIUM | P2 |
| Pomodoro configurable durations | MEDIUM | LOW | P2 |
| Clock seconds toggle | LOW | LOW | P3 |
| System resource widgets | MEDIUM | HIGH | P3 |
| Configurable display selection | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1 launch — without these the product cannot validate its core premise
- P2: Should have — add in v1.x after core pipeline is stable
- P3: Nice to have — future consideration

---

## Competitor Feature Analysis

| Feature | Rainmeter | YASB | Windows 11 Widgets | Our Approach |
|---------|-----------|------|--------------------|--------------|
| Rendering model | Per-skin independent windows; Z-order fights | Single bar Qt process; all widgets in same process | WebView2-hosted cards in a panel | Host renders all widgets; widgets push data |
| Widget isolation | None — one skin crash can destabilize others | None — all widgets in host process | OS-level isolation (separate WebView2) | Per-process via multiprocessing; crash does not kill host |
| Config format | INI files per-skin | YAML + CSS | JSON (cloud-backed, Microsoft account) | config.json; human-readable, no account needed |
| Config hot-reload | Per-skin refresh | Yes (file watcher) | Not user-configurable | Yes (watchdog on config.json) |
| Multi-monitor | Yes, skins float anywhere | Yes, bar assigned per screen | Primary only | Display 3 hardcoded; single bar |
| Cursor lockout | None | None | None | Win32 ClipCursor(); unique to this project |
| Notification interception | None | None | None (separate Action Center) | IUserNotificationListener2 redirect to bar |
| Pomodoro | Community skins only | No built-in | No | First-class built-in widget |
| Control surface | Right-click context menus per skin | Config YAML editing + restart | Mouse interaction in widget panel | Separate PyQt6 control panel process |
| Extensibility | DLL plugins (C++/C#) | Python widget classes | Third-party providers (web service) | Python multiprocessing widget processes |

---

## Domain-Specific Patterns

### Widget Lifecycle States

Every widget process should cycle through defined states so the host can render the appropriate visual for each:

```
STARTING → RUNNING → PAUSED (user-initiated) → RUNNING
RUNNING → CRASHED (exception in widget process)
RUNNING → STOPPED (user removes widget from config)
CRASHED → RESTARTING (user triggers restart from control panel)
```

The host renders: STARTING = loading placeholder, RUNNING = latest frame from queue, PAUSED = last frame (dimmed), CRASHED = error indicator, STOPPED = empty slot.

### IPC Queue Message Protocol

All queue messages should carry a type field so the host can dispatch without inspecting payload shape:

- `RENDER_FRAME` — widget → host: contains draw data (text strings, colors, layout hints)
- `HEARTBEAT` — widget → host: proves the process is alive; host uses absence to detect crash
- `CONTROL` — host/control panel → widget: carries action (e.g., `pomodoro:start`, `pomodoro:reset`)
- `CONFIG_UPDATE` — host → widget: delivers new per-widget config after hot-reload

### Pomodoro State Machine

```
IDLE ──start──> WORK (countdown from work_minutes)
WORK ──zero──> SHORT_BREAK (if cycle_count < cycles_before_long)
WORK ──zero──> LONG_BREAK (if cycle_count == cycles_before_long)
SHORT_BREAK ──zero──> WORK (cycle_count += 1)
LONG_BREAK ──zero──> WORK (cycle_count reset to 0)
ANY ──pause──> PAUSED (countdown frozen)
PAUSED ──resume──> (previous state, countdown resumed)
ANY ──reset──> IDLE
```

The widget owns this state machine internally. The host receives only render data (phase name, MM:SS string, cycle count). The control panel sends control actions via queue.

### Notification Interception Technical Notes

Windows provides two Python-accessible paths to intercept toasts from other apps:

1. `Windows.UI.Notifications.Management.UserNotificationListener` via `winsdk` package — requires the user to grant "notification access" permission. Works in Python via `asyncio` + WinRT bindings. This is the recommended path. [MEDIUM confidence — `winsdk` exposes this API but real-world Python reliability needs prototype validation]

2. `pythonnet` + `Windows.UI.Notifications` COM interfaces — more flexible but more complex to set up correctly.

Neither approach lets a third-party app suppress a toast before it appears (that is only possible for the originating app via `SuppressPopup`). The interception model is: toast appears AND is captured; the bar displays it. The suppression of the original popup requires additional steps (e.g., hooking the notification platform at a lower level) and is likely out-of-scope for v1. **Plan v1 as "display in bar in addition to system toast," not "replace system toast."**

### Clock/Date Display Conventions

Users expect the following based on YASB, Rainmeter Sonder/Monterey, and Windows widget patterns:
- 12h or 24h toggle (configurable per user locale preference)
- Day of week display (e.g., "Thursday")
- Full date (e.g., "March 26, 2026" or "26/03/2026" depending on locale)
- Seconds optional (default off — updating every second at 1920x515 causes unnecessary repaints)
- Time updates on a 1-second timer; date updates on a 1-minute timer (or detect date change)

### Config Hot-Reload Pattern

The host uses `watchdog` to watch `config.json` for modification events. On change:
1. Load new config, validate schema.
2. Diff old config vs new config.
3. For widgets in old but not new: send `STOP` signal, terminate process.
4. For widgets in new but not old: spawn new process.
5. For widgets in both with changed per-widget config: send `CONFIG_UPDATE` via queue.
6. Update host layout regions to match new config.
7. Do NOT restart the host process or the bar window.

---

## Sources

- [Rainmeter Documentation — Skins, Plugins, Layout](https://docs.rainmeter.net/manual/)
- [YASB (Yet Another Status Bar) — GitHub amnweb/yasb](https://github.com/amnweb/yasb)
- [YASB System Architecture — DeepWiki](https://deepwiki.com/amnweb/yasb/7-system-architecture)
- [YASB Configuration — DeepWiki](https://deepwiki.com/amnweb/yasb/3-configuration)
- [YASB Windows Forum Overview](https://windowsforum.com/threads/yasb-a-custom-top-status-bar-for-windows-power-users.401472/)
- [Elgato Stream Deck Plugin System](https://help.elgato.com/hc/en-us/articles/360028232451-Elgato-Stream-Deck-Plugins)
- [Windows 11 Widgets — Microsoft Support](https://support.microsoft.com/en-us/windows/stay-up-to-date-with-widgets-in-windows-7ba79aaa-dac6-4687-b460-ad16a06be6e4)
- [ToastNotification.SuppressPopup — Microsoft Learn](https://learn.microsoft.com/en-us/uwp/api/windows.ui.notifications.toastnotification.suppresspopup?view=winrt-26100)
- [Windows-Toasts Python library](https://pypi.org/project/Windows-Toasts/)
- [winotify PyPI](https://pypi.org/project/winotify/)
- [PyQt6 Multithreading with QThreadPool — pythonguis.com](https://www.pythonguis.com/tutorials/multithreading-pyqt6-applications-qthreadpool/)
- [qt-multiprocessing PyPI](https://pypi.org/project/qt-multiprocessing/)
- [Top Pomodoro Timer Apps — Reclaim/Zapier analysis](https://reclaim.ai/blog/best-pomodoro-timer-apps)
- [How to Build Config Hot-Reload in Python — OneUptime](https://oneuptime.com/blog/post/2026-01-22-config-hot-reload-python/view)
- [PowerToys Always On Top — Microsoft Learn](https://learn.microsoft.com/en-us/windows/powertoys/always-on-top)
- [YASB CPU/system widget update interval patterns](https://deepwiki.com/amnweb/yasb/6.1-status-widgets)
- [Rainmeter arranging skins / layout](https://docs.rainmeter.net/manual/arranging-skins/)

---
*Feature research for: Desktop widget bar / utility display framework (MonitorControl)*
*Researched: 2026-03-26*
