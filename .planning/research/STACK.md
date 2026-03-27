# Stack Research

**Domain:** Python desktop widget/dashboard framework — Windows, dedicated secondary display
**Researched:** 2026-03-27
**Confidence:** HIGH (all APIs verified against official Qt6 documentation and PyQt6 source)

---

## Scope

This file covers ONLY the new stack capabilities needed for v1.2 configurable colors. The existing
validated stack (PyQt6 6.10.2, Pillow, pywin32 311, winrt-* 3.2.1, multiprocessing.Queue,
config.json hot-reload, PyInstaller 6.19.0) is not re-researched.

The new capabilities required are:
1. Hue/intensity sliders with visible gradient groove (not plain grey bars)
2. Live color swatch (a painted rectangle that updates in real time)
3. Hex input field with `#RRGGBB` validation
4. HSL-to-RGB conversion for the slider model → hex → config pipeline
5. Host background fill driven by a `bg_color` string from config

---

## Recommended Stack

### New Core Technologies

No new packages are needed. All v1.2 color capabilities are covered by PyQt6 6.10.2 and
Python's stdlib `colorsys`.

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `colorsys` (stdlib) | built-in (Python 3.x) | HSL-to-RGB and RGB-to-HSL conversion | Already identified in milestone context. Provides `hls_to_rgb(h, l, s)` and `rgb_to_hls(r, g, b)` — all floats in [0.0, 1.0]. No external dependency. Sufficient for slider model → QColor conversion; no precision issues at 8-bit display depth. |
| PyQt6 — `QSlider` | 6.10.2 (already installed) | Hue and intensity slider controls | Inherits from `QAbstractSlider`. Provides `valueChanged` signal, `setRange()`, `setValue()`, `value()`, horizontal/vertical orientation. Styling the gradient groove requires a stylesheet override on the `::groove:horizontal` subcontrol — see patterns below. |
| PyQt6 — `QColor` | 6.10.2 (already installed) | Color construction from HSV/HSL and hex round-trip | `QColor.fromHslF(h, s, l)` constructs from float HSL. `QColor.name()` returns `#RRGGBB`. `QColor.isValidColorName(s)` validates a hex string without constructing an object. Used in the swatch painter and for writing clean hex to config.json. |
| PyQt6 — `QPainter` / `QLinearGradient` | 6.10.2 (already installed) | Gradient groove background for sliders; live swatch fill | `QLinearGradient` with `setColorAt()` stops draws the hue spectrum or grey-to-color intensity ramp. `painter.fillRect(self.rect(), gradient_brush)` paints the swatch. Already used in host `compositor.py` — same pattern. |
| PyQt6 — `QRegularExpressionValidator` | 6.10.2 (already installed) | Constrain hex input field to `#RRGGBB` pattern | In PyQt6 `QRegularExpressionValidator` lives in `QtGui`; `QRegularExpression` lives in `QtCore`. This split is a Qt6 change — in Qt5 both were in `QtGui`. Use `QRegularExpression` from `QtCore` to construct the pattern and pass it to `QRegularExpressionValidator`. |

### Supporting Libraries

None needed. All rendering, input validation, and color math is covered by PyQt6 + stdlib.

---

## Installation

No new packages. All capabilities come from the existing install:

```bash
# Already installed — no changes to requirements.txt
PyQt6==6.10.2
# colorsys is stdlib — no install needed
```

---

## Key Patterns

### Pattern 1: QSlider with gradient groove via stylesheet

Subclassing `QSlider` and overriding `paintEvent()` does not work reliably — the style system
draws over custom painting. The correct approach is a `QWidget` subclass that:

1. Paints the gradient groove background in `paintEvent()` on the widget itself (not on the slider)
2. Overlays a transparent `QSlider` child positioned exactly over the groove

The child QSlider is styled to have a transparent groove and a visible handle only:

```python
from PyQt6.QtWidgets import QWidget, QSlider
from PyQt6.QtGui import QPainter, QLinearGradient, QColor, QBrush
from PyQt6.QtCore import Qt, QRect, pyqtSignal

class HueSlider(QWidget):
    """QWidget that paints a hue-spectrum groove with a QSlider overlay for the handle."""
    hue_changed = pyqtSignal(float)  # 0.0..1.0

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(28)
        self._slider = QSlider(Qt.Orientation.Horizontal, self)
        self._slider.setRange(0, 359)
        self._slider.setStyleSheet("""
            QSlider::groove:horizontal { background: transparent; height: 16px; }
            QSlider::handle:horizontal {
                background: white;
                border: 1px solid #555;
                width: 12px;
                margin: -4px 0;
                border-radius: 6px;
            }
        """)
        self._slider.valueChanged.connect(
            lambda v: self.hue_changed.emit(v / 359.0)
        )

    def resizeEvent(self, event):
        self._slider.setGeometry(self.rect())

    def paintEvent(self, event):
        painter = QPainter(self)
        groove = QRect(0, (self.height() - 16) // 2, self.width(), 16)
        grad = QLinearGradient(groove.topLeft(), groove.topRight())
        for stop in range(7):
            grad.setColorAt(stop / 6.0, QColor.fromHsvF(stop / 6.0, 1.0, 1.0))
        painter.fillRect(groove, QBrush(grad))
        painter.end()
```

The same structure applies for the intensity slider — replace the gradient stops with a ramp from
black → the current hue's full saturation color.

**Critical gotcha:** Always use `self.rect()` (not `event.rect()`) when painting the full widget
background. `event.rect()` is only the dirty region and will leave unpainted gaps at certain
widget sizes on Windows. This bug was confirmed in the Qt Forum
(`pyqt6-windows-os-custom-paintevent-doesn-t-fill-the-whole-widget-background-in-some-size`).

### Pattern 2: Live color swatch

A swatch is a plain `QWidget` subclass that overrides `paintEvent()` to fill its rect with the
current color. Update by calling `update()` after changing `self._color`:

```python
class ColorSwatch(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(32, 32)
        self._color = QColor("#000000")

    def set_color(self, color: QColor) -> None:
        self._color = color
        self.update()  # triggers paintEvent

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), self._color)
        painter.end()
```

Do NOT use `setAutoFillBackground(True)` with `QPalette` for a live swatch — palette changes
can be overridden by the parent's stylesheet. A direct `paintEvent()` override is reliable.

### Pattern 3: Hex input validation

`QRegularExpression` lives in `QtCore` (not `QtGui`) in PyQt6. `QRegularExpressionValidator`
lives in `QtGui`. This split is a Qt6 change from Qt5 where both were in `QtGui`.

```python
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QRegularExpressionValidator
from PyQt6.QtCore import QRegularExpression

hex_re = QRegularExpression(r'^#[0-9A-Fa-f]{6}$')
validator = QRegularExpressionValidator(hex_re)
line_edit.setValidator(validator)
```

`QRegularExpressionValidator` automatically wraps the pattern in `\A`/`\z` anchors — do NOT
double-anchor the pattern yourself. However, the validator allows "Intermediate" states during
typing (e.g., `#FF` is intermediate, not invalid), so `line_edit.hasAcceptableInput()` or
`editingFinished` should gate saving.

For pre-validation of a full hex string without constructing a QColor:

```python
QColor.isValidColorName("#ff4444")  # returns True; preferred over deprecated isValidColor()
```

### Pattern 4: colorsys HSL model → QColor

colorsys uses `hls_to_rgb(h, l, s)` — note the argument order is **H, L, S** (not H, S, L).
QColor uses H, S, L order in `fromHslF(h, s, l)`. This transposition is a common bug source.

```python
import colorsys

# Slider values: hue [0.0, 1.0], intensity [0.0, 1.0]
# Fixed saturation = 1.0 (full saturation model)
def hsl_to_hex(hue: float, intensity: float, saturation: float = 1.0) -> str:
    # colorsys.hls_to_rgb takes (h, LIGHTNESS, saturation) — L is 2nd arg
    r, g, b = colorsys.hls_to_rgb(hue, intensity, saturation)
    return QColor(int(r * 255), int(g * 255), int(b * 255)).name()

# Reverse: hex → slider values
def hex_to_hsl(hex_str: str) -> tuple[float, float, float]:
    c = QColor(hex_str)
    r, g, b = c.redF(), c.greenF(), c.blueF()
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h, l, s  # hue, lightness (intensity), saturation
```

Using `QColor.fromHslF()` directly (bypassing colorsys) is equally valid and avoids the HLS
argument order trap. Either approach is fine; pick one and be consistent:

```python
# Alternative: all-QColor approach (avoids colorsys HLS arg-order trap)
def hsl_to_hex(hue: float, intensity: float) -> str:
    return QColor.fromHslF(hue, 1.0, intensity).name()
```

### Pattern 5: Host background fill from config

The existing `HostWindow.paintEvent()` already calls `painter.fillRect(self.rect(), QColor("#000000"))`.
Changing `bg_color` requires only replacing the hardcoded literal with `QColor(self._bg_color)`.
`QColor` accepts `#RRGGBB` strings in its constructor — no parse step needed.

```python
# In HostWindow.paintEvent():
painter.fillRect(self.rect(), QColor(self._bg_color))  # self._bg_color from config hot-reload
```

Widget backgrounds become transparent: Pillow `Image.new("RGBA", (w, h), (0, 0, 0, 0))` and
the host composites them over the filled background. This already works because the compositor
uses `Format_RGBA8888` — per-pixel alpha is already respected.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Custom `QWidget` + transparent `QSlider` overlay for gradient groove | `QSlider` subclass overriding `paintEvent()` | Never — the style system draws over custom painting in QSlider subclasses; the overlay pattern is the documented workaround |
| `colorsys.hls_to_rgb` or `QColor.fromHslF` for color math | Third-party `colour-science` or `colormath` packages | Only if ICC profile handling, perceptual uniformity (CIECAM02, Oklab), or wide-gamut conversion is needed — none of which apply here |
| `QRegularExpressionValidator` for hex input | Regex in `editingFinished` handler | `QRegularExpressionValidator` prevents invalid characters from being entered at all; handler-only validation allows typing garbage and correcting on save, which is worse UX |
| `QColor.isValidColorName()` for hex validation | `QColor(s).isValid()` | Both work; `isValidColorName()` is the current preferred API (`isValidColor()` is deprecated) |
| `painter.fillRect(self.rect(), color)` for swatch | `setAutoFillBackground(True)` + palette | Palette approach is overridden by parent stylesheets; `paintEvent` override is reliable |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Subclassing `QSlider` and overriding `paintEvent()` | Style system repaints over custom drawing; custom content appears underneath or is invisible | `QWidget` subclass with painted groove + transparent `QSlider` child overlay |
| `colorsys.hls_to_rgb(h, s, l)` with S before L | colorsys argument order is `(h, LIGHTNESS, saturation)` — L is the second argument; swapping S and L produces wrong colors silently | `colorsys.hls_to_rgb(h, l, s)` or use `QColor.fromHslF(h, s, l)` (QColor's order is H, S, L) |
| `QRegularExpression` from `QtGui` | In PyQt6, `QRegularExpression` moved to `QtCore`; importing from `QtGui` raises `ImportError` | `from PyQt6.QtCore import QRegularExpression` |
| `isValidColor()` (deprecated) | Deprecated in Qt6; use `isValidColorName()` | `QColor.isValidColorName(s)` |
| Third-party color picker packages (`pyqt-colorpicker`, `pyqtpicker`) | Add a dependency for functionality achievable with ~80 lines of PyQt6; not packaged for PyInstaller without additional hooks | Inline `ColorPickerWidget` built from `QWidget` + `QSlider` + `QLineEdit` |
| `event.rect()` in `paintEvent()` for full-widget fill | Only covers the dirty region; leaves unpainted gaps at certain widget sizes on Windows | `self.rect()` always returns the full widget rectangle |
| QColorDialog | Launches a separate modal dialog — breaks the inline tab form UX; not reusable as an embedded widget | Inline `ColorPickerWidget` with sliders + swatch + hex field |

---

## Stack Patterns by Variant

**If `bg_color` or widget color is missing from config on upgrade:**
- Fall back to the current hardcoded value (CLR-01 requirement: zero visual change on upgrade)
- `config.get("bg_color", "#000000")` for host background
- Widget settings use `settings.get("time_color", "#ffffff")` etc.

**If the all-QColor approach is used instead of colorsys:**
- `QColor.fromHslF(hue, saturation, lightness)` — QColor HSL argument order is H, S, L
- `c.hslHueF()`, `c.hslSaturationF()`, `c.lightnessF()` — round-trip back to slider values
- This eliminates the colorsys HLS argument-order trap entirely

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| PyQt6 6.10.2 | `colorsys` (stdlib) | Pure Python interfaces — no compatibility concern |
| PyQt6 6.10.2 | `QRegularExpressionValidator` (QtGui) + `QRegularExpression` (QtCore) | This module split is stable since Qt6.0; confirmed in PyQt6 6.10.2 docs |
| PyQt6 6.10.2 | `QColor.fromHslF`, `QColor.fromHsvF` | Available since Qt4; stable; confirmed in PyQt6 6.10.2 Riverbank docs |
| PyInstaller 6.19.0 | `ColorPickerWidget` (pure PyQt6) | No new modules to collect; PyInstaller's existing PyQt6 hook covers everything |

---

## Sources

- [PyQt6 QColor API — Riverbank Computing](https://www.riverbankcomputing.com/static/Docs/PyQt6/api/qtgui/qcolor.html) — `isValidColor` deprecated; `isValidColorName` preferred; `fromHslF`, `fromHsvF` signatures; `name(NameFormat)` — HIGH confidence
- [Qt6 QColor Class Reference](https://doc.qt.io/qt-6/qcolor.html) — `fromHsv(h,s,v,a)` 0-359 hue, 0-255 others; `fromHslF` float variant; `name()` returns `#RRGGBB`; internal 16-bit precision note — HIGH confidence
- [Qt6 QSlider Class Reference](https://doc.qt.io/qt-6/qslider.html) — `valueChanged` signal, `setValue`, `setRange`, `setOrientation`; `paintEvent` and `initStyleOption` protected; stylesheet subcontrol guidance — HIGH confidence
- [Qt6 Stylesheet Examples — Customizing QSlider](https://doc.qt.io/qt-6/stylesheet-examples.html#customizing-qslider) — `::groove:horizontal`, `::handle:horizontal`, `::add-page`, `::sub-page` subcontrol syntax; `qlineargradient` in stylesheet — HIGH confidence
- [Qt6 QRegularExpressionValidator](https://doc.qt.io/qt-6/qregularexpressionvalidator.html) — auto-anchors pattern; Acceptable/Intermediate/Invalid states; lives in QtGui — HIGH confidence
- [PySide6 QRegularExpression — QtCore](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QRegularExpression.html) — confirmed in QtCore (not QtGui) in Qt6 — HIGH confidence
- [linux-nerds.org — PyQt6 QRegularExpressionValidator](https://linux-nerds.org/topic/1135/pyqt6-qregularexpressionvalidator) — `from PyQt6.QtCore import QRegularExpression` / `from PyQt6.QtGui import QRegularExpressionValidator` split confirmed in PyQt6 — HIGH confidence
- [Qt Forum — PyQt6 Windows paintEvent not filling whole widget](https://forum.qt.io/topic/128153/pyqt6-windows-os-custom-paintevent-doesn-t-fill-the-whole-widget-background-in-some-size) — `event.rect()` vs `self.rect()` bug on Windows confirmed; use `self.rect()` for full-widget fill — HIGH confidence
- [pythonguis.com — Creating Custom Widgets in PyQt6](https://www.pythonguis.com/tutorials/pyqt6-creating-your-own-custom-widgets/) — `paintEvent` pattern, `update()` trigger requirement, Y-axis orientation, `setSizePolicy` — MEDIUM confidence
- [runebook.dev — Customizing QSlider: From Stylesheets to Proxies](https://runebook.dev/en/docs/qt/qslider/paintEvent) — confirmed `paintEvent` subclassing does not work; stylesheet or widget composition is required — MEDIUM confidence (secondary source, consistent with official docs)
- [Python docs — colorsys](https://docs.python.org/3/library/colorsys.html) — `hls_to_rgb(h, l, s)` argument order (L before S), float [0.0, 1.0] all args — HIGH confidence

---

*Stack research for: MonitorControl v1.2 — Configurable color system additions*
*Researched: 2026-03-27*
