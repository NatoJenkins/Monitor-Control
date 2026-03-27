"""Pomodoro timer widget — subprocess-safe, renders via Pillow."""
import enum
import queue
import time
import pathlib
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont, ImageColor
from shared.message_schema import FrameData, ConfigUpdateMessage, ControlSignal
from widgets.base import WidgetBase


class PomodoroState(enum.Enum):
    IDLE = "idle"
    WORK = "work"
    SHORT_BREAK = "short_break"
    LONG_BREAK = "long_break"


# --- Font loading ---
_FONTS_DIR = pathlib.Path(__file__).parent / "fonts"
_FONT_MAP = {
    "Inter": _FONTS_DIR / "Inter-Regular.ttf",
    "Digital-7": _FONTS_DIR / "Digital-7.ttf",
    "Share Tech Mono": _FONTS_DIR / "ShareTechMono-Regular.ttf",
}


def _load_font(font_name: str, size: int) -> ImageFont.FreeTypeFont:
    path = _FONT_MAP.get(font_name)
    if path and path.exists():
        return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default(size=size)


# State-to-label mapping
_STATE_LABELS = {
    PomodoroState.IDLE: "Focus",
    PomodoroState.WORK: "Focus",
    PomodoroState.SHORT_BREAK: "Short Break",
    PomodoroState.LONG_BREAK: "Long Break",
}


def format_mm_ss(total_seconds: int) -> str:
    """Format seconds as MM:SS. Clamps negative to 00:00."""
    total_seconds = max(0, total_seconds)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}:{seconds:02d}"


class PomodoroWidget(WidgetBase):
    """Pomodoro timer widget. Renders phase label + MM:SS countdown via Pillow."""

    def __init__(self, widget_id, config, out_queue, in_queue):
        super().__init__(widget_id, config, out_queue, in_queue)
        self._width = config.get("width", 640)
        self._height = config.get("height", 515)
        settings = config.get("settings", {})
        self._work_secs = settings.get("work_minutes", 25) * 60
        self._short_break_secs = settings.get("short_break_minutes", 5) * 60
        self._long_break_secs = settings.get("long_break_minutes", 15) * 60
        self._cycles_before_long = settings.get("cycles_before_long_break", 4)
        self._font_name = settings.get("font", "Inter")
        self._work_color = settings.get("work_accent_color", "#ff4444")
        self._short_break_color = settings.get("short_break_accent_color", "#44ff44")
        self._long_break_color = settings.get("long_break_accent_color", "#4488ff")
        self._bg_color = (26, 26, 46, 255)  # #1a1a2e

        self._state = PomodoroState.IDLE
        self._remaining_secs = self._work_secs  # frozen in IDLE
        self._cycle_count = 0  # completed work cycles in current set
        self._deadline = None  # monotonic deadline when counting down
        self._paused_remaining = None  # remaining secs when paused

        # Pending config (applied on next state transition)
        self._pending_durations = None

    def _accent_color(self) -> tuple:
        """Return RGBA tuple for current state accent color."""
        color_map = {
            PomodoroState.IDLE: self._work_color,
            PomodoroState.WORK: self._work_color,
            PomodoroState.SHORT_BREAK: self._short_break_color,
            PomodoroState.LONG_BREAK: self._long_break_color,
        }
        hex_color = color_map.get(self._state, self._work_color)
        rgb = ImageColor.getrgb(hex_color)
        return rgb + (255,) if len(rgb) == 3 else rgb

    def _poll_in_queue(self):
        """Returns (new_config_dict_or_None, command_str_or_None)."""
        try:
            msg = self.in_queue.get_nowait()
            if isinstance(msg, ConfigUpdateMessage):
                return msg.config, None
            elif isinstance(msg, ControlSignal):
                return None, msg.command
        except queue.Empty:
            pass
        return None, None

    def _apply_config(self, cfg: dict) -> None:
        """Apply a CONFIG_UPDATE. Duration changes are deferred to next transition.
        Visual settings (font, colors) apply immediately."""
        settings = cfg.get("settings", {})
        # Immediate: visual
        if "font" in settings:
            self._font_name = settings["font"]
        if "work_accent_color" in settings:
            self._work_color = settings["work_accent_color"]
        if "short_break_accent_color" in settings:
            self._short_break_color = settings["short_break_accent_color"]
        if "long_break_accent_color" in settings:
            self._long_break_color = settings["long_break_accent_color"]
        # Deferred: durations (applied on next state transition)
        new_durations = {}
        if "work_minutes" in settings:
            new_durations["work_secs"] = settings["work_minutes"] * 60
        if "short_break_minutes" in settings:
            new_durations["short_break_secs"] = settings["short_break_minutes"] * 60
        if "long_break_minutes" in settings:
            new_durations["long_break_secs"] = settings["long_break_minutes"] * 60
        if "cycles_before_long_break" in settings:
            new_durations["cycles_before_long"] = settings["cycles_before_long_break"]
        if new_durations:
            self._pending_durations = new_durations

    def _apply_pending_durations(self) -> None:
        """Apply deferred duration changes at state transitions."""
        if self._pending_durations is None:
            return
        d = self._pending_durations
        if "work_secs" in d:
            self._work_secs = d["work_secs"]
        if "short_break_secs" in d:
            self._short_break_secs = d["short_break_secs"]
        if "long_break_secs" in d:
            self._long_break_secs = d["long_break_secs"]
        if "cycles_before_long" in d:
            self._cycles_before_long = d["cycles_before_long"]
        self._pending_durations = None

    def _duration_for_state(self, state: PomodoroState) -> int:
        if state == PomodoroState.WORK:
            return self._work_secs
        elif state == PomodoroState.SHORT_BREAK:
            return self._short_break_secs
        elif state == PomodoroState.LONG_BREAK:
            return self._long_break_secs
        return self._work_secs  # IDLE shows work duration

    def _transition_to(self, new_state: PomodoroState) -> None:
        """Transition to a new state, applying pending durations first."""
        self._apply_pending_durations()
        self._state = new_state
        duration = self._duration_for_state(new_state)
        self._remaining_secs = duration
        if new_state in (PomodoroState.WORK, PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
            self._deadline = time.monotonic() + duration
        else:
            self._deadline = None

    def _handle_command(self, cmd: str) -> None:
        if cmd == "start":
            if self._state == PomodoroState.IDLE:
                self._transition_to(PomodoroState.WORK)
            elif self._paused_remaining is not None:
                # Resume from pause
                self._deadline = time.monotonic() + self._paused_remaining
                self._paused_remaining = None
        elif cmd == "pause":
            if self._deadline is not None and self._paused_remaining is None:
                self._paused_remaining = max(0, self._deadline - time.monotonic())
                self._deadline = None
        elif cmd == "reset":
            self._state = PomodoroState.IDLE
            self._cycle_count = 0
            self._deadline = None
            self._paused_remaining = None
            self._apply_pending_durations()
            self._remaining_secs = self._work_secs

    def _auto_advance(self) -> None:
        """Auto-advance when countdown reaches zero."""
        if self._state == PomodoroState.WORK:
            self._cycle_count += 1
            if self._cycle_count >= self._cycles_before_long:
                self._cycle_count = 0
                self._transition_to(PomodoroState.LONG_BREAK)
            else:
                self._transition_to(PomodoroState.SHORT_BREAK)
        elif self._state in (PomodoroState.SHORT_BREAK, PomodoroState.LONG_BREAK):
            self._transition_to(PomodoroState.WORK)

    def _update_remaining(self) -> None:
        """Update remaining seconds from monotonic deadline."""
        if self._paused_remaining is not None:
            self._remaining_secs = int(self._paused_remaining)
        elif self._deadline is not None:
            remaining = self._deadline - time.monotonic()
            if remaining <= 0:
                self._remaining_secs = 0
                self._auto_advance()
            else:
                self._remaining_secs = int(remaining) + 1  # ceiling: shows "1:00" not "0:59" at 59.5s
        # IDLE: remaining_secs stays at work duration

    def render_frame(self) -> FrameData:
        """Render current state to a Pillow RGBA image and return as FrameData."""
        W, H = self._width, self._height
        img = Image.new("RGBA", (W, H), self._bg_color)
        draw = ImageDraw.Draw(img)

        label = _STATE_LABELS.get(self._state, "Focus")
        timer_str = format_mm_ss(self._remaining_secs)
        accent = self._accent_color()
        label_color = (200, 200, 200, 255)

        font_label = _load_font(self._font_name, 36)
        font_timer = _load_font(self._font_name, 80)

        # Stacked centering: label above timer
        lbbox = draw.textbbox((0, 0), label, font=font_label)
        tbbox = draw.textbbox((0, 0), timer_str, font=font_timer)
        lw, lh = lbbox[2] - lbbox[0], lbbox[3] - lbbox[1]
        tw, th = tbbox[2] - tbbox[0], tbbox[3] - tbbox[1]
        gap = 20
        total_h = lh + gap + th
        start_y = (H - total_h) // 2

        lx = (W - lw) // 2 - lbbox[0]
        ly = start_y - lbbox[1]
        draw.text((lx, ly), label, font=font_label, fill=label_color)

        tx = (W - tw) // 2 - tbbox[0]
        ty = start_y + lh + gap - tbbox[1]
        draw.text((tx, ty), timer_str, font=font_timer, fill=accent)

        return FrameData(
            widget_id=self.widget_id,
            width=W,
            height=H,
            rgba_bytes=img.tobytes(),
        )

    def run(self) -> None:
        """Main loop. Renders at ~10Hz, pushes frames, polls in_queue."""
        while True:
            # Poll in_queue for config updates and control signals
            new_cfg, cmd = self._poll_in_queue()
            if new_cfg:
                self._apply_config(new_cfg)
            if cmd:
                self._handle_command(cmd)

            self._update_remaining()

            frame = self.render_frame()
            try:
                self.out_queue.put(frame, block=False)
            except queue.Full:
                pass

            time.sleep(0.1)  # 10Hz render; 1-second countdown precision is fine


def run_pomodoro_widget(widget_id: str, config: dict, out_queue, in_queue) -> None:
    """Subprocess entry point. Called by ProcessManager."""
    widget = PomodoroWidget(widget_id, config, out_queue, in_queue)
    widget.run()
