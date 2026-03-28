# Roadmap: MonitorControl

## Milestones

- ✅ **v1.0 MVP** — Phases 1–4 (shipped 2026-03-27)
- ✅ **v1.1 Startup & Distribution** — Phases 5–7 (shipped 2026-03-27)
- 🚧 **v1.2 Configurable Colors** — Phases 8–11 (in progress)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1–4) — SHIPPED 2026-03-27</summary>

- [x] Phase 1: Host Infrastructure + Pipeline (3/3 plans) — completed 2026-03-26
- [x] Phase 2: Config System + Control Panel (2/2 plans) — completed 2026-03-27
- [x] Phase 3: Pomodoro + Calendar Widgets (2/2 plans) — completed 2026-03-27
- [x] Phase 4: Notification Interceptor (2/2 plans) — completed 2026-03-27

Full details: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Startup & Distribution (Phases 5–7) — SHIPPED 2026-03-27</summary>

- [x] Phase 5: Path Resolution & Freeze Safety (1/1 plans) — completed 2026-03-27
- [x] Phase 6: Autostart Toggle (1/1 plans) — completed 2026-03-27
- [x] Phase 7: Control Panel Packaging (1/1 plans) — completed 2026-03-27

Full details: `.planning/milestones/v1.1-ROADMAP.md`

</details>

### 🚧 v1.2 Configurable Colors (In Progress)

**Milestone Goal:** Replace all hardcoded colors with a user-configurable color system. A reusable ColorPickerWidget drives three integration points in the control panel. Background color ownership moves from widget subprocesses to the host compositor. All defaults match current hardcoded values — zero visual change on upgrade.

- [x] **Phase 8: Core Widget + Background Infrastructure** — Build ColorPickerWidget and atomically migrate host/widget background ownership (completed 2026-03-27)
- [x] **Phase 9: Config Schema + Host Hot-Reload Wiring** — Wire bg_color and calendar color keys through config into the live bar (completed 2026-03-27)
- [x] **Phase 10: Control Panel Integration** — Replace Pomodoro hex fields and add Calendar color pickers (completed 2026-03-27)
- [x] **Phase 11: Layout Tab bg_color Picker** — Expose bg_color in the control panel and close the end-to-end user flow (completed 2026-03-28)

## Phase Details

### Phase 8: Core Widget + Background Infrastructure
**Goal**: ColorPickerWidget exists as a tested, reusable component, and the host compositor owns background fill with widgets rendering on a transparent background
**Depends on**: Phase 7
**Requirements**: CPKR-01, CPKR-02, CPKR-03, CPKR-04, CPKR-05, BG-01, BG-02
**Success Criteria** (what must be TRUE):
  1. A ColorPickerWidget instantiated in isolation renders a hue slider, an intensity slider, a live swatch, and a hex input field — all updating each other bidirectionally without signal loops
  2. Typing a valid #RRGGBB hex string into the widget moves both sliders to the correct positions; typing an invalid string leaves the widget unchanged
  3. The widget emits color_changed(str) exactly once per user interaction (drag end or valid hex entry), never on programmatic set_color() calls
  4. The host bar background is filled with a solid QColor via paintEvent using self.rect() — no widget renders its own background fill
  5. The bar is visually identical to v1.1 at the default color (#1a1a2e) with the host-owned fill active
**Plans:** 2/2 plans complete
Plans:
- [ ] 08-01-PLAN.md — Build ColorPickerWidget with TDD (hue/intensity sliders, swatch, hex input, signal behavior)
- [ ] 08-02-PLAN.md — Atomic background migration (host bg fill + widget transparency)

### Phase 9: Config Schema + Host Hot-Reload Wiring
**Goal**: Editing config.json by hand causes the bar background color and calendar text colors to update live — the full config-to-screen pipeline is verified before any control panel UI is built
**Depends on**: Phase 8
**Requirements**: BG-03, CAL-04, CAL-05, CLR-01
**Success Criteria** (what must be TRUE):
  1. Manually setting `bg_color` in config.json and saving causes the bar background to change color within the hot-reload debounce window (no host restart required)
  2. A v1.1 config.json with no `bg_color` key loads without error and renders the bar at #1a1a2e
  3. A v1.1 config.json with no `time_color` or `date_color` in the calendar settings block loads without error and renders calendar text at #ffffff and #dcdcdc respectively
  4. Manually setting `time_color` and `date_color` in the calendar settings block and saving causes calendar text colors to update without restarting the widget subprocess
**Plans:** 2/2 plans complete
Plans:
- [ ] 09-01-PLAN.md — Wire bg_color through host hot-reload pipeline + update config.json schema
- [ ] 09-02-PLAN.md — Add _safe_hex_color and config-driven colors to CalendarWidget

### Phase 10: Control Panel Integration
**Goal**: Pomodoro and Calendar tabs in the control panel expose color pickers — the three existing hex QLineEdit fields in Pomodoro are replaced, and Calendar gains two new pickers — with all changes persisting to config.json on Save
**Depends on**: Phase 9
**Requirements**: POMO-06, CAL-06
**Success Criteria** (what must be TRUE):
  1. Opening the Pomodoro tab shows three ColorPickerWidget instances in place of the previous hex text fields; each is pre-populated with the current accent color from config
  2. Adjusting a Pomodoro color picker and clicking Save causes the Pomodoro widget to update its accent color live without a host restart
  3. Opening the Calendar tab shows two ColorPickerWidget instances for time color and date color; each is pre-populated with the current value from config
  4. Adjusting a Calendar color picker and clicking Save causes the calendar text to update live without a host restart
**Plans:** 1/1 plans complete
Plans:
- [ ] 10-01-PLAN.md — Replace Pomodoro QLineEdit fields with ColorPickerWidgets and add Calendar color pickers (TDD)

### Phase 11: Layout Tab bg_color Picker
**Goal**: The Layout tab exposes a ColorPickerWidget for the bar background color, closing the full user-facing color configuration flow end-to-end
**Depends on**: Phase 10
**Requirements**: BG-04
**Success Criteria** (what must be TRUE):
  1. Opening the Layout tab shows a ColorPickerWidget pre-populated with the current bg_color from config
  2. Adjusting the background color picker and clicking Save causes the bar background to change to the selected color immediately
  3. Reopening the control panel after Save shows the Layout tab picker restored to the previously saved color
**Plans:** 1/1 plans complete
Plans:
- [ ] 11-01-PLAN.md — Add bg_color ColorPickerWidget to Layout tab (TDD)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Host Infrastructure + Pipeline | v1.0 | 3/3 | Complete | 2026-03-26 |
| 2. Config System + Control Panel | v1.0 | 2/2 | Complete | 2026-03-27 |
| 3. Pomodoro + Calendar Widgets | v1.0 | 2/2 | Complete | 2026-03-27 |
| 4. Notification Interceptor | v1.0 | 2/2 | Complete | 2026-03-27 |
| 5. Path Resolution & Freeze Safety | v1.1 | 1/1 | Complete | 2026-03-27 |
| 6. Autostart Toggle | v1.1 | 1/1 | Complete | 2026-03-27 |
| 7. Control Panel Packaging | v1.1 | 1/1 | Complete | 2026-03-27 |
| 8. Core Widget + Background Infrastructure | v1.2 | 2/2 | Complete | 2026-03-27 |
| 9. Config Schema + Hot-Reload Wiring | v1.2 | 2/2 | Complete | 2026-03-27 |
| 10. Control Panel Integration | v1.2 | 1/1 | Complete | 2026-03-27 |
| 11. Layout Tab bg_color Picker | 1/1 | Complete   | 2026-03-28 | - |

---
*Roadmap created: 2026-03-26*
*Last updated: 2026-03-27 — Phase 11 plans created (1 plan, 1 wave)*
