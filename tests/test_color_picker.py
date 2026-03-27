"""Tests for ColorPickerWidget — CPKR-01 through CPKR-04."""
import pytest


@pytest.fixture(scope="module")
def qapp():
    """Minimal QApplication needed to instantiate QWidget subclasses."""
    import sys
    from PyQt6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)
    return app


class TestColorPickerStructure:
    """CPKR-01, CPKR-02, CPKR-03: Structural checks — all four child controls exist."""

    def test_has_hue_slider(self, qapp):
        """widget._hue_slider exists, is QSlider, range 0-359."""
        from control_panel.color_picker import ColorPickerWidget
        from PyQt6.QtWidgets import QSlider
        widget = ColorPickerWidget()
        assert hasattr(widget, "_hue_slider"), "_hue_slider attribute must exist"
        assert isinstance(widget._hue_slider, QSlider), "_hue_slider must be QSlider"
        assert widget._hue_slider.minimum() == 0
        assert widget._hue_slider.maximum() == 359

    def test_has_lightness_slider(self, qapp):
        """widget._lightness_slider exists, is QSlider, range 0-100."""
        from control_panel.color_picker import ColorPickerWidget
        from PyQt6.QtWidgets import QSlider
        widget = ColorPickerWidget()
        assert hasattr(widget, "_lightness_slider"), "_lightness_slider attribute must exist"
        assert isinstance(widget._lightness_slider, QSlider), "_lightness_slider must be QSlider"
        assert widget._lightness_slider.minimum() == 0
        assert widget._lightness_slider.maximum() == 100

    def test_has_swatch(self, qapp):
        """widget._swatch exists, is _ColorSwatch (QWidget subclass)."""
        from control_panel.color_picker import ColorPickerWidget, _ColorSwatch
        from PyQt6.QtWidgets import QWidget
        widget = ColorPickerWidget()
        assert hasattr(widget, "_swatch"), "_swatch attribute must exist"
        assert isinstance(widget._swatch, _ColorSwatch), "_swatch must be _ColorSwatch"
        assert isinstance(widget._swatch, QWidget), "_ColorSwatch must be a QWidget subclass"

    def test_has_hex_field(self, qapp):
        """widget._hex_field exists, is QLineEdit, has validator."""
        from control_panel.color_picker import ColorPickerWidget
        from PyQt6.QtWidgets import QLineEdit
        widget = ColorPickerWidget()
        assert hasattr(widget, "_hex_field"), "_hex_field attribute must exist"
        assert isinstance(widget._hex_field, QLineEdit), "_hex_field must be QLineEdit"
        assert widget._hex_field.validator() is not None, "_hex_field must have a validator"


class TestColorPickerBidirectional:
    """CPKR-01 + CPKR-02: Bidirectional sync between sliders, swatch, and hex field."""

    def test_hex_input_moves_sliders(self, qapp):
        """set_color('#ff0000') makes hue_slider.value()==0 and lightness_slider.value()==50."""
        from control_panel.color_picker import ColorPickerWidget
        widget = ColorPickerWidget()
        widget.set_color("#ff0000")
        assert widget._hue_slider.value() == 0, (
            f"Hue slider should be 0 for red, got {widget._hue_slider.value()}"
        )
        assert widget._lightness_slider.value() == 50, (
            f"Lightness slider should be 50 for red, got {widget._lightness_slider.value()}"
        )

    def test_swatch_updates(self, qapp):
        """After set_color('#ff0000'), swatch._color.name() == QColor.fromHslF(0.0, 0.8, 0.5).name()."""
        from control_panel.color_picker import ColorPickerWidget
        from PyQt6.QtGui import QColor
        widget = ColorPickerWidget()
        widget.set_color("#ff0000")
        expected = QColor.fromHslF(0.0, 0.8, 0.5).name()
        assert widget._swatch._color.name() == expected, (
            f"Swatch color should be {expected}, got {widget._swatch._color.name()}"
        )

    def test_slider_updates_hex(self, qapp):
        """Setting hue_slider to 120 and lightness_slider to 50 makes hex_field.text() match
        QColor.fromHslF(120/360, 0.8, 0.5).name()."""
        from control_panel.color_picker import ColorPickerWidget
        from PyQt6.QtGui import QColor
        widget = ColorPickerWidget()
        widget._hue_slider.setValue(120)
        widget._lightness_slider.setValue(50)
        expected = QColor.fromHslF(120 / 360.0, 0.8, 0.5).name()
        assert widget._hex_field.text() == expected, (
            f"Hex field should be {expected}, got {widget._hex_field.text()!r}"
        )


class TestColorPickerHexInput:
    """CPKR-03: Hex field accepts valid input and rejects invalid input."""

    def test_valid_hex_accepted(self, qapp):
        """set_color('#00ff00') changes color(); color() returns a valid hex string."""
        from control_panel.color_picker import ColorPickerWidget
        widget = ColorPickerWidget()
        widget.set_color("#00ff00")
        result = widget.color()
        assert result.startswith("#"), f"color() must return a hex string, got {result!r}"
        assert len(result) == 7, f"color() must return a 7-char hex string, got {result!r}"

    def test_invalid_hex_rejected(self, qapp):
        """set_color('notacolor') leaves widget unchanged; color() returns prior value."""
        from control_panel.color_picker import ColorPickerWidget
        widget = ColorPickerWidget()
        widget.set_color("#ff0000")
        prior = widget.color()
        widget.set_color("notacolor")
        assert widget.color() == prior, (
            f"Invalid input should leave color unchanged, was {prior!r}, got {widget.color()!r}"
        )

    def test_gray_preserves_hue(self, qapp):
        """set_color('#ff0000'), record _hue, set_color('#808080'), _hue unchanged."""
        from control_panel.color_picker import ColorPickerWidget
        widget = ColorPickerWidget()
        widget.set_color("#ff0000")
        hue_before = widget._hue
        widget.set_color("#808080")
        assert widget._hue == hue_before, (
            f"Gray input should not change _hue. Before: {hue_before}, after: {widget._hue}"
        )


class TestColorPickerSignal:
    """CPKR-04: color_changed(str) signal emission rules."""

    def test_programmatic_set_does_not_emit(self, qapp):
        """Connect color_changed to list.append; set_color('#1a1a2e'); list is empty."""
        from control_panel.color_picker import ColorPickerWidget
        widget = ColorPickerWidget()
        emissions = []
        widget.color_changed.connect(emissions.append)
        widget.set_color("#1a1a2e")
        assert emissions == [], (
            f"set_color() must not emit color_changed, got {emissions}"
        )

    def test_slider_released_emits(self, qapp):
        """Simulate sliderReleased on hue_slider; exactly one emission."""
        from control_panel.color_picker import ColorPickerWidget
        widget = ColorPickerWidget()
        emissions = []
        widget.color_changed.connect(emissions.append)
        widget._hue_slider.sliderReleased.emit()
        assert len(emissions) == 1, (
            f"sliderReleased should emit color_changed exactly once, got {len(emissions)} emissions"
        )
