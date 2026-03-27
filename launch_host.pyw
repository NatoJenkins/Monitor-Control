# launch_host.pyw -- No-console entry point for HKCU Run key autostart.
# sys.path[0] is set by the interpreter to this file's directory (project root),
# which makes all 'from host.X import Y' and 'from shared.X import Y' imports work.
import sys
import os

# Null-guard: under pythonw.exe sys.stdout and sys.stderr are None.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

import multiprocessing

if __name__ == "__main__":
    multiprocessing.set_start_method("spawn")
    from host.main import main
    main()
