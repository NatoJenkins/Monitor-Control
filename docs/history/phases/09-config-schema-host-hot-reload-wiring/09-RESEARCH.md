# Phase 9: Config Schema + Host Hot-Reload Wiring — Research

**Researched:** 2026-03-27
**Domain:** config.json schema extension, ConfigLoader hot-reload pipeline, CalendarWidget subprocess config propagation, PIL color parsing
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| BG-03 | Bar background color stored as top-level `bg_color` key in config.json; default #1a1a2e matches current hardcoded value | `HostWindow.set_bg_color()` already exists from Phase 8; gap is wiring `ConfigLoader._do_reload` → `window.set_bg_color()` and reading on initial load |
| CAL-04 | Calendar widget reads `time_color` from settings block; default #ffffff matches current hardcoded | `_time_color` is currently hardcoded `(255, 255, 255, 255)`; change init to read via `.get()` and update in `poll_config_update` handler |
| CAL-05 | Calendar widget reads `date_color` from settings block; default #dcdcdc matches current hardcoded | `_text_color` is currently hardcoded `(220, 220, 220, 255)`; same pattern as CAL-04 |
| CLR-01 | All new config keys use `.get()` with defaults matching current hardcoded values — zero visual change on upgrade | Already a locked project decision; all `.get()` calls must use the exact hardcoded default, never bracket access on new keys |
</phase_requirements>

---

## Summary

Phase 9 wires three config keys through the existing hot-reload pipeline without adding any new infrastructure. The host already has `QFileSystemWatcher` debounce, `_reconcile()`, and `HostWindow.set_bg_color()` from Phases 1–8. The only missing connections are: (1) the host reading `bg_color` from config on startup and after every hot-reload, and (2) the calendar widget reading color settings from its `settings` block on init and on `CONFIG_UPDATE`.

The `bg_color` key is a **top-level** config key, not inside any widget's `settings` dict. This means `_reconcile()` will not forward it to any widget — the host must extract it directly from the reloaded config. The `after_reload` callback hook already exists in `ConfigLoader` but is currently wired only to `reapply_clip`. Phase 9 extends that callback chain so it also calls `window.set_bg_color(new_config.get("bg_color", "#1a1a2e"))`.

For calendar colors, the pipeline is entirely different: those values live inside the widget's `settings` dict and travel through `_reconcile()` → `send_config_update()` → `in_queue` → `poll_config_update()` in the subprocess. The calendar widget already handles `CONFIG_UPDATE` for `clock_format` and `font`; Phase 9 adds `time_color` and `date_color` to that same handler block. Color hex strings must be converted to Pillow RGBA tuples using `PIL.ImageColor.getrgb()` wrapped in a `_safe_hex_color()` fallback — a pattern already documented as the project standard for subprocess color parsing.

**Primary recommendation:** Two nearly independent work streams — host-side bg wiring and widget-side color reading — that can be planned in a single wave or split into two tasks within one plan.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt6 | 6.10.2 (already installed) | QFileSystemWatcher, QTimer, QColor for bg_color validation | Project-wide Qt layer; no new install |
| Pillow (PIL) | already installed | `PIL.ImageColor.getrgb()` hex→RGB in calendar subprocess | Already used by all widget files; subprocess-safe (no Qt) |
| json | stdlib | config.json parse | Already used throughout |
| colorsys | stdlib | N/A for this phase | Not needed — colors flow as hex strings |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PIL.ImageColor.getrgb | already installed | Convert "#rrggbb" to (R, G, B) tuple | In widget subprocess; wrap in `_safe_hex_color()` |
| QColor.isValid() | PyQt6 6.10.2 | Validate hex string in host context | Already used by `set_bg_color()` in Phase 8 |

**Installation:** No new packages. All dependencies are already present.

---

## Architecture Patterns

### Recommended Project Structure

```
host/
├── config_loader.py    # MODIFIED — _do_reload calls bg callback; apply_config applies bg
├── main.py             # MODIFIED — wire set_bg_color into after_reload callback chain
└── window.py           # UNCHANGED — set_bg_color() already exists from Phase 8

config.json             # MODIFIED — add top-level "bg_color" key

widgets/calendar/
└── widget.py           # MODIFIED — read time_color/date_color from settings; handle in CONFIG_UPDATE
```

### Pattern 1: Host-Side bg_color Wiring

**What:** After every config load or hot-reload, the host extracts `bg_color` from the config dict and calls `window.set_bg_color()`. This must happen both at startup (`apply_config`) and after each hot-reload (`_do_reload`).

**When to use:** Any top-level config key that controls a host-owned property (not a widget setting).

**Two valid wiring approaches:**

Option A — Extend `after_reload` callback in `main.py`:
```python
# Source: host/main.py (existing after_reload pattern)
def _apply_bg_from_config():
    cfg = config_loader.current_config
    window.set_bg_color(cfg.get("bg_color", "#1a1a2e"))

def after_reload():
    reapply_clip()
    _apply_bg_from_config()

config_loader = ConfigLoader(str(_cfg), pm, window.compositor, after_reload=after_reload)
config = config_loader.load()
config_loader.apply_config(config)
_apply_bg_from_config()  # also apply on initial load
```

Option B — Teach `ConfigLoader` about bg_color directly (requires passing `window` to `ConfigLoader`):
Not recommended — increases coupling; `ConfigLoader` currently has no reference to `HostWindow`.

**Recommendation:** Option A. Keep `ConfigLoader` decoupled; extend `after_reload` in `main.py`.

### Pattern 2: Calendar Widget Color Reading (Subprocess)

**What:** On `__init__`, read `time_color` and `date_color` from `settings` using `.get()` with hardcoded defaults. Convert hex string to Pillow RGBA tuple via `_safe_hex_color()`. On `CONFIG_UPDATE`, re-apply the same conversion if the key is present.

**When to use:** Any widget subprocess that needs user-configurable colors.

```python
# Source: codebase design — subprocess-safe color parsing pattern (CLR-01, CAL-04, CAL-05)
from PIL import ImageColor

def _safe_hex_color(hex_str: str, default_rgba: tuple) -> tuple:
    """Convert '#rrggbb' to (R, G, B, 255). Returns default_rgba on any error."""
    try:
        r, g, b = ImageColor.getrgb(hex_str)
        return (r, g, b, 255)
    except (ValueError, AttributeError):
        return default_rgba

# In CalendarWidget.__init__:
settings = config.get("settings", {})
self._time_color = _safe_hex_color(
    settings.get("time_color", "#ffffff"), (255, 255, 255, 255)
)
self._text_color = _safe_hex_color(
    settings.get("date_color", "#dcdcdc"), (220, 220, 220, 255)
)

# In CalendarWidget.run() CONFIG_UPDATE handler:
if "time_color" in settings:
    self._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))
if "date_color" in settings:
    self._text_color = _safe_hex_color(settings["date_color"], (220, 220, 220, 255))
```

### Pattern 3: config.json Schema Extension

**What:** Add `bg_color` as a top-level key. Add `time_color` and `date_color` inside the calendar widget's `settings` block. All additions use the exact current hardcoded values so v1.1 configs without the keys still render identically.

```json
{
  "bg_color": "#1a1a2e",
  "layout": { ... },
  "widgets": [
    {
      "id": "calendar",
      "settings": {
        "clock_format": "12h",
        "font": "Inter",
        "time_color": "#ffffff",
        "date_color": "#dcdcdc"
      }
    }
  ]
}
```

**Note:** The `bg_color` key must be at the top level of the JSON object, not nested under `layout` or any widget — `HostWindow` is not a widget, and its background is a host-level concern.

### Pattern 4: _reconcile Already Handles Widget Color Propagation

**What:** When config.json is saved with new `time_color`/`date_color` values in the calendar `settings` dict, `_reconcile()` detects the widget config changed (dict equality check on entire widget object) and calls `pm.send_config_update("calendar", new_widget_cfg)`. The calendar subprocess receives this on its `in_queue` as a `ConfigUpdateMessage`.

**Important:** This is fully automatic. No changes needed to `_reconcile()` or `ProcessManager`. The only change needed is the calendar widget reading the keys from `settings` in its `CONFIG_UPDATE` handler.

**Why it works:** `_reconcile()` at line 98–100 of `config_loader.py` does:
```python
for wid in set(old_widgets) & set(new_widgets):
    if old_widgets[wid] != new_widgets[wid]:
        self._pm.send_config_update(wid, new_widgets[wid])
```
Any change to the widget's settings dict triggers a `CONFIG_UPDATE` with the full widget config dict.

### Anti-Patterns to Avoid

- **Bracket access on new keys**: `config["bg_color"]` instead of `config.get("bg_color", "#1a1a2e")` — crashes on v1.1 configs without the key. CLR-01 mandates `.get()` everywhere.
- **Directly passing hex strings to Pillow `fill=` without validation**: `ImageColor.getrgb()` raises `ValueError` on invalid hex; this kills the subprocess. Always wrap in `_safe_hex_color()`.
- **Reading `bg_color` from a widget's settings dict**: `bg_color` is top-level; looking for it inside a widget's `settings` block will silently miss it.
- **Relying solely on `_reconcile()` for bg_color**: `_reconcile()` only processes the `widgets` array. Top-level keys like `bg_color` are invisible to it.
- **Converting to RGBA on the host side and sending tuples**: Host → widget IPC carries full widget config dicts (JSON-serializable). Send hex strings; let the widget convert.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hex string validation in host | Custom regex or `try: int(h, 16)` | `QColor(hex_str).isValid()` | Already used in `set_bg_color()`; handles edge cases (#rgb short form, named colors) |
| Hex to RGBA in subprocess | `int(hex_str[1:3], 16)` manual parsing | `PIL.ImageColor.getrgb()` | Handles #rgb, #rrggbb, named colors; Pillow already imported |
| Debounce timer for hot-reload | Custom timer logic | Existing `QTimer` in `ConfigLoader._debounce` | Already implemented; 100ms single-shot debounce |
| Config change detection | Hashing or diff logic | Dict `!=` comparison in `_reconcile()` | Already implemented and tested |

---

## Common Pitfalls

### Pitfall 1: bg_color Not Applied on Initial Load
**What goes wrong:** `apply_config()` starts widgets but never touches `bg_color`. On first startup, `HostWindow._bg_qcolor` defaults to `#1a1a2e` (correct), but once a user sets a custom color and the host restarts, the bg flashes the default until the first file change triggers a reload.
**Why it happens:** `apply_config()` only processes the `widgets` array; `bg_color` is a top-level key outside that array.
**How to avoid:** After `config_loader.load()` and `config_loader.apply_config(config)` in `main.py`, explicitly call `window.set_bg_color(config.get("bg_color", "#1a1a2e"))`.
**Warning signs:** Host shows `#1a1a2e` after restart even when config has a different `bg_color` value.

### Pitfall 2: after_reload Overwrite
**What goes wrong:** `ConfigLoader` is constructed with `after_reload=reapply_clip`. If the Phase 9 change simply replaces this with a new lambda that only does `set_bg_color`, the clip cursor stops being reapplied on hot-reload — a regression.
**Why it happens:** `after_reload` accepts a single callable; replacing it drops the previous behavior.
**How to avoid:** Compose both callbacks: `after_reload=lambda: (reapply_clip(), window.set_bg_color(config_loader.current_config.get("bg_color", "#1a1a2e")))` or define a named function that calls both.
**Warning signs:** After any config.json save, cursor clip no longer re-applies.

### Pitfall 3: CONFIG_UPDATE Carries Full Widget Dict, Not Just Settings
**What goes wrong:** Calendar's `CONFIG_UPDATE` handler does `settings = new_cfg.get("settings", {})` where `new_cfg` is the full widget config dict (including `id`, `type`, `x`, `y`, `width`, `height`, `settings`). This is already correct in the existing `clock_format` handler. The pitfall is assuming `new_cfg` is just the `settings` sub-dict.
**Why it happens:** `send_config_update(wid, new_widgets[wid])` passes the entire widget config object (line 100 of `config_loader.py`), not just `settings`.
**How to avoid:** Always extract `settings = new_cfg.get("settings", {})` at the top of the handler, then read keys from `settings`.
**Warning signs:** `time_color` key lookup fails with `KeyError` because code looked in the wrong dict level.

### Pitfall 4: PIL.ImageColor.getrgb Returns RGB Not RGBA
**What goes wrong:** `ImageColor.getrgb("#ffffff")` returns `(255, 255, 255)` — a 3-tuple. Pillow's `draw.text(fill=...)` accepts both RGB and RGBA, but the existing code uses 4-tuples: `(255, 255, 255, 255)`. Inconsistent tuple length is not an error but is sloppy and may cause issues if tuple is compared or logged.
**Why it happens:** `getrgb()` only returns alpha if the input string includes alpha (e.g. `"#rrggbbaa"`).
**How to avoid:** In `_safe_hex_color()`, always append `255` as the alpha: `r, g, b = ImageColor.getrgb(hex_str); return (r, g, b, 255)`.

### Pitfall 5: config.json at %LOCALAPPDATA% vs. Project Root
**What goes wrong:** During development, editing the wrong `config.json` (project root vs. `%LOCALAPPDATA%\MonitorControl\config.json`) produces no visible effect and no error.
**Why it happens:** Phase 7 moved config to `%LOCALAPPDATA%\MonitorControl\config.json` for packaged exe compatibility. The project root `config.json` still exists as a dev convenience copy but is not watched by the host.
**How to avoid:** Edit `%LOCALAPPDATA%\MonitorControl\config.json` when testing hot-reload. The `shared.paths.get_config_path()` function returns the correct path.
**Warning signs:** config.json edits appear to do nothing; hot-reload log message never prints.

---

## Code Examples

### Reading bg_color in main.py (initial load + after_reload)

```python
# Source: host/main.py — extend existing after_reload pattern
config_loader = ConfigLoader(str(_cfg), pm, window.compositor, after_reload=None)
config = config_loader.load()

# Apply bg_color on initial load (BG-03)
window.set_bg_color(config.get("bg_color", "#1a1a2e"))

config_loader.apply_config(config)

# Compose after_reload: both reapply_clip AND bg update
def _after_reload():
    reapply_clip()
    window.set_bg_color(config_loader.current_config.get("bg_color", "#1a1a2e"))

config_loader._after_reload = _after_reload
```

Or pass directly at construction if the window is available before ConfigLoader is built:

```python
def _after_reload():
    reapply_clip()
    window.set_bg_color(config_loader.current_config.get("bg_color", "#1a1a2e"))

config_loader = ConfigLoader(str(_cfg), pm, window.compositor, after_reload=_after_reload)
config = config_loader.load()
window.set_bg_color(config.get("bg_color", "#1a1a2e"))
config_loader.apply_config(config)
```

Note: In the second form there's a forward reference (`config_loader` used before assignment in the closure). Python closures capture variables by reference so this is safe — the closure doesn't execute until after `config_loader` is bound.

### _safe_hex_color helper (in calendar/widget.py)

```python
# Source: codebase design (CLR-01, subprocess color safety pattern)
from PIL import ImageColor

def _safe_hex_color(hex_str: str, default_rgba: tuple) -> tuple:
    """Convert '#rrggbb' → (R, G, B, 255). Returns default_rgba on error."""
    try:
        r, g, b = ImageColor.getrgb(hex_str)
        return (r, g, b, 255)
    except (ValueError, AttributeError):
        return default_rgba
```

### CalendarWidget __init__ reading color settings

```python
# Source: widgets/calendar/widget.py — replace hardcoded color tuples
settings = config.get("settings", {})
self._time_color = _safe_hex_color(
    settings.get("time_color", "#ffffff"), (255, 255, 255, 255)
)
self._text_color = _safe_hex_color(
    settings.get("date_color", "#dcdcdc"), (220, 220, 220, 255)
)
```

### CalendarWidget CONFIG_UPDATE handler — add color keys

```python
# Source: widgets/calendar/widget.py (extend existing run() handler)
new_cfg = self.poll_config_update()
if new_cfg:
    settings = new_cfg.get("settings", {})
    if "clock_format" in settings:
        self._clock_format = settings["clock_format"]
    if "font" in settings:
        self._font_name = settings["font"]
    # Phase 9 additions:
    if "time_color" in settings:
        self._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))
    if "date_color" in settings:
        self._text_color = _safe_hex_color(settings["date_color"], (220, 220, 220, 255))
```

### config.json with Phase 9 keys

```json
{
  "bg_color": "#1a1a2e",
  "layout": {
    "display": { "width": 1920, "height": 515 }
  },
  "widgets": [
    {
      "id": "calendar",
      "type": "calendar",
      "x": 640, "y": 0, "width": 640, "height": 515,
      "settings": {
        "clock_format": "12h",
        "font": "Inter",
        "time_color": "#ffffff",
        "date_color": "#dcdcdc"
      }
    }
  ]
}
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Widgets own bg fill (hardcoded RGBA in `Image.new()`) | Host owns bg fill via `paintEvent`; widgets transparent | Phase 8-02 | bg_color can now be set per config without touching widget code |
| `_text_color`, `_time_color` as hardcoded tuples in `CalendarWidget.__init__` | Read from `settings.get()` with hardcoded defaults as fallback | Phase 9 | Config-driven without breaking v1.1 configs |
| `after_reload` only used for `reapply_clip` | `after_reload` also calls `window.set_bg_color()` | Phase 9 | bg_color updates live on config file save |

---

## Open Questions

1. **Should `ConfigLoader._do_reload` receive the window reference directly?**
   - What we know: Currently `ConfigLoader` only knows about `process_manager` and `compositor`. Passing `window` to it would centralize bg wiring but increase coupling.
   - What's unclear: Whether future phases will add more host-level config keys that also need wiring, making a tighter `ConfigLoader` more appealing.
   - Recommendation: Keep `ConfigLoader` decoupled for Phase 9; use the `after_reload` callback. Revisit if more host-level keys accumulate in Phase 10/11.

2. **Should bg_color validation error log or silently default?**
   - What we know: `set_bg_color()` already silently no-ops on invalid color (Phase 8 decision). If `bg_color` in config is invalid, the window retains its previous color.
   - What's unclear: Whether a log message would help debugging.
   - Recommendation: Add a `print()` log in `_after_reload` when `QColor(value).isValid()` is False, consistent with other `[ConfigLoader]` log messages.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini present at project root) |
| Config file | `E:/ClaudeCodeProjects/MonitorControl/pytest.ini` |
| Quick run command | `pytest tests/test_config_loader.py tests/test_calendar_widget.py tests/test_window.py -x -q` |
| Full suite command | `pytest -x -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BG-03 | `bg_color` read from config on startup and applied to `HostWindow` | unit | `pytest tests/test_config_loader.py tests/test_window.py -x -q` | ✅ (extend existing files) |
| BG-03 | `bg_color` update flows through hot-reload (`_do_reload` → `after_reload` → `set_bg_color`) | unit | `pytest tests/test_config_loader.py -x -q` | ✅ (extend existing) |
| BG-03 | v1.1 config without `bg_color` key defaults to `#1a1a2e` without error | unit | `pytest tests/test_config_loader.py -x -q` | ✅ (extend existing) |
| CAL-04 | `CalendarWidget.__init__` reads `time_color` from settings; default #ffffff | unit | `pytest tests/test_calendar_widget.py -x -q` | ✅ (extend existing) |
| CAL-05 | `CalendarWidget.__init__` reads `date_color` from settings; default #dcdcdc | unit | `pytest tests/test_calendar_widget.py -x -q` | ✅ (extend existing) |
| CAL-04 | `time_color` CONFIG_UPDATE changes rendered frame | unit | `pytest tests/test_calendar_widget.py -x -q` | ✅ (extend existing) |
| CAL-05 | `date_color` CONFIG_UPDATE changes rendered frame | unit | `pytest tests/test_calendar_widget.py -x -q` | ✅ (extend existing) |
| CLR-01 | Missing keys in v1.1 config load without KeyError | unit | `pytest tests/test_calendar_widget.py tests/test_config_loader.py -x -q` | ✅ (part of BG-03/CAL tests) |
| CLR-01 | Invalid hex string for `time_color`/`date_color` leaves widget unchanged | unit | `pytest tests/test_calendar_widget.py -x -q` | ❌ Wave 0 — add `_safe_hex_color` tests |

### Sampling Rate

- **Per task commit:** `pytest tests/test_config_loader.py tests/test_calendar_widget.py tests/test_window.py -x -q`
- **Per wave merge:** `pytest -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_calendar_widget.py` — add tests for `time_color`/`date_color` reading in `__init__` and `CONFIG_UPDATE` (CLR-01 invalid hex path, CAL-04, CAL-05)
- [ ] `tests/test_config_loader.py` — add tests verifying `after_reload` is called on hot-reload and that `_do_reload` does not crash when `bg_color` is absent from config

No new test files needed — all new tests extend existing test files.

---

## Sources

### Primary (HIGH confidence)

- Direct codebase inspection (`host/config_loader.py`, `host/main.py`, `host/window.py`, `host/compositor.py`, `widgets/calendar/widget.py`, `shared/message_schema.py`, `widgets/base.py`) — all findings are code-level facts
- `config.json` (project root) — current schema, no `bg_color` or calendar color keys present
- `tests/test_config_loader.py`, `tests/test_calendar_widget.py`, `tests/test_window.py` — existing test coverage and patterns

### Secondary (MEDIUM confidence)

- `.planning/STATE.md` `## Decisions` section — locked project decisions including CLR-01, `_safe_hex_color` pattern, `.get()` mandate, `after_reload` hook semantics

### Tertiary (LOW confidence)

None. All findings derived from direct codebase inspection.

---

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — all libraries already in use; no new dependencies
- Architecture: HIGH — derived directly from existing `config_loader.py`, `main.py`, and `window.py` code
- Pitfalls: HIGH — all derived from direct code reading of the exact functions being modified
- Test map: HIGH — existing test files confirmed present; gap identified from requirements not yet covered

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable domain; no external dependencies changing)
