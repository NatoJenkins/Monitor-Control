# Project Research Summary

**Project:** MonitorControl v1.2 — Configurable Color System
**Domain:** PyQt6 desktop widget bar, Windows multiprocessing architecture, inline color picker UI
**Researched:** 2026-03-27
**Confidence:** HIGH

## Executive Summary

MonitorControl v1.2 is a focused enhancement to an already-shipped PyQt6 widget bar. The project replaces all hardcoded colors with a user-configurable color system: a reusable `ColorPickerWidget` (hue slider + intensity slider + live swatch + hex input) deployed in three places in the control panel, plus an architectural shift that moves background color ownership from individual widget subprocesses to the host compositor. The existing stack requires zero new packages — all color capabilities are covered by PyQt6 6.10.2 and Python's stdlib `colorsys`.

The recommended approach is an 8-step build order with a strict prerequisite chain: build `ColorPickerWidget` first (it has no dependencies and can be unit-tested in isolation), then migrate host background ownership and make widgets transparent simultaneously (they must be done in the same commit or the colors will conflict), then wire up config schema changes and calendar color config, then integrate pickers into control panel tabs. The most important architectural constraint is that the host compositor must own background fill before any `bg_color` config key is exposed in the UI.

The primary risks are the argument-order trap in Python's `colorsys` module (`hls_to_rgb(h, l, s)` takes lightness second — not saturation) and the simultaneous migration of widget backgrounds from opaque to transparent. Both produce silent wrong output if missed, but both are easily prevented with a named wrapper function and a targeted unit test. All other risks are well-understood Qt patterns with established fixes documented in PITFALLS.md.

---

## Key Findings

### Recommended Stack

No new packages are required. All v1.2 color capabilities are covered by the existing install: PyQt6 6.10.2 for all UI components and Python's built-in `colorsys` for HSL-to-RGB math (or equivalently `QColor.fromHslF` — either approach is valid and the all-QColor approach avoids the HLS argument-order trap entirely).

**Core technologies:**
- `PyQt6.QSlider` + `QWidget` overlay — gradient groove sliders. Subclassing `QSlider` and overriding `paintEvent` does not work (style system repaints over custom drawing); the correct approach is a `QWidget` that paints the gradient groove and overlays a transparent `QSlider` child for the handle.
- `PyQt6.QColor` — hex string construction, HSL via `QColor.fromHslF(h, s, l)`, validation via `QColor.isValidColorName()` (note: `isValidColor()` is deprecated in Qt6).
- `PyQt6.QRegularExpressionValidator` (from `QtGui`) + `QRegularExpression` (from `QtCore`) — this module split is a Qt6 change from Qt5; importing `QRegularExpression` from `QtGui` raises `ImportError`.
- `colorsys` (stdlib) — `hls_to_rgb(h, l, s)` where argument order is H, L, S (not H, S, L); always use a named wrapper, never inline positional calls.
- `PIL.ImageColor.getrgb()` — hex-to-RGBA conversion in widget subprocesses; already used by PomodoroWidget; must be wrapped with a safe fallback to prevent subprocess crashes on invalid input.

### Expected Features

The v1.2 milestone is explicitly scoped. All items listed under "Launch With" are P1 and non-optional.

**Must have (table stakes):**
- Hue slider (0–359) — primary color selection axis
- Intensity/value slider (0–100%) — controls dark-to-vivid axis for the bar's dark background context
- Live color swatch — `QWidget` subclass overriding `paintEvent` (not `setAutoFillBackground` + palette, which is overridden by parent stylesheets)
- Hex input field with `QRegularExpressionValidator` constraining to `#RRGGBB`; `editingFinished` gates saving
- Bidirectional sync (sliders update hex, hex updates sliders) with an `_updating: bool` flag to prevent signal loops
- Defaults that exactly match current hardcoded values — zero visual change on upgrade (CLR-01)
- Persist on Save via existing atomic config write pattern

**Should have (polish, add after base widget is confirmed stable):**
- Gradient-painted hue track (visual polish only; zero behavior change)
- Bar background preview strip in Layout tab (low complexity; makes bg_color purpose spatially clear)

**Defer (v2+):**
- Theme presets / saved palettes
- Eyedropper / screen color sampling
- Per-widget opacity / alpha slider
- QColorDialog (modal pattern breaks the inline form UX)
- Full HSV/HSL/RGB/CMYK format switcher

**Anti-feature confirmed:** Fixed saturation (not exposing S slider) is the correct design decision. Hue + intensity covers the entire useful color space for a dark-background bar. The hex input serves as the precision escape hatch for any value the two sliders cannot easily reach.

### Architecture Approach

Background color ownership moves from widget subprocesses to the host compositor. Widgets switch from opaque `(26, 26, 46, 255)` Pillow backgrounds to fully transparent `(0, 0, 0, 0)`, and `HostWindow.paintEvent` fills the full window rect with a configurable `QColor` before compositing. The `ColorPickerWidget` lives exclusively in `control_panel/color_picker.py` — it must never be placed in `shared/` because `shared/` is imported by widget subprocesses, and PyQt6 in a subprocess crashes on Windows spawn.

**Major components:**
1. `control_panel/color_picker.py` (NEW) — `ColorPickerWidget` reusable `QWidget` subclass; all three control panel integration points depend on it.
2. `host/window.py` (MODIFIED) — add `_bg_qcolor` attribute + `set_bg_color()` method; `paintEvent` uses attribute instead of hardcoded literal.
3. `widgets/calendar/widget.py` (MODIFIED) — transparent background; reads `time_color` and `date_color` from settings via `.get()` with hardcoded defaults; hex string converted to Pillow RGBA via `ImageColor.getrgb()`.
4. `widgets/pomodoro/widget.py` (MODIFIED) — transparent background only (color config pipeline already works).
5. `control_panel/main_window.py` (MODIFIED) — three integration points: Pomodoro QLineEdit → ColorPickerWidget; Calendar tab gains two pickers; Layout tab gains bg_color picker.
6. `control_panel/config_io.py` (MODIFIED) — add `"bg_color": "#000000"` to `DEFAULT_CONFIG`.
7. `config.json` (MODIFIED) — new top-level `bg_color` key; new `time_color`/`date_color` in calendar settings block.

**Key architectural invariant:** `ProcessManager.send_config_update(wid, new_widgets[wid])` sends only the widget's own config entry — widgets never receive `bg_color`. This is enforced by the existing IPC design and must not be changed.

**Color representation contract:** Config stores all colors as `#rrggbb` hex strings. Host reads to `QColor(hex_str)` directly. Widget subprocesses convert via `PIL.ImageColor.getrgb(hex_str) + (255,)`. No RGBA tuples in JSON.

### Critical Pitfalls

The following are the highest-priority pitfalls for v1.2 (numbered per PITFALLS.md):

1. **colorsys H-L-S argument order trap (Pitfall 17, HIGH)** — `colorsys.hls_to_rgb(h, l, s)` takes lightness second and saturation third, opposite of CSS HSL convention and `QColor.fromHslF`. Passing them reversed produces silently wrong colors with no error. Prevention: use a named wrapper that explicitly maps CSS HSL convention to the colorsys HLS order, or avoid colorsys entirely and use `QColor.fromHslF(h, s, l)` throughout.

2. **Widget opaque background conflicts with host bg_color (Pitfall 21, HIGH)** — If widgets still render with opaque backgrounds after the host gains configurable fill, the widget's alpha=255 pixels overwrite the host fill on every compositor pass. The configured `bg_color` appears to have no effect. Prevention: make widgets transparent and give the host the configurable fill in the same commit — treat as one atomic change.

3. **Missing `bg_color` key crashes upgrade (Pitfall 23, HIGH)** — Using `config["bg_color"]` instead of `config.get("bg_color", "#000000")` raises `KeyError` on v1.1 configs that predate the key. Prevention: all new color keys must use `.get()` with defaults that exactly match current hardcoded values.

4. **`ImageColor.getrgb()` crashes widget subprocess on invalid hex (Pitfall 20, HIGH)** — A malformed hex string in config raises `ValueError` in `render_frame()`, killing the subprocess permanently. Prevention: wrap all `getrgb()` calls with a `_safe_hex_color(value, fallback)` helper; the control panel validator is a first line of defense, not a substitute for subprocess-level defense.

5. **`QColor.fromHslF()` returns hue=-1 for achromatic colors (Pitfall 19, MEDIUM)** — `QColor.hslHueF()` returns `-1` for grays (saturation=0). Round-tripping through a gray hex string snaps the hue slider to minimum, losing the user's hue preference. Prevention: track `_hue` as internal widget state; only update it from `QColor` when `hslHueF() >= 0.0`.

6. **`paintEvent` must use `self.rect()` not `event.rect()` for background fill (Pitfall 22, MEDIUM)** — `event.rect()` is only the dirty region and leaves unpainted gaps at certain widget sizes on Windows. For the host background fill, always use `self.rect()` to prevent bleed-through from previous frames.

---

## Implications for Roadmap

The dependency chain in ARCHITECTURE.md maps cleanly to a 4-phase structure. The architectural constraint — widget transparency and host fill must be done simultaneously — drives the phase boundaries.

### Phase 1: Core Widget and Background Infrastructure

**Rationale:** `ColorPickerWidget` is required by all three control panel integration points; nothing downstream can proceed without it. Widget transparency and host background fill are a single logical change that must be atomic to avoid the double-fill color conflict (Pitfall 21). Both are low-complexity local changes with no cross-process dependencies, making this the safest starting phase.

**Delivers:**
- `control_panel/color_picker.py` — `ColorPickerWidget` with hue slider, intensity slider, live swatch, hex input, bidirectional sync with `_updating` flag, `color_changed(str)` signal, `color()` and `set_color()` interface
- `host/window.py` — `set_bg_color()` method + `_bg_qcolor` attribute; `paintEvent` uses `self.rect()` and the attribute
- Widget subprocesses — transparent `(0, 0, 0, 0)` backgrounds in calendar and pomodoro

**Features addressed:** CPKR-01, prerequisite for BG-01

**Pitfalls to avoid:** Pitfall 17 (HLS arg order — write wrapper first, add unit test), Pitfall 18 (QSlider integer values must be normalized to 0–1 before color math), Pitfall 21 (widget transparency and host fill in same commit), Pitfall 22 (self.rect() not event.rect() for host fill)

**Research flag:** No additional research needed. All APIs verified at HIGH confidence.

### Phase 2: Config Schema and Host Hot-Reload Wiring

**Rationale:** With the host capable of accepting a `bg_color` and widgets already transparent, this phase closes the end-to-end background pipeline from config file to screen. Manual config editing serves as the integration test — change `bg_color` in config.json by hand, confirm the bar changes color — before any control panel UI is built. Calendar color config follows naturally because it uses the same hot-reload path.

**Delivers:**
- `control_panel/config_io.py` — `"bg_color": "#000000"` added to `DEFAULT_CONFIG`
- `host/main.py` — `after_reload` callback reads `bg_color` via `.get()` and calls `window.set_bg_color()`
- `widgets/calendar/widget.py` — reads `time_color` and `date_color` from settings via `.get()` with exact hardcoded defaults; applies on `ConfigUpdateMessage`; converts hex to RGBA via `_parse_color()` helper

**Features addressed:** BG-01, BG-02, CAL-04, CAL-05, CLR-01

**Pitfalls to avoid:** Pitfall 23 (`.get()` with exact defaults for all new keys — never bracket access), Pitfall 4 (QFileSystemWatcher re-add after atomic file replace is already implemented; confirm it remains intact)

**Research flag:** No additional research needed. Established patterns in this codebase.

### Phase 3: Control Panel Integration — Pomodoro and Calendar

**Rationale:** Pomodoro is the lowest-risk integration: the entire data pipeline (config key names, widget hot-reload handler, `_apply_config`) already works correctly — only the UI widget changes from QLineEdit to ColorPickerWidget. Calendar follows immediately, reusing the same picker class with the widget-side config reading already in place from Phase 2.

**Delivers:**
- Pomodoro tab — three existing QLineEdit hex fields replaced with three `ColorPickerWidget` instances; `_load_values()` and `_collect_config()` updated
- Calendar tab — two new `ColorPickerWidget` instances for `time_color` and `date_color`; `_load_values()` reads from calendar settings block

**Features addressed:** POMO-06, CAL-06

**Pitfalls to avoid:** Pitfall 20 (`_safe_hex_color` fallback wrapper added to PomodoroWidget before integration), Pitfall 19 (achromatic hue round-trip — verify with unit test before integration)

**Research flag:** No additional research needed.

### Phase 4: Layout Tab bg_color Picker and Polish

**Rationale:** The final end-to-end integration. By this phase the full pipeline is tested and confirmed. Adding the Layout tab picker is the lowest-risk change and verifies the complete user flow from slider to bar background. Polish items (gradient track, preview strip) are added here if time permits — they are zero-behavior-change additions that do not affect the critical path.

**Delivers:**
- Layout tab — `ColorPickerWidget` for `bg_color`; `_load_values()` reads `config.get("bg_color", "#000000")`; `_collect_config()` writes `config["bg_color"]`
- Optional polish: gradient-painted hue track on sliders; bar background preview strip in Layout tab

**Features addressed:** BG-03, plus P2/P3 polish items

**Pitfalls to avoid:** Pitfall 22 (confirm background bleed does not appear after live color change in the host; verify with a contrasting color test)

**Research flag:** No additional research needed. Gradient track uses the same `QWidget` + transparent slider overlay pattern already built in Phase 1.

### Phase Ordering Rationale

- ColorPickerWidget-first order minimizes blocked work. It has no dependencies on other v1.2 changes and can be built and unit-tested in complete isolation before any host or config changes are made.
- Widget transparency and host fill are treated as one atomic phase (Phase 1) because a partially-migrated state — host has configurable fill but widgets still render opaque — causes the user's configured color to be overwritten silently on every frame. This is the one ordering constraint where partial completion is worse than doing nothing.
- Config schema changes (Phase 2) come after the rendering layer is validated so manual config editing serves as the integration test. Verifying `bg_color` works by editing the JSON directly is faster and more diagnostic than debugging through the control panel UI.
- Control panel UI work (Phases 3 and 4) comes last because it requires the complete rendering pipeline to provide meaningful end-to-end verification.
- Polish items (gradient track, preview strip) are explicitly deferred to Phase 4 to keep the critical path short. Both are zero-behavior-change additions.

### Research Flags

**Phases needing deeper research during planning:**
- None. All four research areas returned HIGH confidence findings from official Qt6 and Python documentation, plus direct codebase inspection for all architecture claims.

**Phases with standard patterns (skip research-phase):**
- **Phase 1:** PyQt6 custom widget patterns are fully documented. The QWidget + transparent slider overlay pattern is the Qt-documented workaround for gradient grooves; colorsys is stdlib.
- **Phase 2:** Config `.get()` defaults and QFileSystemWatcher re-add are established patterns already in this codebase.
- **Phase 3 and 4:** Pure reuse of `ColorPickerWidget` via a stable interface. No new patterns introduced.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All APIs verified against PyQt6 6.10.2 Riverbank docs and Qt6 official docs; colorsys from Python official docs; no new packages means no integration uncertainty |
| Features | HIGH | Derived from direct codebase inspection of existing QLineEdit fields and hardcoded color tuples; anti-features confirmed by architectural constraints |
| Architecture | HIGH | All integration points described from direct inspection of existing source files; component boundaries confirmed by reading `message_schema.py` and `process_manager.py` |
| Pitfalls | HIGH (core v1.2 pitfalls) / MEDIUM (compositing bleed edge cases) | Pitfalls 17–21 verified against official Qt and Python docs; Pitfall 22 (transparent compositing bleed) is MEDIUM — confirmed in Qt Forum but not in official Qt docs |

**Overall confidence:** HIGH

### Gaps to Address

- **Achromatic hue round-trip (Pitfall 19):** The fix is clear (track `_hue` separately), but the exact UX behavior when loading from a gray hex config value should be verified manually with the built widget. Write a unit test: set hue to 0.5, set intensity to 0 (gray), save, reload, confirm hue slider is still at 0.5.

- **colorsys vs QColor-only approach:** Both are valid. The all-QColor approach (`QColor.fromHslF` + `QColor.hslHueF`, `hslSaturationF`, `lightnessF` for round-trip) eliminates the HLS argument-order trap entirely and is recommended if there is any doubt. The implementing developer should choose one approach before writing `ColorPickerWidget` and apply it consistently throughout.

- **Compositor empty-slot fallback:** `compositor.py` has a `painter.fillRect(slot_rect, QColor("#1a1a1a"))` for empty/loading slots. This does not reflect the configured `bg_color`. ARCHITECTURE.md flags it as low priority for v1.2 — it is a loading state, not steady state. If it becomes visually jarring after the background migration, update it to use the same `bg_color` value passed through to the compositor.

---

## Sources

### Primary (HIGH confidence)

- PyQt6 6.10.2 Riverbank Computing docs — `QColor.fromHslF`, `QColor.isValidColorName`, `QColor.name()`, `QColor.hslHueF()` achromatic -1 behavior, `QRegularExpressionValidator` in QtGui
- Qt6 Official docs — `QSlider` stylesheet subcontrol `::groove:horizontal`, `QFileSystemWatcher` re-add after atomic replace behavior, `QRegularExpression` in QtCore
- Python official docs — `colorsys.hls_to_rgb(h, l, s)` argument order; all inputs 0.0–1.0
- Codebase direct inspection — `host/window.py`, `host/compositor.py`, `host/config_loader.py`, `widgets/calendar/widget.py`, `widgets/pomodoro/widget.py`, `control_panel/main_window.py`, `control_panel/config_io.py`, `shared/message_schema.py`, `host/process_manager.py`

### Secondary (MEDIUM confidence)

- Qt Forum — `event.rect()` vs `self.rect()` partial-fill bug on Windows confirmed (PyQt6 specific, `pyqt6-windows-os-custom-paintevent-doesn-t-fill-the-whole-widget-background-in-some-size`)
- pythonguis.com — custom widget `paintEvent` pattern, `update()` trigger requirement
- runebook.dev — confirmation that `QSlider.paintEvent` subclassing does not work in Qt; stylesheet or widget composition required

### Tertiary (LOW confidence)

- Competitor analysis (Rainmeter, yasb) — hex-string-in-config pattern; WebSearch only, not authoritative for implementation decisions

---

*Research completed: 2026-03-27*
*Ready for roadmap: yes*
