"""ColorPickerWidget — reusable hue/intensity color picker for MonitorControl control panel.

Provides a hue slider (0-359), intensity/lightness slider (0-100), live color swatch,
and a hex input field. Emits color_changed(str) on user interaction; never on
programmatic set_color() calls.

No new pip dependencies — uses only PyQt6 (already installed) and stdlib.
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QSlider, QLineEdit, QLabel
from PyQt6.QtCore import Qt, pyqtSignal, QRegularExpression
from PyQt6.QtGui import QPainter, QColor, QRegularExpressionValidator


class _ColorSwatch(QWidget):
    """Live color preview square. Private helper for ColorPickerWidget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._color = QColor("#000000")
        self.setFixedSize(40, 24)

    def set_color(self, color: QColor) -> None:
        """Update displayed color and schedule a repaint."""
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

    Internal state is stored as normalized floats (_hue, _lightness) so that
    achromatic round-trips (gray hex values) preserve the previously set hue.
    QColor.fromHslF is used exclusively — no colorsys import needed.
    """

    color_changed = pyqtSignal(str)  # emits "#rrggbb" lowercase

    SATURATION = 0.8  # fixed for v1.2; not user-adjustable

    def __init__(self, parent=None):
        super().__init__(parent)
        # Canonical internal state: normalized floats, 0.0–1.0
        self._hue = 0.0          # 0.0–1.0; never derived from QColor for achromatic colors
        self._lightness = 0.5    # 0.0–1.0
        self._updating = False   # re-entrancy guard for bidirectional sync
        self._build_ui()
        self._connect_signals()

    # -------------------------------------------------------------------------
    # UI construction
    # -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Hue slider row
        hue_row = QHBoxLayout()
        hue_row.addWidget(QLabel("Hue"))
        self._hue_slider = QSlider(Qt.Orientation.Horizontal)
        self._hue_slider.setRange(0, 359)
        hue_row.addWidget(self._hue_slider)
        layout.addLayout(hue_row)

        # Intensity (lightness) slider row
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

    # -------------------------------------------------------------------------
    # Slider handlers
    # -------------------------------------------------------------------------

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
        """Update swatch and hex field without touching sliders (avoids re-entrancy)."""
        color = self._current_qcolor()
        self._swatch.set_color(color)
        self._updating = True
        try:
            self._hex_field.setText(color.name())
        finally:
            self._updating = False

    # -------------------------------------------------------------------------
    # Hex input handler
    # -------------------------------------------------------------------------

    def _on_hex_editing_finished(self) -> None:
        if self._updating:
            return
        text = self._hex_field.text()
        color = QColor(text)
        if not color.isValid() or not QColor.isValidColorName(text):
            return  # invalid — leave widget unchanged
        if color.hslHueF() >= 0.0:  # only update hue for chromatic colors
            self._hue = color.hslHueF()
        self._lightness = color.lightnessF()
        self._sync_all_from_state()
        self.color_changed.emit(self._current_qcolor().name())

    # -------------------------------------------------------------------------
    # Full state sync
    # -------------------------------------------------------------------------

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
        """Emit color_changed after a drag-end. Guarded against programmatic updates."""
        if not self._updating:
            self.color_changed.emit(self._current_qcolor().name())

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def color(self) -> str:
        """Return current color as a '#rrggbb' lowercase hex string."""
        return self._current_qcolor().name()

    def set_color(self, hex_str: str) -> None:
        """Programmatically set color. Does NOT emit color_changed.

        Achromatic colors (e.g. gray) preserve the previously set hue value.
        Invalid hex strings are silently ignored.
        """
        color = QColor(hex_str)
        if not color.isValid():
            return
        if color.hslHueF() >= 0.0:  # only update hue for chromatic colors
            self._hue = color.hslHueF()
        self._lightness = color.lightnessF()
        self._sync_all_from_state()

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _current_qcolor(self) -> QColor:
        """Build QColor from internal state using QColor.fromHslF (no colorsys needed)."""
        return QColor.fromHslF(self._hue, self.SATURATION, self._lightness)
