# Phase 3: Pomodoro + Calendar Widgets - Research

**Researched:** 2026-03-26
**Domain:** Pillow off-screen rendering, Python state machines, PyQt6 control panel extension, command-file IPC
**Confidence:** HIGH

## Summary

Phase 3 builds two real widget subprocesses — a Pomodoro timer and a Calendar display — using the WidgetBase/Pillow/queue/compositor pipeline established in Phases 1 and 2. Every architectural constraint (no PyQt6 in subprocesses, non-blocking puts, queue.Full guard) is already proven in the DummyWidget reference. Both widgets render RGBA frames via Pillow and push FrameData to the host every second. The Pomodoro widget adds a new message type (ControlSignal) to message_schema.py and requires a second QFileSystemWatcher in the host for command-file delivery.

The implementation is low-risk technically: Pillow 12.1.1 is installed and all APIs verified working (textbbox centering, RGBA tobytes, ImageFont.truetype). The state machine is simple Python (Enum + integer countdown). The command-file pattern for Pomodoro controls (atomic write + QFileSystemWatcher) exactly mirrors the existing config hot-reload pattern. All 53 existing tests pass and the test infrastructure (pytest + conftest fixtures) is fully operational.

The control panel already has placeholder tab methods (_build_pomodoro_tab, _build_calendar_tab) and _load_values/_collect_config/_update_widget_settings methods ready for extension. config.json currently holds a single dummy widget; Phase 3 replaces it with pomodoro + calendar entries and adds a shortcuts section.

**Primary recommendation:** Implement in three sequential plans — (1) widget subprocess code + config.json update + widget registration, (2) ControlSignal IPC + command-file watcher + Pomodoro controls in control panel, (3) font bundling + control panel extensions (font selectors, accent color pickers, shortcut editor) + hardware verification.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Slot Geometry**
- Display carve-up is equal thirds (1920 / 3 = 640px each), all full 515px height:
  - Pomodoro: `x=0, y=0, width=640, height=515`
  - Calendar: `x=640, y=0, width=640, height=515`
  - Notification slot (Phase 4, reserved): `x=1280, y=0, width=640, height=515`
- The dummy widget is removed from `config.json`; Phase 3 replaces it with the two real widget entries

**Visual Style**
- Background color: dark/near-black — `#1a1a2e` (or similar; Claude has discretion on exact shade)
- Text layout within each slot: centered both horizontally and vertically
- Font approach: bundle three TTF files with the widget package (no system-font lookup at runtime):
  - **Inter** — clean readable sans-serif (default for both widgets)
  - **Digital-7** — LCD-style digital clock aesthetic
  - **Share Tech Mono** — cyber monospace feel
- Each widget has its own font setting in config.json and in the control panel (independent selectors)

**Pomodoro Visual Design**
- Accent color per state (text/countdown color changes by state):
  - WORK → red (default `#ff4444`)
  - SHORT_BREAK → green (default `#44ff44`)
  - LONG_BREAK → blue (default `#4488ff`)
- All three accent colors are configurable in the control panel (Pomodoro tab)
- Config keys: `work_accent_color`, `short_break_accent_color`, `long_break_accent_color` (hex strings)
- IDLE state displays: phase label "Focus" + full work duration countdown frozen (e.g., "25:00") — same visual as WORK state but timer is not running

**Pomodoro Controls in the Control Panel**
- Add a **"Controls" QGroupBox** above the existing "Pomodoro Durations" group in the Pomodoro tab
- Three buttons in a row: **[Start]  [Pause]  [Reset]**
- Keyboard shortcuts (configurable in control panel settings, defaults):
  - Start → `Ctrl+S`
  - Pause → `Ctrl+P`
  - Reset → `Ctrl+R`
- Shortcut key bindings are stored in config.json under a `shortcuts` section and editable in the control panel
- Signal delivery mechanism: **dedicated command file** (`pomodoro_command.json` in the same directory as `config.json`)
  - Control panel writes `{"cmd": "start" | "pause" | "reset"}` atomically (temp + os.replace)
  - Host watches this file via a second `QFileSystemWatcher`; on change, reads the command, forwards to Pomodoro widget via `in_queue` as a new `ControlSignal` message type, then deletes the file
  - ControlSignal is a new dataclass in `shared/message_schema.py`: `widget_id: str, command: str`

**Calendar Visual Design**
- Font: per-widget font selector (same three bundled options), default Inter
- Config key: `font` in calendar widget settings
- Seconds: not displayed in v1 (deferred as PLSH-04)
- Date format: locale-aware full date (day of week + full date), time in 12h or 24h per config

**config.json Extensions**
Phase 3 adds to `config.json`:
```json
{
  "widgets": [
    {
      "id": "pomodoro",
      "type": "pomodoro",
      "x": 0, "y": 0, "width": 640, "height": 515,
      "settings": {
        "work_minutes": 25,
        "short_break_minutes": 5,
        "long_break_minutes": 15,
        "cycles_before_long_break": 4,
        "font": "Inter",
        "work_accent_color": "#ff4444",
        "short_break_accent_color": "#44ff44",
        "long_break_accent_color": "#4488ff"
      }
    },
    {
      "id": "calendar",
      "type": "calendar",
      "x": 640, "y": 0, "width": 640, "height": 515,
      "settings": {
        "clock_format": "24h",
        "font": "Inter"
      }
    }
  ],
  "shortcuts": {
    "pomodoro_start": "Ctrl+S",
    "pomodoro_pause": "Ctrl+P",
    "pomodoro_reset": "Ctrl+R"
  }
}
```

### Claude's Discretion
- Exact dark background hex value (#1a1a2e or similar near-black)
- Font sizes for label vs countdown/time (should be legible on the 640x515 slot)
- Pillow rendering details (ImageDraw, textbbox centering math)
- QFileSystemWatcher setup for `pomodoro_command.json`
- ControlSignal message dispatch logic in host
- Pomodoro state machine tick interval (1-second sleep loop vs threading.Timer)
- Test strategy for state machine and rendering pipeline

### Deferred Ideas (OUT OF SCOPE)
- Seconds display on Calendar — already tracked as PLSH-04 (v2), explicitly deferred
- Configurable display selection (not hardcoded to Display 3) — EXT-02 (v2)
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| POMO-01 | Pomodoro widget runs as an isolated subprocess implementing `WidgetBase`; renders to RGBA bytes via Pillow and pushes `FrameData` to the host queue | DummyWidget reference pattern fully applicable; Pillow 12.1.1 RGBA tobytes verified working |
| POMO-02 | Pomodoro implements a full state machine: IDLE → WORK → SHORT_BREAK → LONG_BREAK → WORK, with auto-advance at countdown zero and cycle counting for long-break promotion | State machine logic verified with Python Enum; cycle counting pattern tested (4 cycles → LONG_BREAK) |
| POMO-03 | Pomodoro displays the current phase label (Focus / Short Break / Long Break) and a MM:SS countdown, updated every second | Pillow textbbox centering math verified; MM:SS format f'{m:02d}:{s:02d}' tested |
| POMO-04 | Pomodoro responds to control signals (start, pause, reset) sent from the host/control panel via a second inbound queue | ControlSignal dataclass pattern designed; command-file + QFileSystemWatcher pattern verified; in_queue dispatch logic tested |
| POMO-05 | Work duration, short break duration, long break duration, and cycles-before-long-break are all configurable via `config.json` and applied on CONFIG_UPDATE without restarting the widget process | poll_config_update() extension pattern verified; CONFIG_UPDATE arrives via existing in_queue path |
| CAL-01 | Calendar widget runs as an isolated subprocess implementing `WidgetBase`; renders the current local time and date to RGBA bytes via Pillow and pushes `FrameData` at a 1-second interval | Same push pattern as Pomodoro; 1Hz push rate well within maxsize=10 queue; verified non-blocking |
| CAL-02 | Calendar displays day of week, full date (locale-aware format), and time in either 12h or 24h format as configured in `config.json` | datetime strftime patterns verified: `%A, %B %#d, %Y` for Windows no-zero day; `%I:%M %p` for 12h, `%H:%M` for 24h |
| CAL-03 | Clock format (12h/24h) is configurable via the control panel and applied on CONFIG_UPDATE without restarting the widget process | poll_config_update() pattern; existing clock_format field in control panel already wired |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Pillow | 12.1.1 (installed, verified) | Off-screen RGBA rendering; ImageDraw, ImageFont, textbbox | Only rendering library safe to use in widget subprocesses (no Qt context) |
| Python stdlib: `datetime` | 3.x | Date/time formatting for Calendar widget | No dependency; strftime covers all required formats |
| Python stdlib: `enum` | 3.x | PomodoroState state machine (IDLE/WORK/SHORT_BREAK/LONG_BREAK) | Clean, Pythonic; isinstance checks work in subprocess |
| Python stdlib: `time` | 3.x | Monotonic countdown timing in Pomodoro run loop | time.monotonic() avoids clock adjustment drift |
| Python stdlib: `threading` | 3.x | Optional: threading.Event for clean test isolation of widget loops | Already used in test_dummy_widget.py pattern |
| PyQt6 | 6.10.2 (installed) | QFileSystemWatcher (command file), QShortcut (keyboard shortcuts), QKeySequence — host/control panel side only | Already installed; widget subprocess must NOT import |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Python stdlib: `queue` | 3.x | queue.Full guard in non-blocking put | Always — same pattern as DummyWidget |
| Python stdlib: `os`, `tempfile`, `json` | 3.x | Atomic command-file write (os.replace pattern) | Command-file writes from control panel |
| Python stdlib: `pathlib` | 3.x | Font path resolution relative to widget package `__file__` | Font loading in widget subprocess |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Command-file + QFileSystemWatcher | Direct in_queue from control panel | Control panel runs in separate process; no shared memory; command-file is the only safe cross-process signal path that doesn't require the host as intermediary |
| threading.Event for tick loop | threading.Timer | threading.Timer schedules repeated calls; harder to cancel cleanly; sleep loop with monotonic deadline is simpler and sufficient for 1Hz updates |
| ImageFont.load_default(size=N) as fallback | Always require bundled font | Fallback prevents crash if font file missing; use truetype when available |

**Installation:** No new packages needed. Pillow is already installed. Add `Pillow==12.1.1` to requirements.txt.

**Version verification (confirmed):**
```
Pillow: 12.1.1 (python -c "import PIL; print(PIL.__version__)")
PyQt6: 6.10.2 (already in requirements.txt)
```

## Architecture Patterns

### Recommended Project Structure
```
widgets/
├── __init__.py
├── base.py                  # WidgetBase ABC (existing)
├── dummy/                   # Reference widget (existing)
│   └── widget.py
├── pomodoro/                # New
│   ├── __init__.py
│   ├── widget.py            # PomodoroWidget(WidgetBase) + run_pomodoro_widget()
│   └── fonts/               # Bundled TTF files
│       ├── Inter-Regular.ttf
│       ├── Digital-7.ttf
│       └── ShareTechMono-Regular.ttf
└── calendar/                # New
    ├── __init__.py
    ├── widget.py            # CalendarWidget(WidgetBase) + run_calendar_widget()
    └── fonts/               # Bundled TTF files (same three files, or symlinks)
        ├── Inter-Regular.ttf
        ├── Digital-7.ttf
        └── ShareTechMono-Regular.ttf

shared/
└── message_schema.py        # Add ControlSignal dataclass

host/
└── main.py                  # Add register_widget_type calls + second QFileSystemWatcher

control_panel/
└── main_window.py           # Extend _build_pomodoro_tab(), _build_calendar_tab(),
                             #   _load_values(), _collect_config()
```

### Pattern 1: WidgetBase Subprocess Entry Point
**What:** Every widget module exports a top-level `run_<name>_widget(widget_id, config, out_q, in_q)` function that ProcessManager calls as the subprocess target.
**When to use:** All widgets (mandatory contract).
**Example:**
```python
# Source: widgets/dummy/widget.py (existing reference)
def run_pomodoro_widget(widget_id: str, config: dict, out_queue, in_queue) -> None:
    """Subprocess entry point. Called by ProcessManager."""
    widget = PomodoroWidget(widget_id, config, out_queue, in_queue)
    widget.run()
```

### Pattern 2: Non-Blocking Frame Push
**What:** Always use `put(block=False)` with `except queue.Full: pass` — never block the subprocess.
**When to use:** Every frame push in every widget.
**Example:**
```python
# Source: widgets/dummy/widget.py (existing reference)
try:
    self.out_queue.put(frame, block=False)
except queue.Full:
    pass  # Host drain is slow; drop this frame
```

### Pattern 3: Pillow RGBA Centering Math
**What:** Use `textbbox((0, 0), text, font=font)` to get tight bounding box, then compute centered position. The bbox origin offset (bbox[0], bbox[1]) must be subtracted from draw position to handle fonts with non-zero ascent.
**When to use:** Any text drawn to a Pillow RGBA image.
**Example (verified 2026-03-26):**
```python
# Source: verified locally with Pillow 12.1.1
from PIL import Image, ImageDraw, ImageFont

img = Image.new('RGBA', (W, H), (26, 26, 46, 255))
draw = ImageDraw.Draw(img)

bbox = draw.textbbox((0, 0), text, font=font)
text_w = bbox[2] - bbox[0]
text_h = bbox[3] - bbox[1]
x = (W - text_w) // 2 - bbox[0]
y = (H - text_h) // 2 - bbox[1]
draw.text((x, y), text, font=font, fill=color)

rgba_bytes = img.tobytes()  # Returns width*height*4 bytes, RGBA order
```

### Pattern 4: Stacked Multi-Line Centering (Label + Timer)
**What:** Compute total height of two text elements with gap, then offset each from the center-aligned start Y.
**When to use:** Pomodoro (label above timer), Calendar (time above date).
**Example (verified 2026-03-26):**
```python
# Source: verified locally with Pillow 12.1.1
lbbox = draw.textbbox((0, 0), label, font=font_label)
tbbox = draw.textbbox((0, 0), timer, font=font_timer)
lw, lh = lbbox[2]-lbbox[0], lbbox[3]-lbbox[1]
tw, th = tbbox[2]-tbbox[0], tbbox[3]-tbbox[1]
gap = 20
total_h = lh + gap + th
start_y = (H - total_h) // 2

lx = (W - lw) // 2 - lbbox[0]
ly = start_y - lbbox[1]
draw.text((lx, ly), label, font=font_label, fill=label_color)

tx = (W - tw) // 2 - tbbox[0]
ty = start_y + lh + gap - tbbox[1]
draw.text((tx, ty), timer, font=font_timer, fill=accent_color)
```

### Pattern 5: Font Loading with __file__-Relative Path
**What:** Load bundled TTF using path relative to the widget module's `__file__`, with fallback to default font if file missing.
**When to use:** All widget subprocess font loading (never system font lookup).
**Example:**
```python
# Source: Pillow 12.1.1 ImageFont API
import pathlib
from PIL import ImageFont

def _load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    fonts_dir = pathlib.Path(__file__).parent / 'fonts'
    font_map = {
        'Inter': fonts_dir / 'Inter-Regular.ttf',
        'Digital-7': fonts_dir / 'Digital-7.ttf',
        'Share Tech Mono': fonts_dir / 'ShareTechMono-Regular.ttf',
    }
    path = font_map.get(font_name)
    if path and path.exists():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)  # fallback, never crashes
```

### Pattern 6: In-Queue Dispatch (ConfigUpdate + ControlSignal)
**What:** poll_in_queue handles both ConfigUpdateMessage and ControlSignal from the same in_queue. The base class poll_config_update() is insufficient for Pomodoro (it discards non-ConfigUpdateMessage items). Override or replace with a widget-local poll that handles both types.
**When to use:** PomodoroWidget run loop — must handle both message types.
**Example (verified 2026-03-26):**
```python
# Source: verified locally
def _poll_in_queue(self):
    """Returns (new_config, command) — either or both may be None."""
    try:
        msg = self.in_queue.get_nowait()
        if isinstance(msg, ConfigUpdateMessage):
            return msg.config, None
        elif isinstance(msg, ControlSignal):
            return None, msg.command
    except queue.Empty:
        pass
    return None, None
```

### Pattern 7: Command-File Atomic Write (Control Panel Side)
**What:** Write command JSON to `pomodoro_command.json` using the same atomic temp+replace pattern as config.json writes. The host's second QFileSystemWatcher fires on the replace, reads the command, forwards to Pomodoro in_queue as ControlSignal, then deletes the file.
**When to use:** Pomodoro Start/Pause/Reset button clicks in the control panel.
**Example:**
```python
# Source: mirrors control_panel/config_io.py atomic_write_config pattern
import json, os, tempfile

def write_pomodoro_command(config_dir: str, command: str) -> None:
    cmd_path = os.path.join(config_dir, 'pomodoro_command.json')
    dir_path = os.path.dirname(os.path.abspath(cmd_path))
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix='.tmp')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'cmd': command}, f)
        os.replace(tmp, cmd_path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

### Pattern 8: Second QFileSystemWatcher in host/main.py
**What:** Set up a second QFileSystemWatcher for `pomodoro_command.json` alongside the existing config watcher. On fileChanged, re-add the path (survives atomic replace), read the command file, forward ControlSignal to ProcessManager, delete the file.
**When to use:** host/main.py setup, after ProcessManager and config_loader are initialized.
**Example:**
```python
# Source: mirrors host/config_loader.py QFileSystemWatcher re-add pattern
from PyQt6.QtCore import QFileSystemWatcher

cmd_path = os.path.join(os.path.dirname(config_path), 'pomodoro_command.json')
cmd_watcher = QFileSystemWatcher()

def _on_cmd_file_changed(path: str):
    cmd_watcher.addPath(cmd_path)  # re-add after atomic replace
    if not os.path.exists(cmd_path):
        return
    try:
        with open(cmd_path, encoding='utf-8') as f:
            data = json.load(f)
        command = data.get('cmd')
        if command in ('start', 'pause', 'reset'):
            pm.send_control_signal('pomodoro', command)
        os.unlink(cmd_path)
    except (OSError, json.JSONDecodeError):
        pass

cmd_watcher.fileChanged.connect(_on_cmd_file_changed)
window._cmd_watcher = cmd_watcher  # prevent GC
```

### Pattern 9: Pomodoro State Machine Tick Loop
**What:** Use `time.monotonic()` deadline for drift-free countdown. Sleep in 100ms increments to allow in_queue polls and config updates without missing a second boundary.
**When to use:** Pomodoro WORK/SHORT_BREAK/LONG_BREAK states.
**Example (verified 2026-03-26):**
```python
# Source: verified locally; time.monotonic() confirmed non-drifting
import time

def _run_countdown(self, duration_secs: int):
    """Run one countdown phase. Returns True if completed naturally, False if interrupted."""
    deadline = time.monotonic() + duration_secs
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return True  # completed
        # Poll in_queue during countdown
        new_cfg, cmd = self._poll_in_queue()
        if new_cfg:
            self._apply_config(new_cfg)
        if cmd == 'pause':
            return False  # interrupted
        if cmd == 'reset':
            return None   # reset signal
        # Push frame with current remaining
        self._push_frame(remaining)
        time.sleep(min(remaining, 0.1))
```

### Pattern 10: QKeySequence Shortcut Binding in Control Panel
**What:** Create QShortcut bound to the ControlPanelWindow widget. Call setKey() to update shortcut when config changes. Store shortcuts dict as instance variable.
**When to use:** Pomodoro keyboard shortcuts in ControlPanelWindow.
**Example (verified 2026-03-26):**
```python
# Source: verified locally with PyQt6 6.10.2
from PyQt6.QtGui import QShortcut, QKeySequence

# In _build_pomodoro_tab or __init__:
self._shortcut_start = QShortcut(QKeySequence('Ctrl+S'), self)
self._shortcut_start.activated.connect(self._on_pomodoro_start)

# To update shortcut from config:
self._shortcut_start.setKey(QKeySequence(shortcuts.get('pomodoro_start', 'Ctrl+S')))
```

### Anti-Patterns to Avoid
- **Importing PyQt6 in any widget module:** Any `import PyQt6` or `from PyQt6` in `widgets/pomodoro/widget.py` or `widgets/calendar/widget.py` will crash the subprocess on Windows spawn start method. Zero tolerance.
- **Blocking queue.put():** `put(block=True)` in the widget run loop stalls the subprocess indefinitely when the host drain falls behind. Always `block=False` with `queue.Full` guard.
- **System font lookup at runtime:** `ImageFont.truetype('Inter')` without a path uses system font directories, which are not guaranteed on Windows and vary by environment. Always use `__file__`-relative paths to bundled fonts.
- **textsize() instead of textbbox():** `textsize()` was removed in Pillow 10.0.0. Pillow 12.1.1 requires `textbbox()` for measuring text dimensions.
- **Blocking puts in the command-file watcher callback:** The `_on_cmd_file_changed` callback runs on the Qt main thread. Never call `in_q.put()` with `block=True` here — use `put_nowait()` (already the pattern in `ProcessManager.send_config_update()`).
- **Sharing fonts directory between widget packages:** Each widget subdirectory should have its own `fonts/` directory. This keeps package boundaries clean and avoids cross-package path assumptions in subprocesses.
- **Using threading.Timer for per-second ticks:** threading.Timer accumulates drift over time. time.monotonic() deadline with sleep(min(remaining, 0.1)) is drift-free and simpler to reset/cancel.
- **Calling join() in stop_widget for the new widgets:** The existing ProcessManager.stop_widget() already avoids join() to prevent Qt main thread deadlock (Decision #10 in STATE.md). No change needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Text bounding box measurement | Custom character width tables | `draw.textbbox((0,0), text, font=font)` | Pillow handles kerning, font metrics, Unicode; custom tables are wrong for every font |
| Locale-aware date formatting | String concatenation of month/day/year | `datetime.now().strftime('%A, %B %#d, %Y')` | strftime handles locale, leap years, zero-padding |
| Atomic file write | Open file and write directly | `tempfile.mkstemp + os.replace` (already in config_io.py) | Direct write risks partial reads by the watcher; the existing `atomic_write_config` pattern handles this correctly |
| Cross-process signal delivery | Shared memory, sockets, pipes | Command file + QFileSystemWatcher (mirrors config hot-reload) | Same pattern already proven; zero new dependencies |
| RGBA color hex parsing | Manual `int(hex[1:3], 16)` parsing | `PIL.ImageColor.getrgb('#ff4444')` | Handles all hex formats, named colors, raises on invalid |

**Key insight:** The entire Phase 3 implementation reuses patterns that are already working and tested in Phases 1 and 2. The risk surface is font loading (new) and the command-file IPC (new but structurally identical to the config hot-reload pattern).

## Common Pitfalls

### Pitfall 1: textsize() Removed in Pillow 10+
**What goes wrong:** Code using `draw.textsize(text, font=font)` raises `AttributeError: 'ImageDraw' object has no attribute 'textsize'`.
**Why it happens:** textsize() was deprecated in Pillow 9.2.0 and removed in 10.0.0. Pillow 12.1.1 has no textsize().
**How to avoid:** Always use `draw.textbbox((0, 0), text, font=font)` and compute width as `bbox[2]-bbox[0]`, height as `bbox[3]-bbox[1]`.
**Warning signs:** ImportError or AttributeError on first frame render.

### Pitfall 2: textbbox bbox[0] / bbox[1] Non-Zero Offset
**What goes wrong:** Text drawn at `((W - text_w) // 2, (H - text_h) // 2)` appears shifted up/left because bbox origin is non-zero (font has ascent/descent padding).
**Why it happens:** `textbbox((0,0), ...)` measures the bounding box with origin at (0,0) but the box may start at e.g. (0, 2) — meaning the top-left of the rendered glyph is at y=2, not y=0.
**How to avoid:** Subtract `bbox[0]` from x and `bbox[1]` from y: `x = (W - text_w) // 2 - bbox[0]`.
**Warning signs:** Visually off-center text when inspecting rendered frames.

### Pitfall 3: QFileSystemWatcher Loses Watch After Atomic Replace
**What goes wrong:** Second command-file watcher stops firing after the first command is processed (because os.replace drops the watched path).
**Why it happens:** Same as config.json watcher (Decision #16 in STATE.md) — `os.replace` atomically replaces the inode, which drops the watch.
**How to avoid:** Always call `cmd_watcher.addPath(cmd_path)` as the first line of the `fileChanged` callback, even if the file was deleted.
**Warning signs:** First Start/Pause/Reset command works; subsequent ones are silently ignored.

### Pitfall 4: Font File Not Found Crashes Subprocess
**What goes wrong:** `ImageFont.truetype(str(path), size=48)` raises `OSError: cannot open resource` when the TTF file is not at the expected path. The subprocess dies silently.
**Why it happens:** Font files must be added to the repository and committed. Missing from git, or wrong path relative to `__file__`.
**How to avoid:** Always implement a fallback: `try/except OSError → ImageFont.load_default(size=size)`. The fallback renders ugly but never crashes.
**Warning signs:** Widget process dies immediately after spawn; no frames appear in its slot.

### Pitfall 5: Config Update Applies Mid-Countdown
**What goes wrong:** A CONFIG_UPDATE arrives mid-countdown with new `work_minutes=30`. If applied immediately, the current WORK phase restarts at 30 minutes instead of continuing.
**Why it happens:** Naive application of new config dict mid-run recalculates remaining time.
**How to avoid:** Per the locked decisions (POMO-05): "applied on next phase transition without restarting the widget process." Store the new config but only apply durations when transitioning to a new state. Non-duration settings (font, colors) can be applied immediately.
**Warning signs:** Timer resets unexpectedly during active work sessions.

### Pitfall 6: ControlSignal Not Imported in Widget Subprocess
**What goes wrong:** `isinstance(msg, ControlSignal)` always returns False because the imported `ControlSignal` class in the subprocess is a different object than what the host pickled.
**Why it happens:** Python multiprocessing on Windows spawn re-imports all modules. If the import path differs (e.g., `shared.message_schema` vs relative import), isinstance fails silently.
**How to avoid:** Always use absolute imports in widget.py: `from shared.message_schema import ControlSignal, ConfigUpdateMessage`. Verify host sends from the same module path.
**Warning signs:** Commands dispatched from control panel appear to be received by the widget (queue is drained) but have no effect.

### Pitfall 7: Missing __init__.py in New Widget Packages
**What goes wrong:** `import widgets.pomodoro.widget` fails with `ModuleNotFoundError` in the subprocess.
**Why it happens:** Python spawn start method re-imports from scratch; the package directory needs `__init__.py` files.
**How to avoid:** Create `widgets/pomodoro/__init__.py` and `widgets/calendar/__init__.py` (can be empty) alongside widget.py.
**Warning signs:** Widget process fails to start; ProcessManager shows process died immediately.

### Pitfall 8: Keyboard Shortcuts Conflict with Other Applications
**What goes wrong:** `Ctrl+S` fires the Pomodoro start command even when the control panel is not in focus (if the shortcut is set to application-wide).
**Why it happens:** Qt shortcuts default to `ShortcutContext.WindowShortcut` — fires only when the window is active. This is the correct behavior. If accidentally set to `ApplicationShortcut`, it fires globally.
**How to avoid:** Use the default `WindowShortcut` context (do not set `setContext(Qt.ShortcutContext.ApplicationShortcut)`). The shortcut only activates when the ControlPanelWindow has focus — correct behavior.
**Warning signs:** Ctrl+S triggers Pomodoro start while user is typing in another application.

## Code Examples

Verified patterns from official sources and local verification:

### Pomodoro MM:SS Formatting
```python
# Source: verified locally 2026-03-26
def format_mm_ss(total_seconds: int) -> str:
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f'{minutes:02d}:{seconds:02d}'

# Results: format_mm_ss(1500) = '25:00', format_mm_ss(277) = '04:37'
```

### Calendar strftime Patterns (Windows)
```python
# Source: verified locally 2026-03-26 on Windows 11
import datetime
now = datetime.datetime.now()

# Day of week + date (Windows: %#d removes leading zero)
now.strftime('%A, %B %#d, %Y')   # "Thursday, March 26, 2026"

# 12h time
now.strftime('%I:%M %p')          # "09:01 PM"

# 24h time
now.strftime('%H:%M')             # "21:01"
```

**Important:** `%#d` (Windows flag for no-leading-zero day) is Windows-specific. Linux uses `%-d`. Since this project is Windows-only (see REQUIREMENTS.md Out of Scope), `%#d` is correct.

### PIL ImageColor for Hex Color Parsing
```python
# Source: Pillow 12.1.1 ImageColor module
from PIL import ImageColor

# Parse accent color from config (hex string → RGBA tuple)
def hex_to_rgba(hex_color: str, alpha: int = 255) -> tuple:
    rgb = ImageColor.getrgb(hex_color)  # returns (R, G, B)
    return rgb + (alpha,)               # returns (R, G, B, A)

# hex_to_rgba('#ff4444') → (255, 68, 68, 255)
```

### ControlSignal Dataclass (to add to shared/message_schema.py)
```python
# Source: pattern derived from existing ConfigUpdateMessage
from dataclasses import dataclass

@dataclass
class ControlSignal:
    """Sent host -> widget via in_queue to deliver control commands."""
    widget_id: str
    command: str  # 'start' | 'pause' | 'reset'
```

### ProcessManager.send_control_signal (to add to host/process_manager.py)
```python
# Source: mirrors existing send_config_update pattern
def send_control_signal(self, widget_id: str, command: str) -> None:
    entry = self._widgets.get(widget_id)
    if entry is None:
        return
    _, _, in_q = entry
    try:
        in_q.put_nowait(ControlSignal(widget_id=widget_id, command=command))
    except queue.Full:
        pass
```

### QSpinBox + QLineEdit for Shortcut Editing in Control Panel
```python
# Source: verified PyQt6 6.10.2 locally
from PyQt6.QtWidgets import QLineEdit
from PyQt6.QtGui import QKeySequence

# Shortcut editor: QLineEdit that shows the shortcut string
self._shortcut_start_edit = QLineEdit()
self._shortcut_start_edit.setPlaceholderText('e.g. Ctrl+S')
# On load: self._shortcut_start_edit.setText(shortcuts.get('pomodoro_start', 'Ctrl+S'))
# On save: new_key = self._shortcut_start_edit.text()
#          QKeySequence(new_key)  # validates; empty string → disabled
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `draw.textsize(text, font)` | `draw.textbbox((0,0), text, font=font)` | Pillow 9.2.0 deprecated / 10.0.0 removed | All text measurement must use textbbox |
| `ImageFont.truetype('fontname')` system lookup | `ImageFont.truetype(absolute_path, size)` | Always project-specific; no change | Bundle fonts with widget, never system lookup |
| `winsdk` package for WinRT | `winrt-Windows.*` modular packages | October 2024 (winsdk archived) | N/A for Phase 3; relevant for Phase 4 |

**Deprecated/outdated:**
- `draw.textsize()`: Removed in Pillow 10.0.0. Do not use.
- `draw.textlength()`: Available but only returns width, not height. Use textbbox for both.

## Open Questions

1. **Font file licensing and download**
   - What we know: Inter (SIL OFL), Digital-7 (freeware), Share Tech Mono (SIL OFL) are all freely redistributable
   - What's unclear: Exact download URLs and whether to commit TTF files to git or download at build time
   - Recommendation: Commit TTF files to git (they are small, ~100-300KB each; SIL OFL permits redistribution). Download from Google Fonts (Inter, Share Tech Mono) and dafont.com (Digital-7).

2. **Font sizes for 640x515 legibility**
   - What we know: Default font at size=72 renders "25:00" at ~123px wide, which fits well in 640px width
   - What's unclear: Whether Digital-7 and Share Tech Mono at the same sizes look proportionally correct
   - Recommendation: Plan should specify label size=36 and timer/time size=80 as starting values; implementer has discretion to tune.

3. **Calendar multi-line layout: which line first**
   - What we know: "day of week, full date, and time" (CAL-02) — three pieces of content
   - What's unclear: Exact vertical ordering (time on top or bottom)
   - Recommendation: Render as three stacked lines: time (largest font, top), day+date (medium font, below). This matches typical clock widget conventions.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (>=8.0, verified working — 53 tests pass) |
| Config file | `pytest.ini` (testpaths = tests, integration marker defined) |
| Quick run command | `python -m pytest tests/ -m "not integration" -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| POMO-01 | Pomodoro subprocess pushes FrameData; no PyQt6 import | unit | `pytest tests/test_pomodoro_widget.py -x` | Wave 0 |
| POMO-02 | State machine: IDLE→WORK→SHORT_BREAK→LONG_BREAK cycle counting | unit | `pytest tests/test_pomodoro_widget.py::test_state_machine -x` | Wave 0 |
| POMO-03 | MM:SS countdown rendering; label + timer frame content | unit | `pytest tests/test_pomodoro_widget.py::test_frame_content -x` | Wave 0 |
| POMO-04 | ControlSignal dispatch: start/pause/reset change state | unit | `pytest tests/test_pomodoro_widget.py::test_control_signals -x` | Wave 0 |
| POMO-05 | CONFIG_UPDATE applies new durations on next phase transition | unit | `pytest tests/test_pomodoro_widget.py::test_config_update -x` | Wave 0 |
| CAL-01 | Calendar subprocess pushes FrameData at 1Hz; no PyQt6 import | unit | `pytest tests/test_calendar_widget.py -x` | Wave 0 |
| CAL-02 | 12h and 24h format strings; day-of-week + date rendering | unit | `pytest tests/test_calendar_widget.py::test_date_formats -x` | Wave 0 |
| CAL-03 | CONFIG_UPDATE changes clock_format immediately | unit | `pytest tests/test_calendar_widget.py::test_config_update -x` | Wave 0 |
| POMO-01..05 + CAL-01..03 | End-to-end: both widgets visible in host via real subprocess | integration | `pytest tests/test_e2e_widgets.py -m integration -x` | Wave 0 |
| POMO-04 | ControlSignal reaches widget via command-file → host → in_queue | integration | `pytest tests/test_pomodoro_command_file.py -m integration -x` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -m "not integration" -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pomodoro_widget.py` — covers POMO-01 through POMO-05
- [ ] `tests/test_calendar_widget.py` — covers CAL-01 through CAL-03
- [ ] `tests/test_e2e_widgets.py` — integration test: both widgets spawn and push frames
- [ ] `tests/test_pomodoro_command_file.py` — integration test: command-file → ControlSignal dispatch
- [ ] `widgets/pomodoro/__init__.py` — package marker
- [ ] `widgets/calendar/__init__.py` — package marker
- [ ] `widgets/pomodoro/fonts/` — bundled TTF directory (Inter, Digital-7, Share Tech Mono)
- [ ] `widgets/calendar/fonts/` — bundled TTF directory (same three fonts)

Note: `conftest.py` (session-scoped `qapp` fixture) already exists and covers all Phase 3 control panel tests. No conftest changes needed.

## Sources

### Primary (HIGH confidence)
- Pillow 12.1.1 — verified installed; `textbbox`, `ImageFont.truetype`, `ImageColor.getrgb`, `tobytes()` APIs all verified working locally
- PyQt6 6.10.2 — verified installed; `QFileSystemWatcher`, `QShortcut`, `QKeySequence` APIs verified
- Python stdlib datetime — `strftime` format codes verified on Windows 11 (`%#d` for no-leading-zero)
- `widgets/dummy/widget.py` — authoritative reference for frame push pattern
- `widgets/base.py` — authoritative contract for all widget subprocesses
- `shared/message_schema.py` — authoritative IPC message definitions
- `host/config_loader.py` — authoritative QFileSystemWatcher re-add pattern
- `host/process_manager.py` — authoritative send_config_update pattern
- `control_panel/main_window.py` — confirmed extension points for Phase 3
- `.planning/STATE.md` decisions 10, 11, 13, 16, 19 — confirmed architectural decisions

### Secondary (MEDIUM confidence)
- Python time.monotonic() drift-free timing — standard library behavior, verified locally
- Pillow ImageColor.getrgb() hex parsing — Pillow docs + local verification

### Tertiary (LOW confidence)
- Font file sizes (~100-300KB) and licensing — based on knowledge of Inter/Digital-7/Share Tech Mono; verify at download time
- Digital-7 download source (dafont.com vs other mirrors) — confirm URL before bundling

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — Pillow 12.1.1 and PyQt6 6.10.2 installed and verified; no new dependencies needed
- Architecture: HIGH — All patterns derive from existing working code (dummy widget, config hot-reload, process manager); verified locally
- Pitfalls: HIGH — textbbox migration confirmed against Pillow 12.1.1; QFileSystemWatcher re-add confirmed against existing codebase; subprocess import behavior confirmed against Phase 1 decisions
- Test infrastructure: HIGH — pytest.ini and conftest.py exist; 53 tests green; test patterns well established

**Research date:** 2026-03-26
**Valid until:** 2026-05-01 (stable stack — Pillow, PyQt6, Python stdlib)
