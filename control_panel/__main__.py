"""Entry point for the control panel: python -m control_panel"""
import sys
import os

# Null-guard: PyInstaller windowed mode (console=False) sets sys.stdout/stderr to None.
# Redirect to devnull so any print() call in imported modules does not crash.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from PyQt6.QtWidgets import QApplication
from control_panel.main_window import ControlPanelWindow
from shared.paths import get_config_path


def main():
    app = QApplication(sys.argv)
    window = ControlPanelWindow(config_path=str(get_config_path()))
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
