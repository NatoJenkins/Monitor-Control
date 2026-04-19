# Architecture Research

**Domain:** Python desktop widget bar — configurable color system integration
**Researched:** 2026-03-27
**Confidence:** HIGH (all findings derived from direct inspection of existing codebase)

---

## Context: What Is Already Built

This document covers v1.2 integration architecture only. The existing system (v1.1) is:

- **Host process** (`host/`): PyQt6 app. `HostWindow.paintEvent` fills the background with a hardcoded `QColor("#000000")` then calls `Compositor.paint()`, which blits RGBA frames from widget subprocesses. Background ownership is split: `HostWindow` fills black, widgets paint their own background color into their RGBA frames.
- **Widget subprocesses** (`widgets/`): Long-running, Pillow-only (no PyQt6). Each widget calls `Image.new("RGBA", (W, H), self._bg_color)` at the start of every `render_frame()`, painting a solid `(26, 26, 46, 255)` background before drawing content. Background color is hardcoded in widget `__init__`.
- **Control panel** (`control_panel/`): Separate PyQt6 process. Sole writer of `config.json`. `_collect_config()` builds the full config dict; `_update_widget_settings()` patches the `settings` block of each widget entry. Color fields for Pomodoro are already in the pipeline as `QLineEdit` hex fields.
- **config.json**: Top-level keys are `layout`, `widgets`, `shortcuts`. Widget color settings live inside `widgets[n].settings`. There is no top-level `bg_color` key yet.
- **Hot-reload path**: `QFileSystemWatcher` → `ConfigLoader._do_reload()` → `_reconcile()` → `ProcessManager.send_config_update(wid, widget_cfg)` → `ConfigUpdateMessage` on widget's `in_queue` → widget `poll_config_update()` in render loop.

---

## System Overview: v1.2 Color Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  CONTROL PANEL (PyQt6 process)                                       │
│                                                                       │
│  Layout tab:   ColorPickerWidget  ──► bg_color (top-level in config) │
│  Calendar tab: ColorPickerWidget  ──► time_color, date_color         │
│  Pomodoro tab: ColorPickerWidget  ──► work/short_break/long_break    │
│                   (replaces QLineEdit hex fields)                     │
│                                                                       │
│  _collect_config() writes ALL color values into config dict          │
│  atomic_write_config() → config.json                                 │
└───────────────────────────┬─────────────────────────────────────────┘
                             │ file change
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  config.json  (shared on disk, %LOCALAPPDATA%\MonitorControl\)       │
│                                                                       │
│  {                                                                    │
│    "bg_color": "#000000",          ← NEW top-level key               │
│    "layout": { ... },                                                 │
│    "widgets": [                                                       │
│      { "type": "calendar",                                            │
│        "settings": {                                                  │
│          "time_color": "#ffffff",  ← NEW in calendar settings        │
│          "date_color": "#dcdcdc",  ← NEW in calendar settings        │
│          ...                                                          │
│        }                                                              │
│      },                                                               │
│      { "type": "pomodoro",                                            │
│        "settings": {                                                  │
│          "work_accent_color": "#ff4444",  ← EXISTING, already works  │
│          ...                                                          │
│        }                                                              │
│      }                                                                │
│    ]                                                                  │
│  }                                                                    │
└───────────────────────────┬─────────────────────────────────────────┘
                             │ QFileSystemWatcher hot-reload
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  HOST PROCESS (PyQt6)                                                 │
│                                                                       │
│  ConfigLoader._do_reload()                                            │
│    ├── reads bg_color from top-level  ──► HostWindow.set_bg_color()  │
│    └── _reconcile() sends CONFIG_UPDATE to changed widgets           │
│                                                                       │
│  HostWindow.paintEvent():                                             │
│    painter.fillRect(self.rect(), self._bg_qcolor)  ← MODIFIED       │
│    compositor.paint(painter)                                          │
└───────────────────────────┬─────────────────────────────────────────┘
                             │ multiprocessing.Queue (CONFIG_UPDATE msg)
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  WIDGET SUBPROCESSES (Pillow, no PyQt6)                               │
│                                                                       │
│  CalendarWidget.run():                                                │
│    poll_config_update() → applies time_color, date_color             │
│    render_frame():                                                    │
│      Image.new("RGBA", (W, H), (0, 0, 0, 0))  ← TRANSPARENT bg     │
│      draw.text(..., fill=self._time_color)                            │
│      draw.text(..., fill=self._date_color)                            │
│                                                                       │
│  PomodoroWidget.run():                                                │
│    _apply_config() already handles work/break accent colors          │
│    render_frame():                                                    │
│      Image.new("RGBA", (W, H), (0, 0, 0, 0))  ← TRANSPARENT bg     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Integration Points

### Integration Point 1: Host Background Color

**Current state:** `HostWindow.paintEvent` fills with hardcoded `QColor("#000000")`. `HostWindow` has no stored color attribute.

**Required change:** `HostWindow` must hold a `_bg_qcolor: QColor` attribute and expose a setter so `ConfigLoader` can push the new color on hot-reload. `paintEvent` switches from the literal to `self._bg_qcolor`.

**Who calls the setter:** `ConfigLoader._do_reload()` must read `new_config.get("bg_color", "#000000")` and call `self._window.set_bg_color(color_str)` (or equivalent). This requires `ConfigLoader` to have a reference to `HostWindow` — it already has one indirectly via `Compositor`, but a cleaner path is to pass the window (or a color callback) into `ConfigLoader` at construction.

**Simplest approach:** Add an `after_reload` callback already exists on `ConfigLoader`. Extend it or add a `bg_color_callback` parameter that fires with the new color string. Alternatively, have `_do_reload()` call a method on the compositor that passes through to the window. The cleanest minimal change is: `ConfigLoader` already stores `self._current`; the `after_reload` hook in `main.py` can read `config_loader.current_config["bg_color"]` and call `window.set_bg_color()`. No structural change needed.

**Boundary:** Host-internal. No IPC crosses a process boundary for background color — the host reads `bg_color` from config itself.

### Integration Point 2: Widget Transparent Background

**Current state:** Both `CalendarWidget.render_frame()` and `PomodoroWidget.render_frame()` call `Image.new("RGBA", (W, H), self._bg_color)` where `self._bg_color = (26, 26, 46, 255)` (opaque dark blue). The compositor blits these opaque frames with `painter.drawImage(slot_rect, img)` — Qt's `drawImage` respects the alpha channel of the source image, so switching to `(0, 0, 0, 0)` (transparent) immediately makes the host background show through.

**Required change:** Change `self._bg_color = (0, 0, 0, 0)` in widget `__init__`. Remove the `_bg_color` attribute from widgets entirely since widgets no longer own background color. This is a one-line change per widget.

**Constraint:** Widgets must NOT read `bg_color` from config — that is host-only state. Widget processes only receive their own widget config block (`widgets[n]` entry), not the top-level config. This is enforced by the existing IPC design: `ProcessManager.send_config_update(wid, new_widgets[wid])` sends only the widget's own entry.

**Compositor note:** The compositor has a fallback `painter.fillRect(slot_rect, QColor("#1a1a1a"))` for empty slots. This should also reflect the configured background, but since it is an "empty/loading" state, it can remain as a dark fallback or be updated to use `bg_color`. Treat as low priority.

### Integration Point 3: Calendar Color Config

**Current state:** `CalendarWidget.__init__` has `self._text_color = (220, 220, 220, 255)` and `self._time_color = (255, 255, 255, 255)` as hardcoded tuples. The `run()` method's config-update handler only applies `clock_format` and `font`.

**Required changes:**
1. `__init__`: Read `time_color` and `date_color` from `settings` dict, falling back to current hardcoded values.
2. `run()` config-update handler: Add `time_color` and `date_color` cases.
3. `render_frame()`: Use `self._time_color` (already used) and `self._text_color` (rename to `self._date_color` for clarity, or keep as `_text_color` — either works).
4. Color format: Widget receives hex string (`"#ffffff"`) from config. Must convert to Pillow RGBA tuple. `PIL.ImageColor.getrgb(hex_str)` returns `(r, g, b)` as a 3-tuple; append `255` for full opacity. Pomodoro already does this in `_accent_color()` — reuse the same pattern.

**config.json schema addition:**
```json
"settings": {
  "clock_format": "12h",
  "font": "Inter",
  "time_color": "#ffffff",
  "date_color": "#dcdcdc"
}
```

### Integration Point 4: Control Panel Layout Tab — bg_color Picker

**Current state:** Layout tab has only width/height spinboxes. `_collect_config()` reads `self._display_width.value()` and `self._display_height.value()`.

**Required changes:**
1. Add `ColorPickerWidget` instance for `bg_color` in `_build_layout_tab()`.
2. `_load_values()`: Read `self._config.get("bg_color", "#000000")` and push to the picker.
3. `_collect_config()`: Add `config["bg_color"] = self._bg_color_picker.color()` (or `hex()` equivalent on the picker).

**config.json schema addition:** Top-level `"bg_color": "#000000"` key. Default must be `"#000000"` to match current hardcoded value in `HostWindow`.

**`DEFAULT_CONFIG` in `config_io.py`:** Add `"bg_color": "#000000"` to the default dict so fresh installs and `load_config()` calls that hit the fallback path get a valid default.

### Integration Point 5: Control Panel Pomodoro Tab — Replace QLineEdit with ColorPickerWidget

**Current state:** Three `QLineEdit` fields (`_pomo_work_color`, `_pomo_short_break_color`, `_pomo_long_break_color`) already exist and already write hex strings to config. The entire data pipeline is working.

**Required changes:**
1. Replace `QLineEdit` with `ColorPickerWidget` in `_build_pomodoro_tab()`.
2. Update `_load_values()` to call `picker.set_color(hex_str)` instead of `lineEdit.setText()`.
3. Update `_collect_config()` to call `picker.color()` (or `hex()`) instead of `lineEdit.text()`.

**This is the lowest-risk integration point** because the data pipeline (config key names, widget hot-reload handler, `_apply_config`) is already correct. Only the UI widget changes.

### Integration Point 6: Control Panel Calendar Tab — Add Color Pickers

**Current state:** Calendar tab has `clock_format` combo and `font` combo. Color fields absent.

**Required changes:**
1. Add `ColorPickerWidget` for `time_color` and `date_color` in `_build_calendar_tab()`.
2. `_load_values()`: Read from `cal_cfg.get("time_color", "#ffffff")` and `cal_cfg.get("date_color", "#dcdcdc")`.
3. `_collect_config()` `_update_widget_settings` call for calendar: extend the settings dict with `time_color` and `date_color` values.

### Integration Point 7: ColorPickerWidget Component (New)

**Location:** `control_panel/color_picker.py` — control-panel-only, may import PyQt6 freely.

**Interface contract (what callers need):**
```python
class ColorPickerWidget(QWidget):
    color_changed = pyqtSignal(str)   # emits hex string on any change

    def color(self) -> str:           # returns current hex string e.g. "#ff4444"
    def set_color(self, hex_str: str) -> None:  # loads color from hex string
```

**Internal structure:** Hue slider (0–359) + intensity slider (0–100) + fixed saturation (e.g. 0.85–1.0) + live swatch QLabel + hex QLineEdit as fallback. HSV to RGB conversion is pure Python math or via `colorsys` stdlib — no new dependency.

**Constraint:** Must NOT be imported in widget subprocesses. It lives in `control_panel/` which is never imported by `widgets/` or `host/`.

---

## Component Map: New vs Modified

| Component | Status | Location | Change |
|-----------|--------|----------|--------|
| `control_panel/color_picker.py` | **New** | `control_panel/` | `ColorPickerWidget` — hue/intensity/swatch/hex |
| `host/window.py` | **Modified** | existing | Add `_bg_qcolor` attr + `set_bg_color()` method; paintEvent uses attr |
| `host/main.py` | **Modified** | existing | `after_reload` callback reads `bg_color` from config_loader, calls `window.set_bg_color()` |
| `host/config_loader.py` | **No change needed** | existing | `after_reload` callback pattern already covers bg_color update |
| `widgets/calendar/widget.py` | **Modified** | existing | Transparent bg; add `time_color`/`date_color`; handle in `__init__` + `run()` update handler |
| `widgets/pomodoro/widget.py` | **Modified** | existing | Transparent bg only (color fields already pipeline-ready) |
| `control_panel/main_window.py` | **Modified** | existing | Replace Pomodoro QLineEdit colors; add Calendar color pickers; add Layout bg_color picker |
| `control_panel/config_io.py` | **Modified** | existing | Add `"bg_color": "#000000"` to `DEFAULT_CONFIG` |
| `config.json` | **Modified** | `%LOCALAPPDATA%` | Add top-level `bg_color`; add `time_color`/`date_color` to calendar settings |

---

## Data Flow: Color Config Update End-to-End

### User changes bg_color in control panel

```
User drags hue/intensity slider in ColorPickerWidget (Layout tab)
    │
    ▼
ColorPickerWidget.color_changed signal → (connected to nothing at panel level)
    │  (no live preview needed — color saves on Save button)
    ▼
User clicks Save
    │
    ▼
_collect_config()
    ├── config["bg_color"] = self._bg_color_picker.color()   # "#1a1a2e"
    └── ... rest of existing fields unchanged
    │
    ▼
atomic_write_config(path, config)   → config.json file on disk
    │
    ▼                               (QFileSystemWatcher fires in host)
ConfigLoader._on_file_changed()
    └── debounce 100ms → _do_reload()
            ├── new_config = json.load(...)
            ├── self._current = new_config
            ├── _reconcile(old_config, new_config)
            │       └── sends CONFIG_UPDATE to each changed widget
            └── calls after_reload()
                    └── window.set_bg_color(new_config.get("bg_color", "#000000"))
                            └── self._bg_qcolor = QColor(color_str)
                                self.update()  ← triggers paintEvent
                                    └── painter.fillRect(self.rect(), self._bg_qcolor)
                                        compositor.paint(painter)
```

### User changes time_color in control panel

```
... same Save → atomic write → QFileSystemWatcher path as above ...
    │
    ▼
_reconcile() detects calendar widget settings changed
    └── send_config_update("calendar", new_calendar_widget_cfg)
            └── in_queue.put_nowait(ConfigUpdateMessage(...))
                    │
                    ▼                         (inside CalendarWidget subprocess)
            poll_config_update() → returns new config dict
                └── settings = new_cfg["settings"]
                    self._time_color = _parse_color(settings["time_color"])
                    self._date_color = _parse_color(settings["date_color"])
                        └── ImageColor.getrgb(hex) + (255,) = RGBA tuple
                    (next render_frame() uses updated colors)
```

---

## Recommended Project Structure Changes

```
control_panel/
├── __init__.py
├── __main__.py
├── autostart.py
├── color_picker.py     ← NEW
├── config_io.py        ← MODIFIED (DEFAULT_CONFIG)
└── main_window.py      ← MODIFIED (3 integration points)

host/
├── window.py           ← MODIFIED (set_bg_color + paintEvent)
├── main.py             ← MODIFIED (after_reload reads bg_color)
└── ... unchanged

widgets/
├── calendar/widget.py  ← MODIFIED (transparent bg + color fields)
├── pomodoro/widget.py  ← MODIFIED (transparent bg only)
└── ... unchanged
```

---

## Architectural Patterns

### Pattern 1: Host-Owned Global State, Widget-Owned Per-Widget State

**What:** Background color is host-only state. Widget accent/text colors are widget-process state. The boundary is config schema location: top-level key → host reads it; `widgets[n].settings` key → widget subprocess reads it via `ConfigUpdateMessage`.

**When to use:** Any future color or visual property that spans all widgets (border color, global opacity) goes top-level → host. Any property scoped to a single widget goes in that widget's `settings` block.

**Trade-offs:** Clear ownership. The downside is that widgets cannot inspect the background color for contrast calculations — but that is out of scope for v1.2.

### Pattern 2: Transparent Widget Canvases

**What:** Widgets use `(0, 0, 0, 0)` as their Pillow image background. The compositor's `painter.drawImage()` already preserves alpha (Qt's default composition mode is `SourceOver`). The host fills the background before compositing, so transparency in widget frames reveals the host background.

**When to use:** Always, once the host owns background color. There is no case in v1.2 where a widget should paint its own background.

**Trade-offs:** If the host background is not filled (e.g. bug where `set_bg_color` fails), widgets appear against whatever Qt paints by default (likely the system window background or undefined). This is a debugging concern, not a production concern.

### Pattern 3: Color as Hex String in Config, RGBA Tuple in Widgets

**What:** Config stores colors as hex strings (`"#ff4444"`). Host reads to `QColor(hex_str)` directly (QColor accepts hex strings). Widget subprocesses convert via `PIL.ImageColor.getrgb(hex_str)` + append `255` for alpha. This avoids storing RGBA tuples in JSON (awkward) and avoids parsing complexity.

**When to use:** All color values in config.json. Consistent format allows the control panel to read/write without conversion.

**Example (widget side):**
```python
from PIL import ImageColor

def _parse_color(hex_str: str) -> tuple:
    """Convert "#rrggbb" to Pillow RGBA tuple."""
    rgb = ImageColor.getrgb(hex_str)
    return rgb + (255,) if len(rgb) == 3 else rgb
```

Pomodoro already uses this exact pattern in `_accent_color()`. Calendar should adopt the same helper.

### Pattern 4: Default Values Mirror Current Hardcodes

**What:** Every new color config key must default to the currently hardcoded value. If `time_color` is absent from config, `settings.get("time_color", "#ffffff")` returns `"#ffffff"` — matching the existing `(255, 255, 255, 255)` tuple. If `bg_color` is absent from top-level config, `config.get("bg_color", "#000000")` matches the existing `QColor("#000000")` in paintEvent.

**Why:** Zero visual change on upgrade. Users who do not open the control panel after upgrading to v1.2 see identical output.

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Widget Reads bg_color from Config

**What people do:** Pass the full config dict to widgets (not just their settings block) so they can read `bg_color` and use it for their own background.

**Why it's wrong:** Violates the existing architecture boundary. `ProcessManager.send_config_update(wid, new_widgets[wid])` intentionally sends only the widget's own config entry. Changing this would mean widgets receive the entire config, coupling widget code to top-level schema. It also contradicts the ownership model: the host compositor owns background fill, not the widget.

**Do this instead:** Widget backgrounds are `(0, 0, 0, 0)`. The host fills the background before compositing. Widgets never know the background color.

### Anti-Pattern 2: Storing QColor in HostWindow Before set_bg_color Exists

**What people do:** Hardcode a second literal in paintEvent as an interim step — e.g. change `"#000000"` to `"#1a1a2e"` without making it configurable.

**Why it's wrong:** Creates two hardcoded values to track instead of one. Makes the configurable path harder to verify.

**Do this instead:** Add `set_bg_color()` and the `_bg_qcolor` attribute in the same commit as the transparent widget change. Both changes are one-liners; they belong together.

### Anti-Pattern 3: ColorPickerWidget in shared/ or widgets/

**What people do:** Put `color_picker.py` in `shared/` to make it "available everywhere."

**Why it's wrong:** `ColorPickerWidget` imports PyQt6. Widget subprocesses must never import PyQt6 (crashes on Windows spawn). `shared/` is imported by widget subprocesses via `shared.message_schema` and `shared.paths`. Placing PyQt6 code in `shared/` risks accidental import and violates the no-PyQt6-in-subprocesses constraint.

**Do this instead:** Keep `color_picker.py` in `control_panel/`. It is only needed by the control panel. If the host ever needed a color picker (it doesn't), it would be in `host/`.

### Anti-Pattern 4: Live Preview Requires a New IPC Channel

**What people do:** Add a new queue or socket so the control panel can push color changes to the host in real time (without saving to config.json).

**Why it's wrong:** The entire architecture relies on config.json as the single source of truth with a single write path. Adding a second live-preview channel creates two config paths that can diverge. The complexity is not justified for a static widget bar.

**Do this instead:** Colors apply on Save only. The existing hot-reload path (config.json → QFileSystemWatcher → after_reload) is fast enough for a save-to-apply UX. If instant preview were required, it would be a future milestone concern.

---

## Build Order

```
Step 1: control_panel/color_picker.py (ColorPickerWidget)
    Why: All three control panel integration points depend on this component.
         No other code depends on it yet — zero risk to existing functionality.
         Can be developed and tested in isolation with a small test harness.

Step 2: host/window.py — add set_bg_color() + _bg_qcolor attribute
    Why: Simple, isolated, testable. Cosmetic change to existing code.
         No widget or control panel changes needed to verify this in isolation:
         temporarily hardcode window.set_bg_color("#1a1a2e") in main.py to test.

Step 3: widgets/calendar/widget.py + widgets/pomodoro/widget.py — transparent bg
    Why: Can be verified independently of config changes. Change bg to (0,0,0,0)
         and observe that host background shows through. Confirms compositor
         alpha behavior before wiring up any new config keys.
         Both widgets change together — same one-line fix in each.

Step 4: config.json schema + config_io.py DEFAULT_CONFIG + host/main.py after_reload
    Why: Add "bg_color" to config.json and DEFAULT_CONFIG. Wire after_reload
         in main.py to call window.set_bg_color(). This closes the host-side
         bg_color pipeline. Verify: edit config.json manually, confirm hot-reload
         changes background color.

Step 5: widgets/calendar/widget.py — time_color + date_color config keys
    Why: Depends on Step 3 (transparent bg already in place). Add config reading
         in __init__ and run() update handler. Verify: add time_color to
         config.json calendar settings manually, confirm hot-reload applies.

Step 6: control_panel/main_window.py — Pomodoro tab QLineEdit → ColorPickerWidget
    Why: Lowest risk integration. Pipeline already works. UI-only change.
         Verify: save Pomodoro color from picker, confirm widget updates.

Step 7: control_panel/main_window.py — Calendar tab color pickers
    Why: Depends on Steps 1 and 5. Adds time_color/date_color pickers.
         Verify: save from picker, confirm calendar widget color updates.

Step 8: control_panel/main_window.py — Layout tab bg_color picker
    Why: Depends on Steps 1 and 4. Adds bg_color picker.
         Verify: save from picker, confirm host background changes.
```

**Rationale for this order:**
- Steps 1–3 are pure local changes with no cross-process dependencies — easy to verify and easy to revert.
- Step 4 is the first change that touches the hot-reload pipeline; doing it after the widget side is transparent means the visual result is immediately visible.
- Steps 6–8 are control panel UI work; they are last because they require the full pipeline (host + widget side) to be working for end-to-end verification.

---

## Sources

- Direct inspection of existing codebase (HIGH confidence for all claims):
  - `host/window.py` — paintEvent background fill, hardcoded `QColor("#000000")`
  - `host/compositor.py` — `painter.drawImage()` compositing path
  - `host/config_loader.py` — `after_reload` callback, `_reconcile` sending `ConfigUpdateMessage`
  - `widgets/calendar/widget.py` — hardcoded `_bg_color`, `_text_color`, `_time_color` tuples
  - `widgets/pomodoro/widget.py` — hardcoded `_bg_color`, existing `_apply_config` color handling
  - `control_panel/main_window.py` — existing `QLineEdit` color fields, `_collect_config`, `_update_widget_settings`
  - `control_panel/config_io.py` — `DEFAULT_CONFIG`, `atomic_write_config`
  - `shared/message_schema.py` — `ConfigUpdateMessage` carries `widget_id` + `config` (widget-scoped only)
  - `host/process_manager.py` — `send_config_update(wid, new_widgets[wid])` confirms widget-scoped delivery

---
*Architecture research for: MonitorControl v1.2 — Configurable Colors*
*Researched: 2026-03-27*
