---
phase: 9
slug: config-schema-host-hot-reload-wiring
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` — `testpaths = tests` |
| **Quick run command** | `pytest tests/test_config_loader.py -x` |
| **Full suite command** | `pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_config_loader.py -x`
- **After every plan wave:** Run `pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 9-01-01 | 01 | 0 | BG-03, CLR-01 | unit | `pytest tests/test_config_loader.py -x` | ❌ Wave 0 | ⬜ pending |
| 9-01-02 | 01 | 1 | BG-03 | unit | `pytest tests/test_config_loader.py::TestBgColorWiring -x` | ❌ Wave 0 | ⬜ pending |
| 9-01-03 | 01 | 1 | BG-03, CLR-01 | unit | `pytest tests/test_config_loader.py::TestBgColorDefaults -x` | ❌ Wave 0 | ⬜ pending |
| 9-02-01 | 02 | 0 | CAL-04, CAL-05, CLR-01 | unit | `pytest tests/test_calendar_widget.py -x` | ❌ Wave 0 | ⬜ pending |
| 9-02-02 | 02 | 1 | CAL-04, CAL-05 | unit | `pytest tests/test_calendar_widget.py::TestCalendarColorInit -x` | ❌ Wave 0 | ⬜ pending |
| 9-02-03 | 02 | 1 | CAL-04, CAL-05 | unit | `pytest tests/test_calendar_widget.py::TestCalendarColorUpdate -x` | ❌ Wave 0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config_loader.py` — add `TestBgColorWiring` class: (a) host reads `bg_color` on initial load, (b) `after_reload` calls `set_bg_color` with updated value, (c) v1.1 config without `bg_color` key defaults to `#1a1a2e`
- [ ] `tests/test_calendar_widget.py` — add `TestCalendarColorInit` class: (a) `time_color` read from settings on init, (b) `date_color` read from settings on init, (c) missing keys default to `#ffffff` / `#dcdcdc`; add `TestCalendarColorUpdate` class: (a) `CONFIG_UPDATE` with `time_color` updates `_time_color`, (b) `CONFIG_UPDATE` with `date_color` updates `_text_color`

*Existing `tests/test_config_loader.py` and `tests/test_calendar_widget.py` already exist and can be extended in Wave 0.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Editing `bg_color` in config.json causes bar background to update live | BG-03 | QFileSystemWatcher + QTimer debounce requires a running host on real hardware; cannot headlessly verify paint timing | Edit `%LOCALAPPDATA%\MonitorControl\config.json`, change `bg_color` to `#ff0000`, save — bar background must turn red within ~200ms without restarting the host |
| Editing `time_color`/`date_color` causes calendar text to update live | CAL-04, CAL-05 | Subprocess `CONFIG_UPDATE` round-trip requires running processes; integration test would need process spawning | Edit config.json, change `time_color` to `#ff0000`, save — calendar time text must change color within the next render cycle without restarting the calendar subprocess |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
