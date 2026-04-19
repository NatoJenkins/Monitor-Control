# Phase 5: Path Resolution & Freeze Safety - Research

**Researched:** 2026-03-27
**Domain:** Python path resolution, pythonw.exe null-stream safety
**Confidence:** HIGH

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| INFRA-01 | Host and control panel resolve config.json relative to script/executable directory (not process cwd) — prerequisite for autostart and packaging both working correctly | `__file__`-based resolution via `pathlib.Path(__file__).resolve().parent` is the correct pattern; works for both script and PyInstaller frozen contexts |
| INFRA-02 | Host does not crash when launched without a console window (print() calls null-guarded for pythonw.exe context) | Under pythonw.exe sys.stdout and sys.stderr are None; a single safe_print() helper or a null-guard at module entry is the correct pattern |
</phase_requirements>

---

## Summary

Phase 5 fixes two concrete, pre-existing bugs that will block Phase 6 (autostart) and Phase 7 (packaging) if left unaddressed.

**Bug 1 — INFRA-01**: Both `host/main.py` and `control_panel/__main__.py` currently pass the bare string `"config.json"` to their respective loaders. `os.path.abspath("config.json")` resolves relative to the *process working directory*, not the script location. When the host is launched by a HKCU Run key at login, Windows sets cwd to `C:\Windows\System32`. Config will not be found and both processes will crash immediately. The fix is a `shared/paths.py` module that resolves the config path relative to `__file__` using `pathlib`.

**Bug 2 — INFRA-02**: The host currently has 12 bare `print()` calls across `host/main.py` (7) and `host/config_loader.py` (5). Under `pythonw.exe` (the console-less Python interpreter), `sys.stdout` and `sys.stderr` are `None`. Calling `print()` when stdout is `None` raises `AttributeError: 'NoneType' object has no attribute 'write'`. The fix is a small null-guard: either a `safe_print()` helper in `shared/` that checks for `None` before writing, or a one-time stream replacement at startup that points both streams at a no-op sink.

**Primary recommendation:** Create `shared/paths.py` with `get_config_path()` using `pathlib.Path(__file__).resolve().parent.parent / "config.json"`, and add `safe_print()` or a startup null-guard in `host/main.py`. Both changes are confined to a small surface area and can be done in a single plan.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `pathlib` (stdlib) | Python 3.12+ | Path resolution relative to `__file__` | Cross-platform, no install required, freeze-safe |
| `sys` (stdlib) | Python 3.12+ | Checking `sys.stdout is None` | Direct access to interpreter stream handles |
| `os.path` (stdlib) | Python 3.12+ | `abspath`, `dirname` as fallback | Already used in project; `pathlib` preferred for new code |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `io.StringIO` (stdlib) | Python 3.12+ | Null stream replacement | Only if routing output somewhere (not needed here) |
| `os.devnull` (stdlib) | Python 3.12+ | Black-hole stream sink | Alternative to None-check for stream replacement |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pathlib.Path(__file__)` | `os.path.dirname(os.path.abspath(__file__))` | Both work; `pathlib` is more readable and modern |
| per-call `safe_print()` | Replace `sys.stdout = open(os.devnull)` at startup | Stream replacement is 1 line but hides output on terminal too; `safe_print` is surgical |
| per-call `safe_print()` | Remove all `print()` calls entirely | Over-engineering; print statements serve as debug traces during development |

**Installation:** No new packages required. All solutions use Python stdlib.

---

## Architecture Patterns

### Recommended Project Structure Addition
```
shared/
├── message_schema.py    # exists — IPC message dataclasses
├── paths.py             # NEW — canonical path resolver
```

### Pattern 1: `__file__`-based config path resolution

**What:** Derive config path from the location of the module file itself, not from the process cwd.

**When to use:** Any time a script must locate a sibling file regardless of where the process was launched from.

**Anchor point for this project:** `shared/paths.py` lives at `<project_root>/shared/paths.py`. The config file lives at `<project_root>/config.json`. Therefore:

```python
# shared/paths.py
from pathlib import Path

_SHARED_DIR = Path(__file__).resolve().parent   # .../shared/
_PROJECT_ROOT = _SHARED_DIR.parent              # .../MonitorControl/

def get_config_path() -> Path:
    """Return the absolute path to config.json regardless of launch cwd."""
    return _PROJECT_ROOT / "config.json"
```

**Caller pattern (host/main.py):**
```python
from shared.paths import get_config_path

config_loader = ConfigLoader(str(get_config_path()), pm, window.compositor, after_reload=reapply_clip)
config_dir = str(get_config_path().parent)
```

**Caller pattern (control_panel/__main__.py):**
```python
from shared.paths import get_config_path

window = ControlPanelWindow(config_path=str(get_config_path()))
```

**Why `resolve()`:** On Windows, `__file__` may be a relative path when a script is invoked directly. `.resolve()` guarantees an absolute path and resolves symlinks.

**Why `str(...)`:** Existing `ConfigLoader` and `ControlPanelWindow` accept `str`, not `Path`. Passing `str(get_config_path())` avoids changing any downstream signatures.

### Pattern 2: Null-guard for sys.stdout under pythonw.exe

**What:** Under `pythonw.exe`, Python sets `sys.stdout = None` and `sys.stderr = None`. `print()` delegates to `sys.stdout.write()`, which raises `AttributeError` when the stream is None.

**When to use:** Any host-side code that calls `print()` and may be executed via `pythonw.exe` (i.e., the console-less launcher used by the HKCU Run key autostart).

**Option A — safe_print helper (surgical, recommended):**
```python
# shared/paths.py (or shared/utils.py — can live here to avoid a third file)
import sys

def safe_print(*args, **kwargs) -> None:
    """print() wrapper that no-ops when stdout is None (pythonw.exe context)."""
    if sys.stdout is not None:
        print(*args, **kwargs)
```

Replace all `print(...)` calls in `host/main.py` and `host/config_loader.py` with `safe_print(...)`.

**Option B — startup stream replacement (one-line, coarser):**
```python
# At the top of host/main.py, before any print() calls
import sys, os
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
```

This redirects output to the null device, making all subsequent `print()` calls safe. Simpler but permanently silences output even if a terminal is later attached. Acceptable for a production host.

**Recommendation:** Option B (startup null-guard) is fewer lines and requires no import changes in `config_loader.py`. It is the idiomatic pattern used by Windows GUI Python applications.

### Anti-Patterns to Avoid

- **`os.getcwd()` + `"config.json"`**: Resolves from cwd, which changes per launch context. Never use for locating app data files.
- **`sys.executable` parent**: Resolves to the Python interpreter directory (`C:\Python312\`), not the project root. Wrong anchor.
- **`os.path.abspath("config.json")`**: The existing incorrect pattern. `abspath` with a bare filename is equivalent to `os.path.join(os.getcwd(), "config.json")`.
- **Catching `AttributeError` around every print**: Treating the symptom, not the cause. Null-guard once at startup instead.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Locating project root | Custom `find_project_root()` that walks up looking for `config.json` | `pathlib.Path(__file__).resolve().parent.parent` | The anchor point is known and fixed; discovery logic adds fragility |
| Null stream | Custom `NullWriter` class with `.write()` and `.flush()` | `open(os.devnull, "w")` or a 2-line None-check | stdlib handles this; custom class is dead code |

**Key insight:** Both problems are 5-line stdlib solutions. Any custom abstraction beyond that adds maintenance surface without benefit.

---

## Common Pitfalls

### Pitfall 1: Using `__file__` without `.resolve()`
**What goes wrong:** When the script is run as `python host/main.py` (relative invocation), `__file__` is `host/main.py` (relative). `Path(__file__).parent` yields `Path('host')`, not an absolute path. Joining `"config.json"` gives `Path('host/config.json')`, which is wrong.
**Why it happens:** `__file__` is set by the interpreter to whatever path was used to load the module.
**How to avoid:** Always call `.resolve()` before using `__file__`-derived paths: `Path(__file__).resolve().parent`.
**Warning signs:** Config found when running from project root but not from other directories.

### Pitfall 2: Anchoring to the wrong file
**What goes wrong:** Using `host/main.py`'s `__file__` to compute the project root gives `Path(__file__).resolve().parent.parent`, which is correct. But `host/config_loader.py` is also in `host/`, so using its `__file__` as the anchor would give the same result. If `shared/paths.py` is used as the canonical anchor, its `__file__` is `<root>/shared/paths.py`, so `parent.parent` is the project root. **This must be verified once the file is created.**
**How to avoid:** Put a test in the test suite that asserts `get_config_path().parent == Path(__file__).resolve().parent.parent.parent` from the test's perspective, or more simply: assert the returned path ends with `config.json` and that `get_config_path().parent` is the directory containing `host/` and `control_panel/`.

### Pitfall 3: Forgetting flush=True on safe_print
**What goes wrong:** If Option A (safe_print helper) is used, callers currently pass `flush=True` to many print calls. The helper must forward `**kwargs` to `print()` or the buffering behavior changes.
**How to avoid:** `safe_print(*args, **kwargs)` with `print(*args, **kwargs)` in the body. The `**kwargs` passthrough handles `flush`, `end`, `sep`, etc.

### Pitfall 4: config_loader.py also calls print() — easy to miss
**What goes wrong:** Fixing only `host/main.py` leaves 5 `print()` calls in `host/config_loader.py` unguarded. Under pythonw.exe, the first file-change event will crash the host.
**Why it happens:** The fix seems complete after touching main.py, but config_loader.py's prints are triggered at runtime, not at startup.
**How to avoid:** The Option B startup null-guard (applied once in `main.py` before any Qt setup) covers ALL subsequent print calls in all modules, including `config_loader.py`. Option A requires updating both files.

### Pitfall 5: Bare "config.json" in config_dir computation (host/main.py line 92)
**What goes wrong:** There are TWO occurrences of the config path bug in `host/main.py` — line 87 (`ConfigLoader("config.json", ...)`) AND line 92 (`os.path.dirname(os.path.abspath("config.json"))`). The second one computes the directory for the Pomodoro command file watcher. Both must be fixed.
**How to avoid:** After replacing with `get_config_path()`, use `get_config_path().parent` for the directory, eliminating line 92's `os.path.dirname(os.path.abspath(...))` entirely.

---

## Code Examples

Verified patterns based on Python stdlib documentation:

### get_config_path() — canonical implementation
```python
# shared/paths.py
# Source: Python docs — pathlib.Path.resolve()
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent

def get_config_path() -> Path:
    """Return the absolute path to config.json regardless of launch cwd.

    Resolves relative to this file's location, not the process cwd.
    Works correctly under pythonw.exe, HKCU Run key launch, and PyInstaller.
    """
    return _PROJECT_ROOT / "config.json"
```

### Startup null-guard — Option B (recommended)
```python
# host/main.py — insert before any other imports or print calls
import sys
import os

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
```

### safe_print helper — Option A (alternative)
```python
# Can be added to shared/paths.py or a new shared/utils.py
import sys

def safe_print(*args, **kwargs) -> None:
    """print() wrapper safe for pythonw.exe where sys.stdout is None."""
    if sys.stdout is not None:
        print(*args, **kwargs)
```

### Consuming get_config_path in host/main.py
```python
from shared.paths import get_config_path

# Replace:
#   config_loader = ConfigLoader("config.json", pm, window.compositor, after_reload=reapply_clip)
#   config_dir = os.path.dirname(os.path.abspath("config.json"))
# With:
_cfg = get_config_path()
config_loader = ConfigLoader(str(_cfg), pm, window.compositor, after_reload=reapply_clip)
config_dir = str(_cfg.parent)
```

### Consuming get_config_path in control_panel/__main__.py
```python
from shared.paths import get_config_path

# Replace:
#   window = ControlPanelWindow(config_path="config.json")
# With:
window = ControlPanelWindow(config_path=str(get_config_path()))
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `os.path.dirname(os.path.abspath(__file__))` | `pathlib.Path(__file__).resolve().parent` | Python 3.4 (pathlib added) | More readable, returns `Path` object |
| Manual None checks on every print | Startup null-guard once | Always idiomatic for GUI Python | Single fix covers all modules |

**Deprecated/outdated in this codebase:**
- `os.path.abspath("config.json")` at lines 87 and 92 of `host/main.py`: resolves from cwd, not file location. Must be replaced.
- `config_path="config.json"` in `control_panel/__main__.py` line 9: same bug. Must be replaced.

---

## Open Questions

1. **Where should safe_print or the null-guard live?**
   - What we know: Option B (startup null-guard in `host/main.py`) covers all modules with one change. Option A (safe_print helper) requires updating both `main.py` and `config_loader.py`.
   - What's unclear: Whether the project prefers explicit call-site guards (Option A, more grep-able) or implicit once-at-startup fix (Option B, fewer changes).
   - Recommendation: Option B — startup null-guard. It is the idiomatic pattern for Windows GUI Python apps and requires the smallest code delta. Widget subprocesses don't face this problem because they run under `python.exe` (spawned by the host), not `pythonw.exe`.

2. **Should `get_config_path()` return `Path` or `str`?**
   - What we know: Existing callers (`ConfigLoader.__init__`, `ControlPanelWindow.__init__`) accept `str`. Returning `Path` requires `str()` at call sites.
   - What's unclear: Whether future callers (Phase 7 PyInstaller context) will prefer `Path`.
   - Recommendation: Return `Path` from `get_config_path()` (more useful as a value), and convert with `str()` at the two existing call sites. This is more flexible for Phase 7.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing, pytest.ini present) |
| Config file | `pytest.ini` at project root |
| Quick run command | `pytest tests/test_paths.py -x` |
| Full suite command | `pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INFRA-01 | `get_config_path()` returns absolute path ending in `config.json` | unit | `pytest tests/test_paths.py::test_get_config_path_is_absolute -x` | Wave 0 |
| INFRA-01 | `get_config_path()` returns same path regardless of cwd | unit | `pytest tests/test_paths.py::test_get_config_path_cwd_independent -x` | Wave 0 |
| INFRA-01 | No bare `"config.json"` string in `host/main.py` or `control_panel/__main__.py` | unit (import check) | `pytest tests/test_paths.py::test_no_bare_config_strings -x` | Wave 0 |
| INFRA-02 | Host entry point does not crash when `sys.stdout` is `None` | unit | `pytest tests/test_paths.py::test_safe_print_with_null_stdout -x` | Wave 0 |
| INFRA-02 | Host entry point does not crash when `sys.stderr` is `None` | unit | `pytest tests/test_paths.py::test_safe_print_with_null_stderr -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `pytest tests/test_paths.py -x`
- **Per wave merge:** `pytest`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_paths.py` — covers INFRA-01 and INFRA-02; does not yet exist

*(All other test infrastructure — pytest.ini, conftest.py, existing test files — is already in place.)*

---

## Sources

### Primary (HIGH confidence)
- Python stdlib docs — `pathlib.Path.resolve()` behavior with relative `__file__`
- Python stdlib docs — `sys.stdout` / `sys.stderr` being `None` under `pythonw.exe` is documented in the Python Windows FAQ
- Direct code audit of `host/main.py`, `host/config_loader.py`, `control_panel/__main__.py` — all bare config path usages identified by reading actual source

### Secondary (MEDIUM confidence)
- Python Windows FAQ: "Why does my GUI application freeze on Windows?" — confirms sys.stdout is None under pythonw.exe
- PyInstaller docs: `sys._MEIPASS` and `__file__` behavior in frozen context — relevant context for Phase 7; `pathlib`-based resolution works correctly in frozen .exe if config is in same dir as executable

### Tertiary (LOW confidence)
- None. Both fixes are stdlib-only with clear official documentation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all stdlib; no third-party libraries
- Architecture: HIGH — direct code audit of actual source files identifies exact lines to change
- Pitfalls: HIGH — bugs identified from actual source, not hypothetical

**Research date:** 2026-03-27
**Valid until:** Stable (stdlib-only, no version sensitivity)
