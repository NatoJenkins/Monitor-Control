# Deferred Items — Phase 05

## Pre-existing Failures (out of scope for Phase 5)

### test_e2e_dummy.py::test_dummy_frame_received

- **Status:** Pre-existing failure (confirmed by testing on commit before Phase 5 changes)
- **Type:** Integration test (`@pytest.mark.integration`)
- **Failure:** `AssertionError: Expected at least one FrameData from the dummy widget subprocess`
- **Root cause:** Multiprocessing subprocess does not push frames within the 0.5s window under the CI/test runner environment. Not caused by Phase 5 changes.
- **Action:** Excluded from Phase 5 regression run. Investigate in a future phase or address as a known flaky integration test.
