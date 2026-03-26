import sys
import multiprocessing
from PyQt6.QtWidgets import QApplication
from host.window import HostWindow
from host.win32_utils import find_target_screen, place_on_screen


def main():
    app = QApplication(sys.argv)

    window = HostWindow()
    # Flags already set in HostWindow.__init__

    target = find_target_screen(phys_width=1920, phys_height=515)
    if target is None:
        print("WARNING: Display 3 (1920x515) not found. Using last available screen.")
        target = app.screens()[-1]

    place_on_screen(window, target)

    # ClipCursor, WTS registration, ProcessManager, QueueDrainTimer
    # wired in plans 01-02 and 01-03

    sys.exit(app.exec())


if __name__ == "__main__":
    # BLOCKER: this guard prevents recursive subprocess spawning on Windows spawn
    multiprocessing.set_start_method("spawn")  # explicit; documents intent
    main()
