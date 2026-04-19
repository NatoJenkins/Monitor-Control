# Project Name
MonitorControl

## Project

- **Repo:** https://github.com/NatoJenkins/Monitor-Control
- **Local:** Windows 11, PowerShell (no `grep` — use `Select-String`)

A modular widget framework driving a dedicated 1920×515 secondary display (Display 3, below two primary monitors) as a persistent utility bar. A host PyQt6 app owns the display as a borderless always-on-top window and composites output from widget subprocesses over multiprocessing queues. A separate PyQt6 control panel (packaged as `MonitorControl.exe`) edits `config.json`, which the host hot-reloads.

## Stack

- Python + PyQt6 6.10.2 (host + control panel)
- Pillow (widget off-screen rendering, icon gen)
- pywin32 311 (ClipCursor, WTS session notifications, winreg)
- winrt-Windows.UI.Notifications.Management 3.2.1 + 5 peer packages (WinRT notification access)
- PyInstaller 6.19.0 (build-time only — control panel packaging)
- `multiprocessing.Queue` for all IPC (widget → host: `FrameData`; host → widget: `ConfigUpdateMessage`, `ControlSignal`)

## Current State

**v1.2 Configurable Colors shipped 2026-03-27.** All 14 requirements satisfied (see [docs/milestones/v1.2-MILESTONE-AUDIT.md](docs/milestones/v1.2-MILESTONE-AUDIT.md)). Ships with Pomodoro, Calendar/Clock, and Windows notification interceptor widgets — all colors configurable via hue/intensity pickers. Post-v1.2: Game Mode toggle added (commit d8026f3) to disable cursor lock for borderless games.

**v1.3 candidates** tracked in [tasks/todo.md](tasks/todo.md).

**Start every session by reading:**
- [tasks/todo.md](tasks/todo.md) — active work, v1.3 candidates, decisions log
- `~/.claude/projects/E--ClaudeCodeProjects-MonitorControl/memory/MEMORY.md` + `feedback_*.md` — rules from past corrections (auto-loaded)

## Key Gotchas

- **Rebuild the exe after control panel source changes.** `python -m PyInstaller build/control_panel.spec -y`. The packaged exe is what runs in production; Python source changes are invisible until rebuilt.
- **HKCU Run key is unreliable on Win11** for autostart — Windows silently ignores it despite correct registry + StartupApproved state. Use a `.lnk` in the Startup folder (shell:startup) instead.
- **ClipCursor re-application is polling-based, not message-based.** A 100ms timer reapplies the clip; relying only on WM events (session unlock, WM_DISPLAYCHANGE, WM_ACTIVATEAPP) is insufficient — Windows overrides the clip in contexts that never fire a message.
- **WM_DISPLAYCHANGE must reposition, not just reclip.** Monitor power-cycle causes Windows to relocate the host window; reapplying ClipCursor against the stale position clips empty space. Debounced full re-discovery + reposition + reclip, with 2s retry if Display 3 isn't back yet.
- **Config path is `%LOCALAPPDATA%\MonitorControl\config.json`** — shared between the packaged exe and the Python host. Exe dir ≠ project root during dev; both processes must read/write the same file.
- **WinRT notifications use 2s polling, not event subscription.** `add_notification_changed` raises OSError on python.org Python (validated in Phase 4 spike).
- **`RequestAccessAsync` must run on Qt main thread before widget spawn.** Widget subprocess has no STA apartment; COM threading requires the grant happen host-side.
- **`proc.terminate()` without `join()`** in `stop_widget` is deliberate — join on Qt main thread deadlocks on Windows (queue pipe isn't drained). IPC-03 spec language needs amendment.
- **Pre-existing test failure:** `test_e2e_dummy.py::test_dummy_frame_received` fails on Windows spawn. All VALIDATION.md files remain in draft status (Nyquist sign-off not completed).

## Reference Documents

Read relevant docs before planning non-trivial changes.

- [docs/history/PROJECT.md](docs/history/PROJECT.md) — validated requirements, backlog, out-of-scope, key decisions table
- [docs/history/STATE.md](docs/history/STATE.md) — codebase state snapshot
- [docs/history/ROADMAP.md](docs/history/ROADMAP.md) / [docs/history/MILESTONES.md](docs/history/MILESTONES.md) — milestone plan
- [docs/history/RETROSPECTIVE.md](docs/history/RETROSPECTIVE.md) — v1.2 retrospective
- [docs/milestones/](docs/milestones/) — per-milestone requirements, roadmaps, audits (v1.0, v1.1, v1.2)
- [docs/research/](docs/research/) — `ARCHITECTURE.md`, `FEATURES.md`, `PITFALLS.md`, `STACK.md`, `SUMMARY.md` (deep reference)
- [docs/history/phases/](docs/history/phases/) — per-phase plan/verification/validation artifacts (11 phases)

## Workflow

Follow this loop for every non-trivial task:

1. **Research First** — Investigate the current state. Read relevant files, check existing schemas, explore the data. Understand before proposing.
2. **Plan** — Write plan to `tasks/todo.md`. No code until the plan exists.
3. **Verify Plan** — Present the plan for review before executing.
4. **Track Progress** — Mark items complete in todo.md as you go.
5. **Explain Changes** — Summarize what you did at each step.
6. **Document Results** — Add a review section to todo.md when done.
7. **Capture Lessons** — After any correction, write a memory entry (`~/.claude/projects/E--ClaudeCodeProjects-MonitorControl/memory/feedback_*.md` with frontmatter, plus a pointer line in `MEMORY.md`). Memory auto-loads across sessions; do not maintain a separate `lessons.md`.

## Commits

Atomic commits only. One logical change per commit. If you're adding an endpoint and notice an unrelated typo, that's two commits.

## Rules

- **Plan before executing.** Any task with 3+ steps gets a plan first.
- **Investigate, don't guess.** Diagnose actual causes. No "probably" or "likely" explanations. Define investigation steps, run them, report findings.
- **Verify before done.** Never mark a task complete without proving it works. Run the code, check the output, confirm the behavior.
- **Ask before destructive operations.** Deleting data, dropping tables, overwriting files — confirm first.
- **Write and run tests.** Code needs tests. Tests must pass before marking a task complete.
- **Separate builder from evaluator.** The agent that writes the code should not be the same agent that tests or reviews it. Use subagents to enforce separation.
- **Pin every import.** Every `import X` in a source file must have X in `requirements.txt` with an exact version. Docker images build from `requirements.txt` only — transitive dependencies from the host environment will not be there. Verify before committing: check new imports against `requirements.txt` and add any missing entries.
