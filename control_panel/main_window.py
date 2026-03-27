"""ControlPanelWindow — tab-based configuration UI for MonitorControl.

The control panel is the sole writer of config.json. On Save, it calls
atomic_write_config which triggers the host's QFileSystemWatcher hot-reload.
"""
import copy
import os
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QTabWidget, QVBoxLayout, QHBoxLayout,
    QFormLayout, QGroupBox, QSpinBox, QComboBox, QPushButton,
    QLabel, QMessageBox, QLineEdit, QListWidget, QCheckBox,
)
from PyQt6.QtGui import QShortcut, QKeySequence
from control_panel.config_io import load_config, atomic_write_config, write_pomodoro_command
from control_panel.color_picker import ColorPickerWidget


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
        self._tabs.addTab(self._build_notification_tab(), "Notification")
        self._tabs.addTab(self._build_shortcuts_tab(), "Shortcuts")
        self._tabs.addTab(self._build_startup_tab(), "Startup")
        root_layout.addWidget(self._tabs)

        # Save button row
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._save_btn = QPushButton("Save")
        self._save_btn.clicked.connect(self._on_save)
        btn_row.addWidget(self._save_btn)
        root_layout.addLayout(btn_row)

        # Set up QShortcut bindings (defaults; overridden by _load_values from config)
        self._shortcut_start = QShortcut(QKeySequence("Ctrl+S"), self)
        self._shortcut_start.activated.connect(lambda: self._send_pomo_command("start"))
        self._shortcut_pause = QShortcut(QKeySequence("Ctrl+P"), self)
        self._shortcut_pause.activated.connect(lambda: self._send_pomo_command("pause"))
        self._shortcut_reset = QShortcut(QKeySequence("Ctrl+R"), self)
        self._shortcut_reset.activated.connect(lambda: self._send_pomo_command("reset"))

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

        # --- Controls groupbox (POMO-04) ---
        controls_group = QGroupBox("Controls")
        controls_layout = QHBoxLayout(controls_group)

        self._pomo_start_btn = QPushButton("Start")
        self._pomo_pause_btn = QPushButton("Pause")
        self._pomo_reset_btn = QPushButton("Reset")

        self._pomo_start_btn.clicked.connect(lambda: self._send_pomo_command("start"))
        self._pomo_pause_btn.clicked.connect(lambda: self._send_pomo_command("pause"))
        self._pomo_reset_btn.clicked.connect(lambda: self._send_pomo_command("reset"))

        controls_layout.addWidget(self._pomo_start_btn)
        controls_layout.addWidget(self._pomo_pause_btn)
        controls_layout.addWidget(self._pomo_reset_btn)

        layout.addWidget(controls_group)

        # --- Durations groupbox ---
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

        # --- Appearance groupbox ---
        appear_group = QGroupBox("Appearance")
        appear_form = QFormLayout(appear_group)

        self._pomo_font = QComboBox()
        self._pomo_font.addItems(["Inter", "Digital-7", "Share Tech Mono"])
        appear_form.addRow("Font:", self._pomo_font)

        self._pomo_work_color = ColorPickerWidget()
        appear_form.addRow("Work Color:", self._pomo_work_color)

        self._pomo_short_break_color = ColorPickerWidget()
        appear_form.addRow("Short Break Color:", self._pomo_short_break_color)

        self._pomo_long_break_color = ColorPickerWidget()
        appear_form.addRow("Long Break Color:", self._pomo_long_break_color)

        layout.addWidget(appear_group)
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

        self._cal_font = QComboBox()
        self._cal_font.addItems(["Inter", "Digital-7", "Share Tech Mono"])
        form.addRow("Font:", self._cal_font)

        self._cal_time_color = ColorPickerWidget()
        form.addRow("Time Color:", self._cal_time_color)

        self._cal_date_color = ColorPickerWidget()
        form.addRow("Date Color:", self._cal_date_color)

        layout.addWidget(group)
        layout.addStretch()
        return container

    def _build_notification_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)

        # --- Settings groupbox ---
        settings_group = QGroupBox("Notification Settings")
        settings_form = QFormLayout(settings_group)

        self._notif_timeout = QSpinBox()
        self._notif_timeout.setRange(5, 300)
        self._notif_timeout.setSuffix(" sec")
        settings_form.addRow("Auto-dismiss timeout:", self._notif_timeout)

        self._notif_font = QComboBox()
        self._notif_font.addItems(["Inter", "Digital-7", "Share Tech Mono"])
        settings_form.addRow("Font:", self._notif_font)

        layout.addWidget(settings_group)

        # --- Blocklist groupbox ---
        block_group = QGroupBox("Blocked Apps")
        block_layout = QVBoxLayout(block_group)

        self._notif_blocklist = QListWidget()
        block_layout.addWidget(self._notif_blocklist)

        btn_row = QHBoxLayout()
        self._notif_add_btn = QPushButton("+")
        self._notif_add_btn.setFixedWidth(40)
        self._notif_add_btn.clicked.connect(self._on_blocklist_add)
        self._notif_remove_btn = QPushButton("-")
        self._notif_remove_btn.setFixedWidth(40)
        self._notif_remove_btn.clicked.connect(self._on_blocklist_remove)
        btn_row.addWidget(self._notif_add_btn)
        btn_row.addWidget(self._notif_remove_btn)
        btn_row.addStretch()
        block_layout.addLayout(btn_row)

        self._notif_app_input = QLineEdit()
        self._notif_app_input.setPlaceholderText("App name to block (e.g. Microsoft Edge)")
        block_layout.addWidget(self._notif_app_input)

        layout.addWidget(block_group)
        layout.addStretch()
        return container

    def _on_blocklist_add(self) -> None:
        app_name = self._notif_app_input.text().strip()
        if app_name:
            self._notif_blocklist.addItem(app_name)
            self._notif_app_input.clear()

    def _on_blocklist_remove(self) -> None:
        current = self._notif_blocklist.currentRow()
        if current >= 0:
            self._notif_blocklist.takeItem(current)

    def _build_shortcuts_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        group = QGroupBox("Pomodoro Shortcuts")
        form = QFormLayout(group)

        self._shortcut_start_edit = QLineEdit()
        self._shortcut_start_edit.setPlaceholderText("e.g. Ctrl+S")
        form.addRow("Start:", self._shortcut_start_edit)

        self._shortcut_pause_edit = QLineEdit()
        self._shortcut_pause_edit.setPlaceholderText("e.g. Ctrl+P")
        form.addRow("Pause:", self._shortcut_pause_edit)

        self._shortcut_reset_edit = QLineEdit()
        self._shortcut_reset_edit.setPlaceholderText("e.g. Ctrl+R")
        form.addRow("Reset:", self._shortcut_reset_edit)

        layout.addWidget(group)
        layout.addStretch()
        return container

    def _build_startup_tab(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        group = QGroupBox("Startup")
        group_layout = QVBoxLayout(group)

        self._autostart_checkbox = QCheckBox("Start MonitorControl at Windows login")
        group_layout.addWidget(self._autostart_checkbox)

        self._autostart_label = QLabel(
            "MonitorControl will start automatically at next login"
        )
        self._autostart_label.setVisible(False)
        group_layout.addWidget(self._autostart_label)

        layout.addWidget(group)
        layout.addStretch()

        self._autostart_checkbox.toggled.connect(self._on_autostart_toggled)
        return container

    def _on_autostart_toggled(self, checked: bool) -> None:
        from control_panel.autostart import enable_autostart, disable_autostart
        try:
            if checked:
                enable_autostart()
            else:
                disable_autostart()
            self._autostart_label.setVisible(checked)
        except (OSError, RuntimeError) as e:
            QMessageBox.critical(
                self, "Autostart Error",
                f"Failed to update autostart setting:\n{e}"
            )
            # Revert checkbox to match actual registry state
            from control_panel.autostart import is_autostart_enabled
            self._autostart_checkbox.blockSignals(True)
            self._autostart_checkbox.setChecked(is_autostart_enabled())
            self._autostart_checkbox.blockSignals(False)

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

        # Pomodoro appearance
        self._pomo_font.setCurrentText(pomo_cfg.get("font", "Inter"))
        self._pomo_work_color.set_color(pomo_cfg.get("work_accent_color", "#ff4444"))
        self._pomo_short_break_color.set_color(pomo_cfg.get("short_break_accent_color", "#44ff44"))
        self._pomo_long_break_color.set_color(pomo_cfg.get("long_break_accent_color", "#4488ff"))

        cal_cfg = self._find_widget_settings("calendar")
        clock_fmt = cal_cfg.get("clock_format", "24h")
        idx = self._clock_format.findText(clock_fmt)
        if idx >= 0:
            self._clock_format.setCurrentIndex(idx)

        # Calendar font
        self._cal_font.setCurrentText(cal_cfg.get("font", "Inter"))

        # Calendar colors
        self._cal_time_color.set_color(cal_cfg.get("time_color", "#ffffff"))
        self._cal_date_color.set_color(cal_cfg.get("date_color", "#dcdcdc"))

        # Notification settings
        notif_cfg = self._find_widget_settings("notification")
        self._notif_timeout.setValue(notif_cfg.get("auto_dismiss_seconds", 30))
        self._notif_font.setCurrentText(notif_cfg.get("font", "Inter"))
        self._notif_blocklist.clear()
        for app in notif_cfg.get("blocked_apps", []):
            self._notif_blocklist.addItem(app)

        # Shortcuts
        shortcuts = self._config.get("shortcuts", {})
        self._shortcut_start_edit.setText(shortcuts.get("pomodoro_start", "Ctrl+S"))
        self._shortcut_pause_edit.setText(shortcuts.get("pomodoro_pause", "Ctrl+P"))
        self._shortcut_reset_edit.setText(shortcuts.get("pomodoro_reset", "Ctrl+R"))

        # Update QShortcut bindings from config
        self._shortcut_start.setKey(QKeySequence(shortcuts.get("pomodoro_start", "Ctrl+S")))
        self._shortcut_pause.setKey(QKeySequence(shortcuts.get("pomodoro_pause", "Ctrl+P")))
        self._shortcut_reset.setKey(QKeySequence(shortcuts.get("pomodoro_reset", "Ctrl+R")))

        # Autostart (reads live HKCU registry state -- STRT-03)
        from control_panel.autostart import is_autostart_enabled
        enabled = is_autostart_enabled()
        self._autostart_checkbox.blockSignals(True)
        self._autostart_checkbox.setChecked(enabled)
        self._autostart_checkbox.blockSignals(False)
        self._autostart_label.setVisible(enabled)

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
            "font": self._pomo_font.currentText(),
            "work_accent_color": self._pomo_work_color.color(),
            "short_break_accent_color": self._pomo_short_break_color.color(),
            "long_break_accent_color": self._pomo_long_break_color.color(),
        })

        # Update or create calendar widget settings
        self._update_widget_settings(config, "calendar", {
            "clock_format": self._clock_format.currentText(),
            "font": self._cal_font.currentText(),
            "time_color": self._cal_time_color.color(),
            "date_color": self._cal_date_color.color(),
        })

        # Update notification widget settings
        blocked = [self._notif_blocklist.item(i).text()
                   for i in range(self._notif_blocklist.count())]
        self._update_widget_settings(config, "notification", {
            "font": self._notif_font.currentText(),
            "auto_dismiss_seconds": self._notif_timeout.value(),
            "blocked_apps": blocked,
        })

        # Shortcuts
        config["shortcuts"] = {
            "pomodoro_start": self._shortcut_start_edit.text(),
            "pomodoro_pause": self._shortcut_pause_edit.text(),
            "pomodoro_reset": self._shortcut_reset_edit.text(),
        }

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

    def _send_pomo_command(self, command: str) -> None:
        """Write a Pomodoro command file for the host to pick up."""
        config_dir = os.path.dirname(os.path.abspath(self._config_path))
        write_pomodoro_command(config_dir, command)

    def _on_save(self) -> None:
        """Collect form values and write config atomically."""
        config = self._collect_config()
        try:
            atomic_write_config(self._config_path, config)
            self._config = config
        except Exception as e:
            QMessageBox.critical(self, "Save Error", f"Failed to save config:\n{e}")
