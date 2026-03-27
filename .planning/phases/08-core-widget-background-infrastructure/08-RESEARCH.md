# Phase 8: Core Widget + Background Infrastructure — Research

**Researched:** 2026-03-27
**Domain:** PyQt6 custom widget construction, HSL color math, Pillow RGBA rendering, host compositor paintEvent
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| CPKR-01 | ColorPickerWidget renders hue slider (0–360) and intensity slider (0–100, maps to HSL lightness) with fixed saturation at 0.8 | QWidget overlay + transparent QSlider child; QColor.fromHslF(h/360, 0.8, l/100) for math |
| CPKR-02 | ColorPickerWidget displays a live swatch that updates as sliders are dragged | QWidget subclass overriding paintEvent, calling self.update() on value change |
| CPKR-03 | ColorPickerWidget shows hex field that accepts typed/pasted #RRGGBB input; valid hex moves sliders, invalid hex rejected silently | QRegularExpressionValidator(QRegularExpression(r"#[0-9A-Fa-f]{6}")); editingFinished signal; QColor.isValidColorName() guard |
| CPKR-04 | ColorPickerWidget emits color_changed(str) signal on any value change from user interaction; not on programmatic set_color() calls | pyqtSignal(str); _updating: bool flag to suppress during programmatic sets |
| CPKR-05 | ColorPickerWidget uses colorsys from stdlib — no new pip dependencies | colorsys.hls_to_rgb wrapper or QColor.fromHslF exclusively; stdlib only |
| BG-01 | Host compositor fills full 1920×515 with configurable background color before compositing widget frames | host/window.py paintEvent: painter.fillRect(self.rect(), self._bg_qcolor) |
| BG-02 | All three widgets render on transparent background — no longer hardcode their own bg fill | Change Image.new("RGBA", ..., self._bg_color) to Image.new("RGBA", ..., (0, 0, 0, 0)) in calendar, pomodoro, notification widgets |
</phase_requirements>

---

## Summary

Phase 8 is a self-contained build-and-migrate phase with two distinct deliverables that must land in the same commit: a new `ColorPickerWidget` in `control_panel/color_picker.py`, and an atomic migration of background color ownership from widget subprocesses to `HostWindow.paintEvent`. These two changes are coupled by a practical constraint — if widgets still render opaque backgrounds while the host already fills with a configurable color, the widget frames overwrite that fill on every compositor pass, making the configured color invisible.

The new widget file has zero external dependencies and no coupling to any other v1.2 work. `ColorPickerWidget` can be built and fully unit-tested before any host or widget changes are touched. The background migration is a three-line change across three widget files (swap `(26, 26, 46, 255)` for `(0, 0, 0, 0)`) and a two-line addition to `host/window.py`. The composite change is low risk, high verifiability, and leaves the bar visually identical to v1.1 at the default color.

The most important technical correctness issues are: the `colorsys.hls_to_rgb` argument order trap (takes H, L, S — not H, S, L), the `QColor.hslHueF()` returns -1 for achromatic colors (track `_hue` separately), and the `_updating: bool` flag that must prevent signal loops in bidirectional sync. All three have deterministic fixes described in the Code Examples section.

**Primary recommendation:** Build `ColorPickerWidget` first with unit tests, then migrate background ownership atomically in the same commit as making widgets transparent.

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyQt6 | 6.10.2 (already installed) | QWidget, QSlider, QColor, QRegularExpressionValidator, pyqtSignal | Project-wide Qt layer; no new install |
| colorsys | stdlib | HLS ↔ RGB conversion | No new dependency; CPKR-05 requires stdlib only |
| Pillow (PIL) | already installed | Widget subprocess RGBA frame rendering | Already used by all three widget files |

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyQt6.QtCore.QRegularExpression | 6.10.2 | Hex input validation regex | Import from QtCore — NOT QtGui (Qt6 module split) |
| PyQt6.QtGui.QRegularExpressionValidator | 6.10.2 | Constrain hex input to #RRGGBB format | Import from QtGui — NOT QtCore |
| PIL.ImageColor.getrgb | already installed | Hex-to-RGBA in widget subprocesses | Wrap in `_safe_hex_color()` to prevent subprocess crash |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| colorsys.hls_to_rgb wrapper | QColor.fromHslF exclusively | All-QColor approach eliminates HLS argument-order trap entirely; slightly less transparent math but no risk of wrong argument order |
| QRegularExpressionValidator | No validator + editingFinished guard | Validator gives immediate character-level feedback; guard alone allows typing invalid intermediate states |

**Installation:** No new packages. All dependencies are already in the project environment.

---

## Architecture Patterns

### Recommended Project Structure

```
control_panel/
├── color_picker.py        # NEW — ColorPickerWidget lives HERE ONLY
├── main_window.py         # UNCHANGED in Phase 8
├── config_io.py           # UNCHANGED in Phase 8
└── ...

host/
└── window.py              # MODIFIED — _bg_qcolor attribute + set_bg_color() + paintEvent update

widgets/
├── calendar/widget.py     # MODIFIED — transparent background only
├── pomodoro/widget.py     # MODIFIED — transparent background only
└── notification/widget.py # MODIFIED — transparent background only
```

**Placement rule (CRITICAL):** `ColorPickerWidget` must live in `control_panel/color_picker.py`, never in `shared/`. The `shared/` package is imported by widget subprocesses. PyQt6 imported inside a subprocess spawned via `multiprocessing.spawn` (the Windows default) crashes immediately. Widget subprocesses must remain Qt-free.

### Pattern 1: ColorPickerWidget Internal State

**What:** Track hue, lightness, and saturation as normalized float attributes (0.0–1.0) on the widget. Never derive the canonical hue from `QColor.hslHueF()` at read time — it returns -1 for achromatic colors, which snaps the hue slider to its minimum on round-trip.

**When to use:** Always, for any widget that must survive a round-trip through a gray hex value.

```python
# Source: codebase design + QColor docs (hslHueF achromatic -1 behavior)
class ColorPickerWidget(QWidget):
    color_changed = pyqtSignal(str)   # emits "#rrggbb" string

    def __init__(self, parent=None):
        super().__init__(parent)
        # Canonical state: normalized floats, 0.0–1.0
        self._hue = 0.0          # 0.0–1.0 (never derived from QColor for achromatic)
        self._lightness = 0.5    # 0.0–1.0
        self._saturation = 0.8   # fixed for v1.2
        self._updating = False   # re-entrancy guard for bidirectional sync
```

### Pattern 2: Bidirectional Sync With _updating Guard

**What:** When sliders change, update the hex field; when the hex field changes, update the sliders. Without a guard, each update triggers the other, producing an infinite signal loop.

**When to use:** Any widget with multiple controls representing the same underlying value.

```python
# Source: Qt signal/slot design pattern; _updating guard is the canonical solution
def _on_hue_changed(self, value: int) -> None:
    if self._updating:
        return
    self._hue = value / 360.0
    self._sync_all_from_state()

def _sync_all_from_state(self) -> None:
    """Update all child controls to match internal state. Never emits color_changed."""
    self._updating = True
    try:
        self._hue_slider.setValue(int(self._hue * 360))
        self._lightness_slider.setValue(int(self._lightness * 100))
        self._hex_field.setText(self._current_hex())
        self._swatch.update()  # triggers swatch paintEvent
    finally:
        self._updating = False

def set_color(self, hex_str: str) -> None:
    """Programmatic color set. Does NOT emit color_changed."""
    color = QColor(hex_str)
    if not color.isValid():
        return
    if color.hslHueF() >= 0.0:   # only update hue for chromatic colors
        self._hue = color.hslHueF()
    self._lightness = color.lightnessF()
    self._sync_all_from_state()  # _updating=True inside, no signal emitted
```

### Pattern 3: color_changed Signal Emission

**What:** Emit `color_changed(str)` exactly once per user interaction (drag end or valid hex entry). Never emit on programmatic `set_color()` calls.

**When to use:** Slider drag end (`sliderReleased`) and hex `editingFinished`.

```python
# Source: Qt signal documentation; sliderReleased fires once at drag end
def _setup_signals(self) -> None:
    self._hue_slider.sliderReleased.connect(self._emit_color_changed)
    self._lightness_slider.sliderReleased.connect(self._emit_color_changed)
    self._hex_field.editingFinished.connect(self._on_hex_editing_finished)

def _emit_color_changed(self) -> None:
    """Called at drag-end. Emits color_changed once."""
    if not self._updating:
        self.color_changed.emit(self._current_hex())

def _on_hex_editing_finished(self) -> None:
    """Validate and apply hex input. Emits color_changed on valid input only."""
    if self._updating:
        return
    text = self._hex_field.text()
    color = QColor(text)
    if not color.isValid() or not QColor.isValidColorName(text):
        return  # invalid — leave widget unchanged
    # Valid: update state and emit
    if color.hslHueF() >= 0.0:
        self._hue = color.hslHueF()
    self._lightness = color.lightnessF()
    self._sync_all_from_state()
    self.color_changed.emit(self._current_hex())
```

### Pattern 4: Live Color Swatch

**What:** A `QWidget` subclass that overrides `paintEvent` to fill its rect with the current color. Call `self.update()` to trigger a repaint whenever the color changes.

**When to use:** Any inline color preview. Do not use `setAutoFillBackground + QPalette` — parent stylesheets override the palette, leaving the swatch the wrong color.

```python
# Source: pythonguis.com custom widget paintEvent pattern
class _ColorSwatch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#000000")
        self.setFixedSize(40, 24)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()   # schedule repaint

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)
        painter.end()
```

### Pattern 5: Hex Validation

**What:** Use `QRegularExpressionValidator` from `QtGui` (not `QtCore`) with a `QRegularExpression` from `QtCore` (not `QtGui`). This module split is a Qt6 change from Qt5. Both classes must come from their correct modules or an `ImportError` is raised.

```python
# Source: Qt6 docs — QRegularExpression is in QtCore; QRegularExpressionValidator is in QtGui
from PyQt6.QtCore import QRegularExpression
from PyQt6.QtGui import QRegularExpressionValidator

hex_validator = QRegularExpressionValidator(
    QRegularExpression(r"#[0-9A-Fa-f]{0,6}")
)
self._hex_field = QLineEdit()
self._hex_field.setValidator(hex_validator)
self._hex_field.setMaxLength(7)
self._hex_field.setPlaceholderText("#rrggbb")
```

### Pattern 6: HLS Conversion Wrapper

**What:** When using stdlib `colorsys`, always use a named wrapper that explicitly maps CSS HSL convention (H, S, L in 0–1) to `colorsys.hls_to_rgb(h, l, s)` (H, L, S order). Never write inline positional calls.

```python
# Source: Python stdlib docs — colorsys.hls_to_rgb(h, l, s) takes H, L, S order (NOT H, S, L)
import colorsys

def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    """Convert CSS-convention HSL (h, s, l each 0.0–1.0) to RGB tuple (0–255).

    IMPORTANT: colorsys.hls_to_rgb takes (H, L, S) not (H, S, L).
    This wrapper translates CSS convention to colorsys argument order.
    """
    r, g, b = colorsys.hls_to_rgb(h, l, s)   # note: l and s swapped here
    return (int(r * 255), int(g * 255), int(b * 255))
```

Alternatively (recommended to eliminate risk entirely): use `QColor.fromHslF(h, s, l)` which follows CSS convention and has no argument-order trap.

```python
# Source: PyQt6 docs — QColor.fromHslF(h, s, l) — h=0.0–1.0, s=0.0–1.0, l=0.0–1.0
def _current_qcolor(self) -> QColor:
    return QColor.fromHslF(self._hue, self._saturation, self._lightness)

def _current_hex(self) -> str:
    return self._current_qcolor().name()   # returns "#rrggbb" lowercase
```

### Pattern 7: Host Background Fill

**What:** `HostWindow.paintEvent` must use `self.rect()` (not `event.rect()`) to fill the entire window background. `event.rect()` is only the dirty region — on Windows it is frequently a sub-rectangle, leaving gaps from previous frames.

**Current state:** `host/window.py` line 21 already uses `self.rect()` correctly and fills with `QColor("#000000")`. Phase 8 replaces the hardcoded `"#000000"` with a `self._bg_qcolor` attribute.

```python
# Source: codebase inspection + Qt Forum (event.rect() vs self.rect() Windows partial-fill bug)
# BEFORE (current host/window.py):
painter.fillRect(self.rect(), QColor("#000000"))

# AFTER (Phase 8):
class HostWindow(QWidget):
    def __init__(self):
        super().__init__()
        # ... existing flags ...
        self._bg_qcolor = QColor("#1a1a2e")   # default matches v1.1 hardcoded value

    def set_bg_color(self, hex_str: str) -> None:
        """Update background color. Called by host after config reload."""
        color = QColor(hex_str)
        if color.isValid():
            self._bg_qcolor = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_qcolor)   # self.rect() — not event.rect()
        self.compositor.paint(painter)
        painter.end()
```

### Pattern 8: Widget Transparent Background

**What:** Remove the opaque background fill from all three widget subprocess renderers. Replace `Image.new("RGBA", (W, H), self._bg_color)` with `Image.new("RGBA", (W, H), (0, 0, 0, 0))`.

**CRITICAL:** This change and the host `paintEvent` update must be committed together. A partial state — host has configurable fill but widgets still render `(26, 26, 46, 255)` — causes every compositor pass to overwrite the configured color with the old hardcoded value. The configured color appears to have no effect.

```python
# BEFORE (current in all three widgets):
self._bg_color = (26, 26, 46, 255)  # #1a1a2e
img = Image.new("RGBA", (W, H), self._bg_color)

# AFTER (Phase 8 — all three widget files):
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # transparent; host owns background fill
```

Files to modify:
- `widgets/calendar/widget.py` — remove `self._bg_color` attribute, use `(0, 0, 0, 0)` in all `Image.new` calls (line 51 in `render_frame`)
- `widgets/pomodoro/widget.py` — remove `self._bg_color` attribute, use `(0, 0, 0, 0)` in `render_frame` (line 212)
- `widgets/notification/widget.py` — remove `self._bg_color` attribute, use `(0, 0, 0, 0)` in `_render_notification` (line 134), `_render_idle` (line 209), `_render_permission_placeholder` (line 240)

### Anti-Patterns to Avoid

- **QSlider paintEvent subclassing:** Does not work in Qt. The Qt style system repaints over custom drawing in QSlider.paintEvent. Use QWidget overlay + transparent QSlider child instead.
- **setAutoFillBackground + QPalette for swatch:** Parent stylesheets override the palette. Use paintEvent override instead.
- **Inline colorsys.hls_to_rgb positional calls:** The argument order (H, L, S not H, S, L) is a silent wrong-color trap. Always use a named wrapper.
- **Deriving hue from QColor.hslHueF() on round-trip:** Returns -1 for achromatic colors. Track `_hue` as private float state; only update it from QColor when `hslHueF() >= 0.0`.
- **event.rect() for host background fill:** Only the dirty region. Use `self.rect()` to fill the full window.
- **Placing ColorPickerWidget in shared/:** shared/ is imported by widget subprocesses. PyQt6 in subprocess crashes on Windows spawn. Color picker lives in control_panel/ only.
- **Committing widget transparency without host fill (or vice versa):** Partial migration causes configured color to be silently overwritten every frame.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Hex color validation | Custom character filter | QRegularExpressionValidator | Handles cursor position, paste, clipboard correctly |
| HSL-to-RGB math | Custom formula | colorsys.hls_to_rgb (with wrapper) or QColor.fromHslF | Correct edge cases at hue wraparound, achromatic gray |
| Color string formatting | Custom hex formatter | QColor.name() | Returns "#rrggbb" lowercase, guaranteed valid |
| Hex string parsing | Custom int(hex, 16) parser | QColor(hex_str) + isValid() | Handles case normalization, alpha, named colors correctly |
| Widget repaint scheduling | Explicit update loops | QWidget.update() | Qt coalesces repaints efficiently; direct call is correct |

**Key insight:** Qt's QColor covers the full color parsing and formatting surface. The only hand-rolled piece is the HSL state model (tracking `_hue`, `_lightness`) to preserve hue across achromatic round-trips. Everything else delegates to Qt.

---

## Common Pitfalls

### Pitfall 1: colorsys HLS Argument Order (HIGH — silent wrong color)

**What goes wrong:** `colorsys.hls_to_rgb(h, l, s)` takes lightness second, saturation third. CSS HSL convention and `QColor.fromHslF` both take saturation second and lightness third. Passing the arguments in CSS order silently produces wrong output — no exception, no warning.

**Why it happens:** Python's colorsys module uses HLS (Hue-Lightness-Saturation) order, while CSS and Qt use HSL (Hue-Saturation-Lightness) order.

**How to avoid:** Use a named wrapper that explicitly maps CSS-order parameters to colorsys order, or avoid colorsys entirely and use `QColor.fromHslF(h, s, l)` throughout. Choose one approach before writing any color math and apply it consistently.

**Warning signs:** Colors appear with wrong saturation or lightness (e.g., a bright red renders as a muted pink, or a dark color appears washed out).

### Pitfall 2: Widget Opaque Background Overwrites Host Fill (HIGH — invisible configured color)

**What goes wrong:** Widgets still render with `(26, 26, 46, 255)` alpha=255 Pillow backgrounds. On every compositor pass, `drawImage()` in `Compositor.paint()` paints the widget frame's alpha=255 pixels over the host's background fill. The configured `bg_color` is never visible.

**Why it happens:** Pillow `Image.new("RGBA", ..., (26, 26, 46, 255))` creates fully opaque pixels. Qt's `painter.drawImage()` uses source-over compositing by default; opaque source pixels overwrite the destination entirely.

**How to avoid:** Commit the transparent-background change to all three widgets and the host `set_bg_color` + `paintEvent` change in a single commit. Never leave one half deployed without the other.

**Warning signs:** Bar looks identical to v1.1 even after changing `bg_color` config value.

### Pitfall 3: QColor.hslHueF() Returns -1 for Achromatic Colors (MEDIUM — snaps slider to minimum)

**What goes wrong:** If a user types `#808080` (gray) into the hex field, `QColor("#808080").hslHueF()` returns -1 (achromatic sentinel). If the widget updates `_hue` from this -1 value, the hue slider snaps to position 0 (red). Next time the user drags the lightness slider away from gray, the hue they set earlier is gone.

**Why it happens:** Qt defines hue as undefined for achromatic colors (saturation = 0). The HSL model has no hue at pure gray.

**How to avoid:** In `set_color()` and `_on_hex_editing_finished()`, only update `_hue` when `color.hslHueF() >= 0.0`. Leave `_hue` unchanged for achromatic colors.

**Warning signs:** Hue slider always resets to the leftmost position after the user types a gray hex value.

### Pitfall 4: QRegularExpression/QRegularExpressionValidator Module Split (HIGH — ImportError at startup)

**What goes wrong:** In Qt5, `QRegularExpression` and `QRegularExpressionValidator` were both in `QtGui`. In Qt6, `QRegularExpression` moved to `QtCore`. Importing either class from the wrong module raises `ImportError` immediately on control panel launch.

**Why it happens:** Qt6 reorganized module boundaries. The project uses PyQt6 6.10.2, which follows Qt6 layout.

**How to avoid:** Import `QRegularExpression` from `PyQt6.QtCore` and `QRegularExpressionValidator` from `PyQt6.QtGui`. Both imports must be correct independently.

**Warning signs:** `ImportError: cannot import name 'QRegularExpression' from 'PyQt6.QtGui'` or similar.

### Pitfall 5: Slider Integer Normalization (MEDIUM — off-by-one in color math)

**What goes wrong:** `QSlider` emits integer `valueChanged(int)`. Naively dividing by the slider maximum (e.g., `value / 360`) produces values in `[0.0, 1.0)` but never exactly `1.0`. `QColor.fromHslF` expects hue in `[0.0, 1.0)` (360 degrees = 1.0 is wrapped to 0), but lightness and saturation expect `[0.0, 1.0]`. Division by wrong denominators causes color calculation errors.

**How to avoid:** Hue slider range: 0–359, divide by 360.0. Lightness slider range: 0–100, divide by 100.0. This matches QColor.fromHslF(h, s, l) expectations: h in [0, 1) for 0–360 degrees, l and s in [0, 1].

### Pitfall 6: color_changed Signal Emitted on set_color() (MEDIUM — spurious config writes)

**What goes wrong:** If `color_changed` is emitted during programmatic `set_color()` calls, the control panel's `_load_values()` method triggers `_collect_config()` and `atomic_write_config()` on every panel open. Config is written with no user action.

**Why it happens:** Bidirectional sync wiring connects slider `valueChanged` to signal emission; `set_color()` triggers slider updates which emit signals.

**How to avoid:** Set `self._updating = True` at the top of `set_color()` and in `_sync_all_from_state()`. `_emit_color_changed()` checks `_updating` before emitting. `sliderReleased` (not `valueChanged`) is the signal for drag-end emission, so programmatic slider moves during `_sync_all_from_state` do not trigger emissions.

---

## Code Examples

### Complete ColorPickerWidget Skeleton

```python
# control_panel/color_picker.py
# Source: codebase design; patterns verified against PyQt6 6.10.2 docs

from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLineEdit, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QPainter, QColor, QRegularExpressionValidator


class _ColorSwatch(QWidget):
    """Live color preview square."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#000000")
        self.setFixedSize(40, 24)

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)
        painter.end()


class ColorPickerWidget(QWidget):
    """Reusable hue+intensity color picker for the MonitorControl control panel.

    Emits color_changed(str) on user interaction (drag-end or valid hex entry).
    Does NOT emit on programmatic set_color() calls.
    """
    color_changed = pyqtSignal(str)   # "#rrggbb" lowercase

    SATURATION = 0.8   # fixed for v1.2; not user-adjustable

    def __init__(self, parent=None):
        super().__init__(parent)
        # Canonical internal state (normalized floats, 0.0–1.0)
        self._hue = 0.0
        self._lightness = 0.5
        self._updating = False
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Hue slider
        hue_row = QHBoxLayout()
        hue_row.addWidget(QLabel("Hue"))
        self._hue_slider = QSlider(Qt.Orientation.Horizontal)
        self._hue_slider.setRange(0, 359)
        hue_row.addWidget(self._hue_slider)
        layout.addLayout(hue_row)

        # Intensity (lightness) slider
        intensity_row = QHBoxLayout()
        intensity_row.addWidget(QLabel("Intensity"))
        self._lightness_slider = QSlider(Qt.Orientation.Horizontal)
        self._lightness_slider.setRange(0, 100)
        intensity_row.addWidget(self._lightness_slider)
        layout.addLayout(intensity_row)

        # Swatch + hex field row
        bottom_row = QHBoxLayout()
        self._swatch = _ColorSwatch()
        bottom_row.addWidget(self._swatch)

        self._hex_field = QLineEdit()
        self._hex_field.setValidator(
            QRegularExpressionValidator(QRegularExpression(r"#[0-9A-Fa-f]{0,6}"))
        )
        self._hex_field.setMaxLength(7)
        self._hex_field.setPlaceholderText("#rrggbb")
        bottom_row.addWidget(self._hex_field)
        layout.addLayout(bottom_row)

    def _connect_signals(self) -> None:
        self._hue_slider.valueChanged.connect(self._on_hue_slider_changed)
        self._lightness_slider.valueChanged.connect(self._on_lightness_slider_changed)
        self._hue_slider.sliderReleased.connect(self._emit_color_changed)
        self._lightness_slider.sliderReleased.connect(self._emit_color_changed)
        self._hex_field.editingFinished.connect(self._on_hex_editing_finished)

    # --- Slider handlers ---

    def _on_hue_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self._hue = value / 360.0
        self._sync_swatch_and_hex()

    def _on_lightness_slider_changed(self, value: int) -> None:
        if self._updating:
            return
        self._lightness = value / 100.0
        self._sync_swatch_and_hex()

    def _sync_swatch_and_hex(self) -> None:
        """Update swatch and hex field without moving sliders (avoids re-entrancy)."""
        color = self._current_qcolor()
        self._swatch.set_color(color)
        self._updating = True
        try:
            self._hex_field.setText(color.name())
        finally:
            self._updating = False

    # --- Hex input handler ---

    def _on_hex_editing_finished(self) -> None:
        if self._updating:
            return
        text = self._hex_field.text()
        color = QColor(text)
        if not color.isValid() or not QColor.isValidColorName(text):
            return  # invalid — leave widget unchanged
        if color.hslHueF() >= 0.0:   # only update hue for chromatic colors
            self._hue = color.hslHueF()
        self._lightness = color.lightnessF()
        self._sync_all_from_state()
        self.color_changed.emit(self._current_qcolor().name())

    # --- Full sync ---

    def _sync_all_from_state(self) -> None:
        """Update all child controls from internal state. Never emits color_changed."""
        self._updating = True
        try:
            self._hue_slider.setValue(int(self._hue * 360))
            self._lightness_slider.setValue(int(self._lightness * 100))
            color = self._current_qcolor()
            self._hex_field.setText(color.name())
            self._swatch.set_color(color)
        finally:
            self._updating = False

    def _emit_color_changed(self) -> None:
        """Emit color_changed after drag-end. Guarded by _updating."""
        if not self._updating:
            self.color_changed.emit(self._current_qcolor().name())

    # --- Public API ---

    def color(self) -> str:
        """Return current color as "#rrggbb" string."""
        return self._current_qcolor().name()

    def set_color(self, hex_str: str) -> None:
        """Programmatically set color. Does NOT emit color_changed."""
        color = QColor(hex_str)
        if not color.isValid():
            return
        if color.hslHueF() >= 0.0:
            self._hue = color.hslHueF()
        self._lightness = color.lightnessF()
        self._sync_all_from_state()

    # --- Internal ---

    def _current_qcolor(self) -> QColor:
        """Build QColor from internal state using QColor.fromHslF (no colorsys needed)."""
        return QColor.fromHslF(self._hue, self.SATURATION, self._lightness)
```

### Host Window Modification

```python
# host/window.py — Phase 8 modification
# Source: codebase inspection (current file: 23 lines)

class HostWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self._bg_qcolor = QColor("#1a1a2e")   # default matches v1.1 hardcoded #1a1a2e
        self.compositor = Compositor(self)

    def set_bg_color(self, hex_str: str) -> None:
        """Update background color. Called from host after config reload."""
        color = QColor(hex_str)
        if color.isValid():
            self._bg_qcolor = color
            self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._bg_qcolor)   # self.rect() not event.rect()
        self.compositor.paint(painter)
        painter.end()
```

### Widget Transparent Background Change

```python
# Apply to: widgets/calendar/widget.py, widgets/pomodoro/widget.py,
#            widgets/notification/widget.py

# REMOVE these lines from __init__ in all three widget classes:
self._bg_color = (26, 26, 46, 255)  # #1a1a2e

# CHANGE all Image.new calls in render_frame/_render_* methods:
# BEFORE:
img = Image.new("RGBA", (W, H), self._bg_color)
# AFTER:
img = Image.new("RGBA", (W, H), (0, 0, 0, 0))   # transparent; host owns fill
```

### Test Pattern — ColorPickerWidget Unit Test Skeleton

```python
# tests/test_color_picker.py
# Source: existing test_window.py pattern (qapp fixture, QWidget instantiation)

import pytest
from PyQt6.QtWidgets import QApplication
import sys

@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    return app

class TestColorPickerBidirectional:
    def test_hex_input_moves_sliders(self, qapp):
        from control_panel.color_picker import ColorPickerWidget
        w = ColorPickerWidget()
        w.set_color("#ff0000")   # pure red
        assert w._hue_slider.value() == 0    # red = hue 0
        assert w._lightness_slider.value() == 50  # HSL lightness 0.5 for saturated red

    def test_programmatic_set_does_not_emit(self, qapp):
        from control_panel.color_picker import ColorPickerWidget
        w = ColorPickerWidget()
        emitted = []
        w.color_changed.connect(emitted.append)
        w.set_color("#1a1a2e")
        assert emitted == []   # set_color must not emit

    def test_gray_preserves_hue(self, qapp):
        from control_panel.color_picker import ColorPickerWidget
        w = ColorPickerWidget()
        w.set_color("#ff0000")   # set hue = red
        hue_before = w._hue
        w.set_color("#808080")   # set to gray (achromatic)
        assert w._hue == hue_before  # hue must be preserved, not reset to -1
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| QRegularExpression from QtGui | QRegularExpression from QtCore | Qt6.0 | ImportError if wrong module; affects all Qt6 projects |
| QColor.isValidColor() | QColor.isValidColorName() | Qt6.x deprecation | isValidColor deprecated in Qt6; use isValidColorName |
| QSlider.paintEvent subclass for gradient | QWidget overlay + transparent QSlider | Always (Qt style system) | paintEvent subclass never worked; overlay is canonical Qt workaround |

**Deprecated/outdated:**
- `QColor.isValidColor()`: Deprecated in Qt6. Use `QColor.isValidColorName()` for hex/named strings.
- `QRegularExpression` from `QtGui`: Moved to `QtCore` in Qt6. Import from wrong module raises `ImportError`.

---

## Open Questions

1. **SliderMoved vs sliderReleased for emit timing**
   - What we know: `sliderReleased` fires once at drag end. `sliderMoved` fires during drag (live preview).
   - What's unclear: Whether the live swatch should update during drag (yes — `valueChanged` drives swatch) vs whether `color_changed` should fire during drag (no — spec says drag-end only).
   - Recommendation: Use `valueChanged` to update the swatch (CPKR-02 says "live"), use `sliderReleased` for `color_changed` emission (CPKR-04 says "drag end"). These serve different purposes and both are needed.

2. **Notification widget bg_color: BG-02 scope**
   - What we know: BG-02 says "all three widgets render on transparent background." NotificationWidget has `self._bg_color` used in three separate render methods (`_render_notification`, `_render_idle`, `_render_permission_placeholder`).
   - What's unclear: Whether BG-02 includes the notification widget or only pomodoro + calendar.
   - Recommendation: Include it. "All three" in BG-02 = all three widget subprocesses. The notification widget has the same `_bg_color = (26, 26, 46, 255)` pattern and must be made transparent to prevent overwriting the host fill.

3. **Achromatic lightness round-trip: `lightnessF()` precision**
   - What we know: `QColor("#1a1a2e").lightnessF()` should return approximately 0.135 (the L in HSL for that dark blue).
   - What's unclear: Whether `QColor.fromHslF(h, s, l).name()` round-trips exactly or introduces floating-point rounding to adjacent hex values.
   - Recommendation: Write a unit test: `assert ColorPickerWidget._current_hex() == "#1a1a2e"` after `set_color("#1a1a2e")`. If there is rounding, use `QColor(hex).name()` output as the canonical form (QColor normalizes hex).

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (pytest.ini present at project root) |
| Config file | `pytest.ini` — `testpaths = tests` |
| Quick run command | `pytest tests/test_color_picker.py -x` |
| Full suite command | `pytest tests/ -m "not integration"` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CPKR-01 | Widget renders hue and intensity sliders | unit | `pytest tests/test_color_picker.py::TestColorPickerStructure -x` | ❌ Wave 0 |
| CPKR-02 | Live swatch updates as sliders dragged | unit | `pytest tests/test_color_picker.py::TestColorPickerBidirectional::test_swatch_updates -x` | ❌ Wave 0 |
| CPKR-03 | Valid hex moves sliders; invalid hex rejected silently | unit | `pytest tests/test_color_picker.py::TestColorPickerHexInput -x` | ❌ Wave 0 |
| CPKR-04 | color_changed emits once on interaction; never on set_color() | unit | `pytest tests/test_color_picker.py::TestColorPickerSignal -x` | ❌ Wave 0 |
| CPKR-05 | No new pip dependencies (colorsys only) | structural | Verified by inspection — no new imports in color_picker.py | N/A |
| BG-01 | Host fills full window with configurable QColor | unit | `pytest tests/test_window.py -x` | ✅ (extend existing) |
| BG-02 | All widgets render on transparent background | unit | `pytest tests/test_compositor.py::test_transparent_widget_bg -x` | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `pytest tests/test_color_picker.py -x`
- **Per wave merge:** `pytest tests/ -m "not integration"`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `tests/test_color_picker.py` — covers CPKR-01 through CPKR-04 (structure, swatch, hex input, signal behavior)
- [ ] Extend `tests/test_window.py` — add `TestWindowBgColor` class covering `set_bg_color()` and `_bg_qcolor` default

*(Existing `tests/test_compositor.py` transparent-background test can be added to existing file without a Wave 0 gap since the file already exists; add one test verifying that a transparent RGBA frame composites correctly over the host fill.)*

---

## Sources

### Primary (HIGH confidence)

- Codebase direct inspection — `host/window.py`, `host/compositor.py`, `widgets/calendar/widget.py`, `widgets/pomodoro/widget.py`, `widgets/notification/widget.py`, `control_panel/main_window.py`, `control_panel/config_io.py`, `shared/message_schema.py`
- `.planning/research/SUMMARY.md` — milestone-level research synthesis (HIGH confidence, cross-referenced against PyQt6 and Python docs)
- `.planning/STATE.md` — locked architectural decisions for v1.2
- Python official docs — `colorsys.hls_to_rgb(h, l, s)` argument order (H, L, S); all inputs 0.0–1.0

### Secondary (MEDIUM confidence)

- Qt Forum — `event.rect()` vs `self.rect()` partial-fill bug on Windows (confirmed PyQt6-specific)
- pythonguis.com — custom `QWidget.paintEvent` override pattern for live color swatch

### Tertiary (LOW confidence)

- None for this phase — all critical claims have PRIMARY or SECONDARY sources.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already installed; no new packages; APIs verified in SUMMARY.md against PyQt6 6.10.2 docs
- Architecture: HIGH — all integration points inspected directly in source files; 5 files read at codebase level
- Pitfalls: HIGH (pitfalls 1–4) / MEDIUM (pitfall 5 slider normalization, pitfall 6 spurious emit) — core pitfalls verified in SUMMARY.md against official docs; normalization and signal-timing pitfalls are well-understood Qt patterns

**Research date:** 2026-03-27
**Valid until:** 2026-04-27 (stable Qt6 + Python stdlib; no fast-moving dependencies)
