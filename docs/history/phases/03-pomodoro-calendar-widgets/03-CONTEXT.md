# Phase 3: Pomodoro + Calendar Widgets - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Two real widgets — Pomodoro timer and Calendar display — running as isolated subprocesses implementing `WidgetBase`. Each renders its content via Pillow to RGBA bytes and pushes `FrameData` to the host queue. Phase 3 also extends the control panel with Pomodoro control buttons and additional per-widget settings. No external calendar integration; date/time display only.

</domain>

<decisions>
## Implementation Decisions

### Slot Geometry
- Display carve-up is equal thirds (1920 / 3 = 640px each), all full 515px height:
  - Pomodoro: `x=0, y=0, width=640, height=515`
  - Calendar: `x=640, y=0, width=640, height=515`
  - Notification slot (Phase 4, reserved): `x=1280, y=0, width=640, height=515`
- The dummy widget is removed from `config.json`; Phase 3 replaces it with the two real widget entries

### Visual Style
- Background color: dark/near-black — `#1a1a2e` (or similar; Claude has discretion on exact shade)
- Text layout within each slot: centered both horizontally and vertically
- Font approach: bundle three TTF files with the widget package (no system-font lookup at runtime):
  - **Inter** — clean readable sans-serif (default for both widgets)
  - **Digital-7** — LCD-style digital clock aesthetic
  - **Share Tech Mono** — cyber monospace feel
- Each widget has its own font setting in config.json and in the control panel (independent selectors)

### Pomodoro Visual Design
- Accent color per state (text/countdown color changes by state):
  - WORK → red (default)
  - SHORT_BREAK → green (default)
  - LONG_BREAK → blue (default)
- All three accent colors are configurable in the control panel (Pomodoro tab)
- Config keys: `work_accent_color`, `short_break_accent_color`, `long_break_accent_color` (hex strings)
- IDLE state displays: phase label "Focus" + full work duration countdown frozen (e.g. "25:00") — same visual as WORK state but timer is not running

### Pomodoro Controls in the Control Panel
- Add a **"Controls" QGroupBox** above the existing "Pomodoro Durations" group in the Pomodoro tab
- Three buttons in a row: **[Start]  [Pause]  [Reset]**
- Keyboard shortcuts (configurable in control panel settings, defaults):
  - Start → `Ctrl+S`
  - Pause → `Ctrl+P`
  - Reset → `Ctrl+R`
- Shortcut key bindings are stored in config.json under a `shortcuts` section and editable in the control panel
- Signal delivery mechanism: **dedicated command file** (`pomodoro_command.json` in the same directory as `config.json`)
  - Control panel writes `{"cmd": "start" | "pause" | "reset"}` atomically (temp + os.replace)
  - Host watches this file via a second `QFileSystemWatcher`; on change, reads the command, forwards to Pomodoro widget via `in_queue` as a new `ControlSignal` message type, then deletes the file
  - ControlSignal is a new dataclass in `shared/message_schema.py`: `widget_id: str, command: str`

### Calendar Visual Design
- Font: per-widget font selector (same three bundled options), default Inter
- Config key: `font` in calendar widget settings
- Seconds: not displayed in v1 (deferred as PLSH-04)
- Date format: locale-aware full date (day of week + full date), time in 12h or 24h per config

### config.json Extensions
Phase 3 adds to `config.json`:
```json
{
  "widgets": [
    {
      "id": "pomodoro",
      "type": "pomodoro",
      "x": 0, "y": 0, "width": 640, "height": 515,
      "settings": {
        "work_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "cycles_before_long_break": 4,
        "font": "Inter",
        "work_accent_color": "#ff4444",
        "short_break_accent_color": "#44ff44",
        "long_break_accent_color": "#4488ff"
      }
    },
    {
      "id": "calendar",
      "type": "calendar",
      "x": 640, "y": 0, "width": 640, "height": 515,
      "settings": {
        "clock_format": "24h",
        "font": "Inter"
      }
    }
  ],
  "shortcuts": {
    "pomodoro_start": "Ctrl+S",
    "pomodoro_pause": "Ctrl+P",
    "pomodoro_reset": "Ctrl+R"
  }
}
```

### Claude's Discretion
- Exact dark background hex value (#1a1a2e or similar near-black)
- Font sizes for label vs countdown/time (should be legible on the 640x515 slot)
- Pillow rendering details (ImageDraw, textbbox centering math)
- QFileSystemWatcher setup for `pomodoro_command.json`
- ControlSignal message dispatch logic in host
- Pomodoro state machine tick interval (1-second sleep loop vs threading.Timer)
- Test strategy for state machine and rendering pipeline

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Widget contract and IPC
- `widgets/base.py` — WidgetBase ABC: `run()`, `out_queue`, `in_queue`, `poll_config_update()`; contract every widget subprocess must implement
- `widgets/dummy/widget.py` — Reference implementation: non-blocking put, queue.Full guard, frame push loop pattern
- `shared/message_schema.py` — FrameData (rgba_bytes), ConfigUpdateMessage; Phase 3 adds ControlSignal here

### Host integration
- `host/config_loader.py` — WIDGET_REGISTRY (register_widget_type), reconcile logic (stop→start→CONFIG_UPDATE); new widget types must be registered before ConfigLoader construction
- `host/process_manager.py` — start_widget, send_config_update, in_queue; ControlSignal delivery goes here
- `host/main.py` — Entry point; where new widget types are registered and second file watcher is set up

### Control panel extension
- `control_panel/main_window.py` — Existing Pomodoro tab (duration settings) and Calendar tab (clock format) to be extended; `_update_widget_settings` does NOT auto-create widget entries (decision #19 in STATE.md)
- `control_panel/config_io.py` — atomic_write_config pattern; same pattern used for pomodoro_command.json writes

### Config structure
- `config.json` — Current structure (dummy widget); Phase 3 replaces dummy with pomodoro + calendar entries per the schema in decisions above

### Key architectural constraints (from ROADMAP.md confirmed research)
- Widget processes MUST NOT import PyQt6 — Pillow is the off-screen renderer; crashes on Windows spawn with Qt context in subprocess
- All widget `queue.put()` calls MUST be `block=False` with `queue.Full` guard; no blocking puts in steady state

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `WidgetBase` (`widgets/base.py`): provides `widget_id`, `config`, `out_queue`, `in_queue`, `poll_config_update()` — Pomodoro and Calendar extend this directly
- `FrameData` (`shared/message_schema.py`): already the correct push format; width/height/rgba_bytes
- `ConfigUpdateMessage` (`shared/message_schema.py`): used for duration/format config updates; pattern extends to ControlSignal
- `ProcessManager.send_config_update()`: already sends messages to in_queue; same path used to forward ControlSignal
- `atomic_write_config` (`control_panel/config_io.py`): use this pattern for writing `pomodoro_command.json`

### Established Patterns
- Frame push loop: `while True: put(block=False) / except queue.Full: pass / time.sleep(interval)` — DummyWidget is the reference
- Config update handling: `poll_config_update()` in the run loop → apply new config dict on return
- Widget registration: `register_widget_type("pomodoro", run_pomodoro_widget)` called in `host/main.py` before ConfigLoader
- Subprocess entry point: module-level `run_<widget>(widget_id, config, out_q, in_q)` function

### Integration Points
- `host/main.py`: add `register_widget_type` calls for "pomodoro" and "calendar" before ConfigLoader construction
- `config.json`: replace dummy widget entry with pomodoro + calendar entries (+ shortcuts section)
- `control_panel/main_window.py`: extend `_build_pomodoro_tab()` and `_build_calendar_tab()`, add `_load_values()`/`_collect_config()` coverage for new settings (font, accent colors, shortcuts)
- `shared/message_schema.py`: add `ControlSignal` dataclass

</code_context>

<specifics>
## Specific Ideas

- "Let me select percentages, not pixels" → decided equal thirds = 640px per slot, planning for Phase 4's notification widget at x=1280
- Keyboard shortcuts configurable in control panel settings (not hardcoded) with defaults Ctrl+S/P/R
- Each widget has its own font selector (not shared) — Pomodoro and Calendar can have different fonts
- Font selector should offer: Inter (default), Digital-7 (LCD), Share Tech Mono (cyber mono)
- Command file approach for Pomodoro signals keeps config.json clean of transient commands

</specifics>

<deferred>
## Deferred Ideas

- Seconds display on Calendar — already tracked as PLSH-04 (v2), explicitly deferred
- Configurable display selection (not hardcoded to Display 3) — EXT-02 (v2)

</deferred>

---

*Phase: 03-pomodoro-calendar-widgets*
*Context gathered: 2026-03-26*
