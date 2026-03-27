"""Entry point for the control panel: python -m control_panel"""
import sys
from PyQt6.QtWidgets import QApplication
from control_panel.main_window import ControlPanelWindow


def main():
    app = QApplication(sys.argv)
    window = ControlPanelWindow(config_path="config.json")
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
