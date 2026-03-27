# Feature Research

**Domain:** Configurable color system for a desktop utility bar / widget app settings panel (PyQt6)
**Researched:** 2026-03-27 (v1.2 milestone — configurable colors)
**Confidence:** HIGH for color picker mechanics (well-established patterns, verified against Qt docs and codebase); HIGH for UX anti-features (confirmed by codebase constraints); MEDIUM for competitor comparisons (WebSearch only)

---

## v1.2 Scope Context

v1.1 shipped autostart and control panel packaging. v1.2 replaces all hardcoded colors with a user-configurable color system:

- Bar background color (`bg_color`) moves from hardcoded `#1a1a2e` in widgets to compositor-owned, config-driven fill
- Calendar text colors (`time_color`, `date_color`) become configurable per-widget settings
- Pomodoro tab's three hex QLineEdit fields are replaced with a reusable `ColorPickerWidget`
- A reusable `ColorPickerWidget` (hue slider + intensity slider + hex input + live swatch) is the central deliverable

Existing code state (from codebase inspection):
- `control_panel/main_window.py`: three `QLineEdit` fields for Pomodoro accent colors already exist — these are replaced by `ColorPickerWidget`
- `widgets/calendar/widget.py`: `_bg_color = (26, 26, 46, 255)`, `_time_color = (255, 255, 255, 255)`, `_text_color = (220, 220, 220, 255)` are hardcoded — these become config-driven
- `host/compositor.py`: `painter.fillRect(slot_rect, QColor("#1a1a1a"))` for empty slots — background ownership moves to host before widget paint

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features a color configuration UI must have. Missing these makes the UI feel broken or unfinished.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Hue slider (0–359 degrees) | Primary color selection axis; universal in all color pickers since Photoshop; without it users cannot select a color intuitively | LOW | `QSlider(Qt.Horizontal)` with range 0–359; `QColor.fromHsv(h, s, v)` converts to RGB for display |
| Intensity/value slider (0–100%) | Controls dark-to-vivid axis; essential for a dark-background bar where the same hue at full value looks very different from 40% | LOW | Value component of HSV; range 0–100 mapped to 0–255 internally via `QColor.fromHsv` |
| Live swatch preview | Users cannot evaluate a color from slider positions alone; they need to see the result; hex strings give zero visual feedback | LOW | A `QFrame` with `setStyleSheet(f"background-color: {hex_str};")` updated on every slider change |
| Hex input field with validation | Power users paste exact hex codes; hex is universal across design tools; the existing Pomodoro fields already establish this expectation | LOW | `QLineEdit` with a 7-char `#RRGGBB` regex validator or `inputMask`; already present for Pomodoro — replace, do not add |
| Bidirectional sync (sliders update hex, hex updates sliders) | If the sliders can update hex but hex cannot update sliders, users who type a hex value have no confirmation it registered; inconsistency is a UX bug | MEDIUM | Two-way binding with `blockSignals(True)` guards or an `_updating: bool` instance flag to prevent update loops |
| Defaults that match current hardcoded values | Users upgrading from v1.1 must see zero visual change; unexpected color change on upgrade destroys trust | LOW | Default values: `bg_color: "#1a1a2e"`, `time_color: "#ffffff"`, `date_color: "#dcdcdc"`, Pomodoro defaults: `#ff4444`, `#44ff44`, `#4488ff` — all match existing hardcoded values |
| Persist on Save | Color changes survive Save + reload cycle; the existing Save button pattern and atomic config write must apply to color fields identically to other settings | LOW | Serialize as `"#rrggbb"` strings in config.json; the pattern is already established for Pomodoro color fields |

### Differentiators (Competitive Advantage)

Features that add value beyond the minimum, worthwhile for this personal utility context.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Gradient-painted hue track | The slider track painted as a rainbow gradient makes the current hue position obvious without mental translation from a 0–359 number; no other setting in the control panel requires this kind of spatial reasoning | MEDIUM | Custom `paintEvent` on a `QSlider` subclass drawing a `QLinearGradient` across hue 0–359; or a stylesheet `qlineargradient` if Qt supports it for the groove sub-control. Either way: well-understood, no custom hit testing needed |
| Fixed saturation (not exposed) | The bar runs on a very dark background (#1a1a2e); full HSV exposes S (saturation) as a third slider that adds complexity with little practical gain — for this use case hue + value is sufficient to cover the entire useful color space | LOW | This is a deliberate non-feature that reduces widget surface area; fix saturation at 85–90%; users who need a specific exact color use hex input |
| Colored swatch button beside label | A small colored rectangle next to the field label shows the current color at a glance without expanding anything; reinforces "this is a color setting" without extra words | LOW | `QLabel` or narrow `QFrame` with `setFixedWidth(32)` and `setStyleSheet` background; placed in the form row beside the "Work Color:" label |
| Bar background preview strip in Layout tab | A fixed-height narrow horizontal strip painted with the current `bg_color` value in the Layout tab makes the spatial relationship (this is what fills the bar behind everything) immediately obvious | LOW | A `QFrame` with fixed height (e.g. 24px), full row width, updated on color change |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Full HSV/HSL/RGB/CMYK switcher | "Professional" tools like Photoshop have it; users expect parity | Multiplies UI surface 3–4×; forces format conversion code for every read/write path; this app has 5–6 fixed accent colors, not a design workflow requiring CMYK; the control panel window is 480px minimum — multiple format panels do not fit gracefully | Expose H + V only; accept hex input as the precision escape hatch for any value sliders cannot easily reach |
| Color wheel (circular picker) | Looks impressive; common in mobile apps; some PyQt libs offer it | Requires a canvas widget with mouse hit-testing inside a circle — significant custom Qt painting and pointer math; circular pickers are harder to use precisely than linear sliders; the control panel window is narrow and the wheel needs ~200×200 pixels of square canvas | Two linear `QSlider` widgets are easier to use precisely, require no custom mouse hit-testing, and fit naturally in a `QFormLayout` row |
| Eyedropper / screen color sampling | Power users want to sample colors from elsewhere on the screen (wallpaper, another app) | Requires Win32 `GetPixel` or screenshot-and-sample loop; full-screen screenshot on Windows with elevated permissions is complex; the control panel is a settings panel, not a design tool | Hex input is sufficient as an escape hatch; users can use a system color picker or external tool and paste the hex value |
| Real-time bar preview (live edit on bar as sliders move) | Users want to see changes on the bar without pressing Save | The bar is on Display 3; the control panel is on a primary display — the user cannot see both simultaneously while operating the sliders; the hot-reload system requires a config file write to trigger QFileSystemWatcher; adding a side channel for unsaved preview state adds architectural complexity for marginal value | Live swatch in the control panel provides immediate feedback; Save triggers hot-reload fast enough (QFileSystemWatcher + 100ms debounce) that round-trip latency is acceptable |
| Alpha/opacity slider per color | Widgets on a transparent surface could blend with a background | The host compositor fills the bar background with a solid color (BG-01 moves background ownership to compositor); per-color alpha has no rendering target in the current architecture; mixing semi-transparent widget renders on top of a solid compositor fill produces correct results only if widget alpha is 0 (transparent) or 255 (opaque) | Keep all user-facing colors fully opaque (`#rrggbb` not `#aarrggbb`); the compositor `bg_color` alpha is always 255 |
| Theme presets / saved palettes | "Let me save my favorite color schemes" | Creates a separate data management problem: CRUD for presets, a new config schema section, an additional UI surface area (preset list, add/delete buttons, name input); this app has a single user with a single bar and a small fixed number of color slots | Manual hex input provides equivalent flexibility without building a palette manager; if presets become important, they are a v2+ backlog item |
| QColorDialog (Qt native) as the picker | Built-in, no code needed | Modal dialog: it blocks the settings panel, requires a click to open and another to confirm, provides no inline preview in context with the other settings, and shows a full HSV/CMYK/HTML panel that is overkill for this use case | Inline widget (hue + value sliders + swatch) in the form layout provides immediate feedback without modal interruption |

---

## Feature Dependencies

```
[ColorPickerWidget (reusable PyQt6 QWidget subclass)]
    └──requires──> [Hue QSlider (0–359)]
    └──requires──> [Intensity/Value QSlider (0–100)]
    └──requires──> [Live swatch QFrame]
    └──requires──> [Hex QLineEdit (validated, #RRGGBB)]
    └──requires──> [Bidirectional slider ↔ hex sync with blockSignals guards]
    └──emits──>    [color_changed(hex_str: str) signal]

[bg_color in config.json]
    └──requires──> [Compositor owns bar background fill (BG-01)]
                       └──requires──> [Widgets render on transparent background (alpha=0 bg)]
                                          └──requires──> [CalendarWidget._bg_color changed from solid to transparent]
    └──exposed by──> [ColorPickerWidget in Layout tab (BG-03)]

[Calendar time_color / date_color]
    └──requires──> [CalendarWidget reads colors from config settings block (CAL-04..05)]
    └──exposed by──> [ColorPickerWidget in Calendar tab (CAL-06)]
    └──reuses──>   [ColorPickerWidget] (same widget class, different instance)

[Pomodoro accent pickers]
    └──replaces──> [Three existing QLineEdit hex fields in Pomodoro tab]
    └──reuses──>   [ColorPickerWidget] (same widget class, three instances)

[Bidirectional sync]
    └──conflicts──> [Naive signal connections without guards]
                    (slider.valueChanged → update_hex AND hex.textChanged → update_sliders
                     creates an infinite update loop without blockSignals or _updating flag)
```

### Dependency Notes

- **Compositor background ownership (BG-01) is a prerequisite for bg_color:** The compositor currently does `painter.fillRect(slot_rect, QColor("#1a1a1a"))` to fill empty slots, which incidentally serves as background. For a configurable `bg_color`, the host must call `painter.fillRect(window_rect, QColor(bg_color))` before iterating slots, and widgets must render with a transparent background (RGBA alpha=0 where they have no content). This rendering architecture change must be in place before `bg_color` is exposed in config.

- **ColorPickerWidget lives in `control_panel/` only:** It is a PyQt6 widget. Widget subprocess code (Pillow-based) is Qt-free. Colors flow from the control panel to the widget processes as hex strings in config.json, deserialized by the widget into RGBA tuples using `PIL.ImageColor.getrgb()` or manual parsing. No PyQt6 import bleeds into widget subprocess code.

- **Bidirectional sync requires explicit loop prevention:** Connecting `slider.valueChanged` → `update_hex` and `hex.textChanged` → `update_sliders` creates a signal loop. The standard PyQt6 pattern is an `_updating: bool` instance flag set to `True` before programmatic updates and checked at the top of each handler. `blockSignals(True)` is an alternative but hides other signals.

- **CalendarWidget has two color roles (time and date):** The existing code uses `_time_color` for the large time text and `_text_color` for the date line. Both become configurable. The config.json settings block gains `time_color` and `date_color` keys. The widget reads these on init and on `ConfigUpdateMessage`. The naming convention in config should be `time_color` and `date_color` to match the PROJECT.md requirements (CAL-04..05).

---

## MVP Definition

### Launch With (v1.2)

This milestone is the MVP — all items below constitute the complete v1.2 scope.

- [ ] **Compositor owns bar background (BG-01):** Host fills entire window rect with `bg_color` before painting widget frames; widgets render on transparent (alpha=0) background
- [ ] **bg_color in config.json (BG-02):** Top-level key, default `"#1a1a2e"`, read by host on hot-reload
- [ ] **ColorPickerWidget (CPKR-01):** Reusable `QWidget` subclass with hue slider, intensity/value slider, live swatch, hex input, bidirectional sync, `color_changed(str)` signal
- [ ] **bg_color picker in Layout tab (BG-03):** Layout tab gains a ColorPickerWidget for bar background color
- [ ] **Pomodoro hex fields replaced (POMO-06):** Three QLineEdit accent color fields replaced with three ColorPickerWidget instances
- [ ] **Calendar time_color + date_color (CAL-04..06):** CalendarWidget reads both from settings block; Calendar tab gains two ColorPickerWidget instances
- [ ] **Zero visual change on upgrade (CLR-01):** All color defaults match current hardcoded values exactly

### Add After Validation (v1.2 polish)

- [ ] **Gradient-painted hue track** — Visual polish only; add after base ColorPickerWidget is confirmed stable; no behavior change
- [ ] **Bar background preview strip in Layout tab** — Low complexity; makes bg_color purpose spatially obvious

### Future Consideration (v2+)

- [ ] **Theme presets** — Only if multi-profile or share-with-others use case emerges
- [ ] **Eyedropper** — Only if users report hex input is an insufficient precision escape hatch
- [ ] **Per-widget opacity** — Only if architecture changes to support alpha-composited widget layers

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| ColorPickerWidget (hue + value sliders + swatch + hex) | HIGH | LOW | P1 |
| Bidirectional slider ↔ hex sync | HIGH | MEDIUM | P1 |
| Compositor owns bg fill (BG-01) | HIGH (prerequisite) | MEDIUM | P1 |
| bg_color in config + Layout tab picker | HIGH | LOW (reuse) | P1 |
| Pomodoro hex fields → ColorPickerWidget | HIGH | LOW (reuse) | P1 |
| Calendar time_color + date_color | HIGH | LOW (reuse) | P1 |
| Widget transparent background rendering | HIGH (prerequisite) | LOW | P1 |
| Defaults matching current hardcoded values | HIGH | LOW | P1 |
| Gradient hue track on slider | LOW | MEDIUM | P3 |
| Bar background preview strip | LOW | LOW | P2 |
| Fixed saturation (not exposing S slider) | HIGH (simplicity) | LOW (non-feature) | P1 |

**Priority key:**
- P1: Required for v1.2 milestone
- P2: Polish, add if time permits
- P3: Nice to have, future consideration

---

## Competitor / Reference Analysis

Reference implementations reviewed for pattern extraction (what comparable tools do for color config):

| Feature | Rainmeter | yasb (PyQt6, Windows) | Our Approach |
|---------|-----------|------------------------|--------------|
| Color config mechanism | Hex strings hand-edited in .ini skin files | CSS-like stylesheet strings in config.yaml | Hex strings in config.json via GUI color pickers |
| Color picker UI | None — raw hex in text file | None — raw CSS string | Inline hue + value sliders + swatch + hex input |
| Live preview | None — requires skin reload | None — requires restart | Swatch in control panel; hot-reload on Save |
| Per-widget vs global colors | Global via skin variables | Per-widget via CSS class selector | Both: global `bg_color`, per-widget accent/text colors |
| Saturation control | Full HSL in CSS | Full CSS color syntax | Fixed saturation (intentionally limited for simplicity) |

Key insight: every comparable tool requires editing raw hex or CSS strings in config files with no GUI. MonitorControl's control panel is already a differentiator in this space. The color picker feature raises the UX bar without adding complexity beyond what the PyQt6 `QSlider` + `QLineEdit` + `QColor` APIs already support natively.

---

## Sources

- Codebase: `control_panel/main_window.py` — existing QLineEdit hex fields (lines 131–141, 299–301)
- Codebase: `host/compositor.py` — hardcoded `#1a1a1a` background fill, BG-01 prerequisite (line 55)
- Codebase: `widgets/calendar/widget.py` — hardcoded `_bg_color`, `_time_color`, `_text_color` (lines 36–38)
- [tomfln/pyqt-colorpicker-widget](https://github.com/tomfln/pyqt-colorpicker-widget) — PyQt5/PyQt6 custom color picker (HSV canvas approach; circular/area design)
- [tomfln/pyqt-colorpicker](https://github.com/tomfln/pyqt-colorpicker) — QDialog-based color picker; modal pattern (rejected for inline use)
- [PySide6 QColorDialog](https://doc.qt.io/qtforpython-6/PySide6/QtWidgets/QColorDialog.html) — Qt native dialog; modal, overkill for this use case
- [PySide6 QColor](https://doc.qt.io/qtforpython-6/PySide6/QtGui/QColor.html) — `QColor.fromHsv(h, s, v)` API for slider-to-swatch conversion
- [Mobbin: Color Picker UI Design](https://mobbin.com/glossary/color-picker) — Design variants: palette, slider, wheel, area; slider is most compact
- [Every Color Picker — Slider picker](https://everycolorpicker.com/pickers/slider-color-picker/) — Slider picker pattern reference
- [yasb status bar](https://github.com/shadowash8/yasb) — PyQt6 Windows bar; CSS-only color config (no GUI picker)
- [Rainmeter](https://www.rainmeter.net/) — Windows widget/skin bar; hex-in-config-file pattern

---

*Feature research for: MonitorControl v1.2 Configurable Colors*
*Researched: 2026-03-27*
