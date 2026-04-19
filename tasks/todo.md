# Todo

Active work and v1.3 candidates. Completed items move to a `## Done` section with date; rationale for non-trivial decisions gets a short note inline.

## v1.3 Candidates

- [ ] **ClipCursor game auto-detect** — extend the Game Mode toggle (commit d8026f3) to auto-disable cursor lock when a fullscreen/borderless game is foreground, re-enable on focus loss. Current toggle is manual.
- [ ] **PLSH-03 — Notification scrollable queue** — notification widget shows a scrollable list of simultaneous toasts instead of single-at-a-time auto-dismiss.
- [ ] **PLSH-01 — Pomodoro audio cue** — play a sound at each phase transition (WORK→SHORT_BREAK, etc.). Config key for enable/disable and sound file path.
- [ ] **PLSH-02 — Widget crash detection** — host detects widget subprocess exit, shows visual placeholder on the bar, exposes restart button in control panel.
- [ ] **PLSH-04 — Calendar seconds toggle** — config flag to show/hide seconds in the time display.
- [ ] **Phase 1 retroactive VERIFICATION.md** — documentation gap carried from v1.0 audit. All Phase 1 code works; just missing the formal verification doc.
- [ ] **MISS-01 — `_update_widget_settings` silent drop** — `control_panel/main_window.py:408–416` docstring claims "Creates widget entry if absent" but code doesn't. Currently masked (config always has all three entries). Either fix the docstring or implement the create path.

## Notification app-icon display (user-requested)

- [ ] Show the originating app's icon in the notification widget alongside title/body/app name.

## Active

<!-- nothing in flight -->

## Done

<!-- completed items, newest first -->
