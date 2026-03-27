"""ControlPanelWindow — tab-based configuration UI for MonitorControl.

The control panel is the sole writer of config.json. On Save, it calls
atomic_write_config which triggers the host's QFileSystemWatcher hot-reload.
"""
import copy
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QMessageBox,
)
from control_panel.config_io import load_config, atomic_write_config


class ControlPanelWindow(QMainWindow):
    def __init__(self, config_path: str):
        super().__init__()
        self._config_path = config_path
        self._config = load_config(config_path)
        self.setWindowTitle("MonitorControl \u2014 Settings")
        self.setMinimumWidth(480)
        self.setMinimumHeight(400)
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_layout_tab(), "Layout")
        self._tabs.addTab(self._build_pomodoro_tab(), "Pomodoro")
        self._tabs.addTab(self._build_calendar_tab(), "Calendar")
        root_layout.addWidget(self._tabs)

        # Save button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        root_layout.addLayout(btn_row)

    def _build_layout_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        group = QGroupBox("Display")
        form = QFormLayout(group)

        self._display_width = QSpinBox()
        self._display_width.setRange(100, 7680)
        form.addRow("Width:", self._display_width)

        self._display_height = QSpinBox()
        self._display_height.setRange(100, 4320)
        form.addRow("Height:", self._display_height)

        layout.addWidget(group)
        layout.addStretch()
        return container

    def _build_pomodoro_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        group = QGroupBox("Pomodoro Durations")
        form = QFormLayout(group)

        self._pomo_work = QSpinBox()
        self._pomo_work.setRange(1, 120)
        self._pomo_work.setSuffix(" min")
        form.addRow("Work:", self._pomo_work)

        self._pomo_short_break = QSpinBox()
        self._pomo_short_break.setRange(1, 30)
        self._pomo_short_break.setSuffix(" min")
        form.addRow("Short Break:", self._pomo_short_break)

        self._pomo_long_break = QSpinBox()
        self._pomo_long_break.setRange(1, 60)
        self._pomo_long_break.setSuffix(" min")
        form.addRow("Long Break:", self._pomo_long_break)

        self._pomo_cycles = QSpinBox()
        self._pomo_cycles.setRange(1, 10)
        form.addRow("Cycles before long break:", self._pomo_cycles)

        layout.addWidget(group)
        layout.addStretch()
        return container

    def _build_calendar_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        group = QGroupBox("Clock Settings")
        form = QFormLayout(group)

        self._clock_format = QComboBox()
        self._clock_format.addItems(["12h", "24h"])
        form.addRow("Clock Format:", self._clock_format)

        layout.addWidget(group)
        layout.addStretch()
        return container

    def _load_values(self) -> None:
        """Populate form fields from self._config."""
        display = self._config.get("layout", {}).get("display", {})
        self._display_width.setValue(display.get("width", 1920))
        self._display_height.setValue(display.get("height", 515))

        # Find widget settings by type
        pomo_cfg = self._find_widget_settings("pomodoro")
        self._pomo_work.setValue(pomo_cfg.get("work_minutes", 25))
        self._pomo_short_break.setValue(pomo_cfg.get("short_break_minutes", 5))
        self._pomo_long_break.setValue(pomo_cfg.get("long_break_minutes", 15))
        self._pomo_cycles.setValue(pomo_cfg.get("cycles_before_long_break", 4))

        cal_cfg = self._find_widget_settings("calendar")
        clock_fmt = cal_cfg.get("clock_format", "24h")
        idx = self._clock_format.findText(clock_fmt)
        if idx >= 0:
            self._clock_format.setCurrentIndex(idx)

    def _find_widget_settings(self, widget_type: str) -> dict:
        """Find settings dict for a widget type in config. Returns empty dict if not found."""
        for w in self._config.get("widgets", []):
            if w.get("type") == widget_type:
                return w.get("settings", {})
        return {}

    def _collect_config(self) -> dict:
        """Build config dict from current form values."""
        config = copy.deepcopy(self._config)
        config["layout"]["display"]["width"] = self._display_width.value()
        config["layout"]["display"]["height"] = self._display_height.value()

        # Update or create pomodoro widget settings
        self._update_widget_settings(config, "pomodoro", {
            "work_minutes": self._pomo_work.value(),
            "short_break_minutes": self._pomo_short_break.value(),
            "long_break_minutes": self._pomo_long_break.value(),
            "cycles_before_long_break": self._pomo_cycles.value(),
        })

        # Update or create calendar widget settings
        self._update_widget_settings(config, "calendar", {
            "clock_format": self._clock_format.currentText(),
        })

        return config

    def _update_widget_settings(self, config: dict, widget_type: str,
                                 settings: dict) -> None:
        """Update settings for widget_type in config. Creates widget entry if absent."""
        for w in config.get("widgets", []):
            if w.get("type") == widget_type:
                w["settings"] = settings
                return
        # Widget type not in config yet — do not add automatically.
        # Phase 3 adds Pomodoro/Calendar entries to config.json.

    def _on_save(self) -> None:
        """Collect form values and write config atomically."""
        config = self._collect_config()
        try:
            atomic_write_config(self._config_path, config)
            self._config = config
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save config:\n{e}")
