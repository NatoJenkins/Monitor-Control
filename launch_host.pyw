# launch_host.pyw -- No-console entry point for HKCU Run key autostart.
# sys.path[0] is set by the interpreter to this file's directory (project root),
# which makes all 'from host.X import Y' and 'from shared.X import Y' imports work.
import sys
import os

# Redirect stdout/stderr to a log file so autostart failures are visible.
_log_dir = os.path.join(os.path.expandvars("%LOCALAPPDATA%"), "MonitorControl")
os.makedirs(_log_dir, exist_ok=True)
_log = open(os.path.join(_log_dir, "launch.log"), "a")
import datetime
_log.write(f"\n--- launch {datetime.datetime.now().isoformat()} ---\n")
_log.flush()
sys.stdout = _log
sys.stderr = _log

import multiprocessing

if __name__ == "__main__":
    import time
    time.sleep(5)  # Wait for displays and shell to fully initialize at login
    multiprocessing.set_start_method("spawn")
    from host.main import main
    main()
