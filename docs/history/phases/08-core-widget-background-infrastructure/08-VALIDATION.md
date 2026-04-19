---
phase: 8
slug: core-widget-background-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-27
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` — `testpaths = tests` |
| **Quick run command** | `pytest tests/test_color_picker.py -x` |
| **Full suite command** | `pytest tests/ -m "not integration"` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_color_picker.py -x`
- **After every plan wave:** Run `pytest tests/ -m "not integration"`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** ~10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 8-01-01 | 01 | 0 | CPKR-01..04 | unit | `pytest tests/test_color_picker.py -x` | ❌ Wave 0 | ⬜ pending |
| 8-01-02 | 01 | 1 | CPKR-01 | unit | `pytest tests/test_color_picker.py::TestColorPickerStructure -x` | ❌ Wave 0 | ⬜ pending |
| 8-01-03 | 01 | 1 | CPKR-02 | unit | `pytest tests/test_color_picker.py::TestColorPickerBidirectional::test_swatch_updates -x` | ❌ Wave 0 | ⬜ pending |
| 8-01-04 | 01 | 1 | CPKR-03 | unit | `pytest tests/test_color_picker.py::TestColorPickerHexInput -x` | ❌ Wave 0 | ⬜ pending |
| 8-01-05 | 01 | 1 | CPKR-04 | unit | `pytest tests/test_color_picker.py::TestColorPickerSignal -x` | ❌ Wave 0 | ⬜ pending |
| 8-01-06 | 01 | 1 | CPKR-05 | structural | Inspect color_picker.py imports — no new packages | N/A | ⬜ pending |
| 8-02-01 | 02 | 2 | BG-01 | unit | `pytest tests/test_window.py -x` | ✅ extend | ⬜ pending |
| 8-02-02 | 02 | 2 | BG-02 | unit | `pytest tests/test_compositor.py -x` | ✅ extend | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_color_picker.py` — stubs for CPKR-01 through CPKR-04 (structure, swatch, hex input, signal behavior)
- [ ] Extend `tests/test_window.py` — add `TestWindowBgColor` class covering `set_bg_color()` and `_bg_qcolor` default value `#1a1a2e`

*Existing `tests/test_compositor.py` can be extended in Wave 2 (not a Wave 0 gap — file already exists).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Sliders update live swatch visually as dragged | CPKR-02 | Qt paint events require display; cannot headlessly verify swatch color | Instantiate widget in test harness, drag hue slider, confirm swatch QColor matches expected |
| Bar visually identical to v1.1 at #1a1a2e | BG-01, BG-02 | Pixel-level visual comparison requires running host | Run host, confirm bar background matches prior screenshot |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
