# Phase 10: Control Panel Integration - Research

**Researched:** 2026-03-27
**Domain:** PyQt6 control panel UI — replacing QLineEdit fields with ColorPickerWidget, wiring save to config hot-reload
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| POMO-06 | Replace the three hex QLineEdit fields in the Pomodoro Appearance groupbox with ColorPickerWidget instances; each pre-populated from config on open; values persisted to config on Save | ColorPickerWidget.set_color() and .color() APIs confirmed. _build_pomodoro_tab / _load_values / _collect_config mutation points all identified. |
| CAL-06 | Add two ColorPickerWidget instances to the Calendar Clock Settings groupbox for time_color and date_color; pre-populated from config on open; values persisted to config on Save | CalendarWidget already reads time_color / date_color from config and hot-reloads them. Calendar tab _build / _load / _collect mutation points identified. |
</phase_requirements>

---

## Summary

Phase 10 is a pure UI surgery on `control_panel/main_window.py`. No new pip packages are required. ColorPickerWidget already exists at `control_panel/color_picker.py` and is fully tested. PomodoroWidget already reads `work_accent_color`, `short_break_accent_color`, and `long_break_accent_color` from settings and applies them via `_apply_config()` on hot-reload. CalendarWidget already reads `time_color` and `date_color` from settings and hot-reloads them via `run()`. The full config-to-screen pipeline is therefore already operational — Phase 10 only needs to wire the control panel UI end.

The work is three-sided: (1) replace three QLineEdit fields in the Pomodoro Appearance groupbox with ColorPickerWidget instances; (2) add two ColorPickerWidget instances to the Calendar Clock Settings groupbox; (3) update `_load_values()` and `_collect_config()` to read/write from the pickers instead of the former line edits. Atomic save via `atomic_write_config()` already triggers QFileSystemWatcher hot-reload in the host — no host changes needed.

The existing test for `_pomo_work_color` / `_pomo_short_break_color` / `_pomo_long_break_color` as QLineEdit instances (`test_pomodoro_accent_colors_load`) will break when those attributes become ColorPickerWidget instances. That test must be updated in the same plan that replaces the fields.

**Primary recommendation:** Perform the entire change in `main_window.py` as one focused plan. Write failing tests first (TDD), then implement. The only new import needed is `from control_panel.color_picker import ColorPickerWidget`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt6 | Already installed | ColorPickerWidget, QFormLayout, _build_pomodoro_tab refactor | All control panel code already uses PyQt6 |
| control_panel.color_picker.ColorPickerWidget | local | The reusable picker widget built in Phase 8 | Designed for exactly this use case |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyQt6.QtWidgets.QFormLayout | Already in use | Layout rows of label + ColorPickerWidget | Already used in Pomodoro and Calendar tabs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ColorPickerWidget | QColorDialog | QColorDialog is a modal popup — poor UX for a settings panel; ColorPickerWidget is inline |
| ColorPickerWidget | Re-using QLineEdit | QLineEdit is what we are replacing per POMO-06 |

**Installation:** No new packages needed.

---

## Architecture Patterns

### How ColorPickerWidget slots into a QFormLayout

The existing Pomodoro Appearance groupbox uses `QFormLayout`. Each color row is currently:
```python
self._pomo_work_color = QLineEdit()
appear_form.addRow("Work Color:", self._pomo_work_color)
```

The replacement pattern is identical in structure:
```python
self._pomo_work_color = ColorPickerWidget()
appear_form.addRow("Work Color:", self._pomo_work_color)
```

`ColorPickerWidget` is a `QWidget` subclass — it drops directly into any layout.

### _load_values() pattern

Current (QLineEdit):
```python
self._pomo_work_color.setText(pomo_cfg.get("work_accent_color", "#ff4444"))
```

New (ColorPickerWidget):
```python
self._pomo_work_color.set_color(pomo_cfg.get("work_accent_color", "#ff4444"))
```

`set_color()` silently ignores invalid hex strings — no guard needed.

### _collect_config() pattern

Current (QLineEdit):
```python
"work_accent_color": self._pomo_work_color.text(),
```

New (ColorPickerWidget):
```python
"work_accent_color": self._pomo_work_color.color(),
```

`color()` always returns a valid `#rrggbb` lowercase string from internal state.

### Calendar tab additions

Calendar's `_build_calendar_tab()` currently has one `QGroupBox("Clock Settings")` with a `QFormLayout`. Two new rows are appended:

```python
self._cal_time_color = ColorPickerWidget()
form.addRow("Time Color:", self._cal_time_color)

self._cal_date_color = ColorPickerWidget()
form.addRow("Date Color:", self._cal_date_color)
```

`_load_values()` gains:
```python
self._cal_time_color.set_color(cal_cfg.get("time_color", "#ffffff"))
self._cal_date_color.set_color(cal_cfg.get("date_color", "#dcdcdc"))
```

`_collect_config()` gains two keys in the calendar settings dict:
```python
"time_color": self._cal_time_color.color(),
"date_color": self._cal_date_color.color(),
```

### Hot-reload path (no host changes needed)

```
User adjusts picker -> clicks Save
  -> _collect_config() reads .color() from pickers
  -> atomic_write_config() writes config.json
  -> QFileSystemWatcher fires fileChanged in host
  -> ConfigLoader._reconcile() sends ConfigUpdateMessage to pomodoro/calendar in_queues
  -> PomodoroWidget._apply_config() / CalendarWidget.run() applies immediately
```

This entire pipeline was verified operational in Phase 9. Phase 10 only adds the UI triggers at the top.

### Recommended Project Structure (no changes)
```
control_panel/
├── color_picker.py    # unchanged — ColorPickerWidget already complete
├── main_window.py     # PRIMARY CHANGE FILE — all Phase 10 work lives here
├── config_io.py       # unchanged
└── autostart.py       # unchanged
tests/
└── test_control_panel_window.py  # update broken test + add 5 new tests
```

### Anti-Patterns to Avoid
- **Connecting color_changed signal to anything during panel build:** The signal is for live-preview use cases. Phase 10 does NOT need real-time widget updates from the picker — the user clicks Save and the hot-reload fires. Do not wire up color_changed.
- **Using .text() instead of .color() in _collect_config:** ColorPickerWidget has no .text() method. Accessing the internal _hex_field.text() directly is a fragile anti-pattern.
- **Guarding set_color() with QColor.isValid():** set_color() already silently ignores invalid hex strings. Double-guarding adds noise.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Inline color picker | Custom slider + swatch widget | ColorPickerWidget | Already built and TDD-verified in Phase 8 |
| Hex validation | Manual regex on picker output | ColorPickerWidget.color() | Always returns valid #rrggbb |
| Config write + hot-reload trigger | Custom file writer | atomic_write_config() | Already atomic, already watched by host |

---

## Common Pitfalls

### Pitfall 1: Broken test for `_pomo_work_color` attribute type
**What goes wrong:** `test_pomodoro_accent_colors_load` asserts `window._pomo_work_color.text() == "#aabbcc"`. After replacement, `_pomo_work_color` is a `ColorPickerWidget`, which has no `.text()` method — the test raises `AttributeError`.
**Why it happens:** The test was written when the field was a QLineEdit. The attribute name is reused but the type changes.
**How to avoid:** Update the test in the same task that replaces the fields. Assert `.color()` rather than `.text()`. Also check that `.color()` returns the nearest matching color — note ColorPickerWidget normalizes through HSL at fixed saturation 0.8, so the returned value may not be byte-identical to the input hex.
**Warning signs:** `AttributeError: 'ColorPickerWidget' object has no attribute 'text'` in the test run.

### Pitfall 2: ColorPickerWidget normalizes colors through HSL
**What goes wrong:** You call `picker.set_color("#aabbcc")` and then `picker.color()` returns a different hex string. This happens because ColorPickerWidget stores `_hue` and `_lightness` floats and reconstructs via `QColor.fromHslF(hue, 0.8, lightness)` — the saturation is fixed at 0.8 and the round-trip through HSL may shift the RGB values.
**Why it happens:** The widget was designed for user-facing color selection, not exact-hex-passthrough.
**How to avoid:** In tests, assert `picker.color()` returns a valid 7-char lowercase hex string (structural check) rather than asserting exact byte equality with the input. For config write tests, assert the key is present and the value starts with `#` and is 7 chars.
**Warning signs:** Test assertions like `assert picker.color() == "#aabbcc"` failing with a close-but-different hex value.

### Pitfall 3: Import placement — ColorPickerWidget must not be imported in widget subprocesses
**What goes wrong:** If ColorPickerWidget import leaks into shared/ or widget code, it triggers `import PyQt6` in subprocesses, which crashes on Windows spawn.
**Why it happens:** Import added at module level in a file that is transitively imported by subprocess entry points.
**How to avoid:** Import `ColorPickerWidget` only inside `control_panel/main_window.py`. Never in shared/ or widgets/. This is an existing project constraint from the Roadmap decisions.
**Warning signs:** Subprocess crash with `RuntimeError: PyQt6 imported in subprocess`.

### Pitfall 4: _collect_config calendar block is incomplete
**What goes wrong:** If the calendar _collect_config block only writes `clock_format` and `font`, the new `time_color` / `date_color` keys are silently dropped on every Save, reverting colors to widget defaults.
**Why it happens:** `_update_widget_settings()` overwrites the entire `settings` dict — it does not merge. If the dict passed to it omits keys, those keys are gone.
**How to avoid:** Ensure the calendar settings dict in `_collect_config()` includes ALL four keys: `clock_format`, `font`, `time_color`, `date_color`.

---

## Code Examples

Verified patterns from existing codebase:

### ColorPickerWidget public API (from control_panel/color_picker.py)
```python
# Source: control_panel/color_picker.py

# Instantiate
picker = ColorPickerWidget()

# Pre-populate programmatically (no signal emitted)
picker.set_color("#ff4444")   # accepts #rrggbb; silently ignores invalid

# Read current color
hex_str = picker.color()      # returns "#rrggbb" lowercase, always valid
```

### How PomodoroWidget applies color updates (from widgets/pomodoro/widget.py)
```python
# Source: widgets/pomodoro/widget.py — _apply_config()
if "work_accent_color" in settings:
    self._work_color = settings["work_accent_color"]
```
The Pomodoro widget applies color changes immediately on next render — no restart needed.

### How CalendarWidget applies color updates (from widgets/calendar/widget.py)
```python
# Source: widgets/calendar/widget.py — run()
if "time_color" in settings:
    self._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))
if "date_color" in settings:
    self._text_color = _safe_hex_color(settings["date_color"], (220, 220, 220, 255))
```

### How _update_widget_settings works (key risk: full overwrite)
```python
# Source: control_panel/main_window.py — _update_widget_settings()
def _update_widget_settings(self, config, widget_type, settings):
    for w in config.get("widgets", []):
        if w.get("type") == widget_type:
            w["settings"] = settings   # FULL OVERWRITE — must include all keys
            return
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| QLineEdit for hex color input | ColorPickerWidget (hue/intensity/swatch) | Phase 8 (2026-03-27) | POMO-06 replaces QLineEdits |
| Calendar had no color config | time_color / date_color in config.json + hot-reload | Phase 9 (2026-03-27) | CAL-06 exposes these in the panel |

**Deprecated/outdated:**
- `self._pomo_work_color = QLineEdit()` and siblings: removed in this phase, replaced by ColorPickerWidget.

---

## Open Questions

1. **ColorPickerWidget height in QFormLayout**
   - What we know: ColorPickerWidget renders a VBox with two slider rows plus a swatch+hex row. Its sizeHint is driven by QSlider default height (~20px each) plus margins — approximately 80-100px total.
   - What's unclear: Whether the Appearance groupbox height becomes visually awkward in the 480px minimum window.
   - Recommendation: Accept default sizing. The control panel can be resized; no constraints prevent it. If the panel feels cramped, the planner can note that `setMinimumHeight` on the main window could be bumped — but this is cosmetic and out of scope for POMO-06.

2. **Color round-trip fidelity in tests**
   - What we know: `picker.set_color("#ff4444")` followed by `picker.color()` returns `QColor.fromHslF(hue_of_ff4444, 0.8, lightness_of_ff4444).name()` which may differ from `"#ff4444"`.
   - What's unclear: Whether test authors will expect exact equality.
   - Recommendation: Tests for picker load/save should assert structural validity (`startswith("#")`, `len == 7`) or compute the expected value via `QColor.fromHslF(...)` rather than asserting exact input equality.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini present) |
| Config file | `E:/ClaudeCodeProjects/MonitorControl/pytest.ini` |
| Quick run command | `python -m pytest tests/test_control_panel_window.py -q` |
| Full suite command | `python -m pytest tests/ -q -m "not integration"` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| POMO-06 | Pomodoro tab has 3 ColorPickerWidget instances (not QLineEdit) at `_pomo_work_color`, `_pomo_short_break_color`, `_pomo_long_break_color` | unit | `python -m pytest tests/test_control_panel_window.py::test_pomodoro_color_pickers_are_widgets -x` | Wave 0 |
| POMO-06 | Pickers pre-populated from config (set_color called with config value) | unit | `python -m pytest tests/test_control_panel_window.py::test_pomodoro_color_pickers_load_from_config -x` | Wave 0 |
| POMO-06 | _collect_config includes work/short/long_break accent color from picker.color() | unit | `python -m pytest tests/test_control_panel_window.py::test_collect_config_includes_pomo_colors -x` | Wave 0 (update existing test) |
| CAL-06 | Calendar tab has 2 ColorPickerWidget instances at `_cal_time_color`, `_cal_date_color` | unit | `python -m pytest tests/test_control_panel_window.py::test_calendar_color_pickers_are_widgets -x` | Wave 0 |
| CAL-06 | Calendar pickers pre-populated from config | unit | `python -m pytest tests/test_control_panel_window.py::test_calendar_color_pickers_load_from_config -x` | Wave 0 |
| CAL-06 | _collect_config includes time_color and date_color from calendar pickers | unit | `python -m pytest tests/test_control_panel_window.py::test_collect_config_includes_cal_colors -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_control_panel_window.py -q`
- **Per wave merge:** `python -m pytest tests/ -q -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] 6 new test functions in `tests/test_control_panel_window.py` — listed in table above
- [ ] Update `test_pomodoro_accent_colors_load` — currently asserts `.text()` on QLineEdit; must be rewritten to assert `.color()` on ColorPickerWidget
- [ ] Update `test_collect_config_includes_new_fields` — currently implicitly passes because the keys exist; may need no change, but verify after attribute type changes
- [ ] No new test files needed — all new tests extend the existing file

*(No new test infrastructure required — pytest + qapp fixture already present.)*

---

## Sources

### Primary (HIGH confidence)
- `control_panel/main_window.py` — full source read; all mutation points (build/load/collect) confirmed
- `control_panel/color_picker.py` — full source read; public API (`set_color`, `color`, `color_changed`) confirmed
- `widgets/pomodoro/widget.py` — full source read; `_apply_config()` color handling confirmed
- `widgets/calendar/widget.py` — full source read; `run()` color hot-reload handling confirmed
- `control_panel/config_io.py` — full source read; `atomic_write_config()` and `_update_widget_settings` overwrite behavior confirmed
- `host/config_loader.py` — full source read; `_reconcile()` sends `ConfigUpdateMessage` on widget settings change
- `tests/test_control_panel_window.py` — full source read; broken test (`test_pomodoro_accent_colors_load`) identified
- `config.json` — full source read; confirmed `time_color`, `date_color`, `work_accent_color`, etc. already in schema

### Secondary (MEDIUM confidence)
- None required — all findings come from direct codebase inspection

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in use; no new dependencies
- Architecture: HIGH — mutation points fully identified by reading existing code
- Pitfalls: HIGH — broken test and color normalization issue directly observed from code
- Test gaps: HIGH — existing test file read in full; new test names derived from requirement IDs

**Research date:** 2026-03-27
**Valid until:** This research is based entirely on the local codebase. Valid as long as Phase 8 and Phase 9 are not reverted.
