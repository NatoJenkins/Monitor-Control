# Deferred Items — Phase 02 Config System + Control Panel

## Pre-existing issues discovered but not fixed (out of scope)

### 1. test_e2e_dummy.py::test_dummy_frame_received fails on Windows spawn

- **Discovered during:** 02-01 Task 1 verification
- **File:** tests/test_e2e_dummy.py
- **Issue:** The integration test spawns a subprocess running run_dummy_widget and expects frames on the queue, but receives 0 frames. Confirmed pre-existing (git stash showed same failure on original code before any 02-01 changes).
- **Root cause:** Likely Windows spawn behavior + queue pickling or import path issue in subprocess context. The process starts and stays alive but doesn't push frames to the queue.
- **Impact:** Marked @pytest.mark.integration; excluded by default via `python -m pytest -m "not integration"`. Does not affect non-integration test suite (36 passing).
- **Resolution:** Requires debugging the subprocess import/queue behavior in the Windows spawn context. Candidate fix: ensure PYTHONPATH is set correctly in subprocess environment, or add explicit import guards.
