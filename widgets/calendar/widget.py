"""Calendar/clock widget — subprocess-safe, renders via Pillow."""
import datetime
import queue
import time
import pathlib
from PIL import Image, ImageColor, ImageDraw, ImageFont
from shared.message_schema import FrameData, ConfigUpdateMessage
from widgets.base import WidgetBase


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


def _safe_hex_color(hex_str: str, default_rgba: tuple) -> tuple:
    """Convert '#rrggbb' to (R, G, B, 255). Returns default_rgba on any error."""
    try:
        r, g, b = ImageColor.getrgb(hex_str)
        return (r, g, b, 255)
    except (ValueError, AttributeError, TypeError):
        return default_rgba


class CalendarWidget(WidgetBase):
    """Displays current time and date. Renders via Pillow at 1Hz."""

    def __init__(self, widget_id, config, out_queue, in_queue):
        super().__init__(widget_id, config, out_queue, in_queue)
        self._width = config.get("width", 640)
        self._height = config.get("height", 515)
        settings = config.get("settings", {})
        self._clock_format = settings.get("clock_format", "24h")
        self._font_name = settings.get("font", "Inter")
        self._time_color = _safe_hex_color(
            settings.get("time_color", "#ffffff"), (255, 255, 255, 255)
        )
        self._text_color = _safe_hex_color(
            settings.get("date_color", "#dcdcdc"), (220, 220, 220, 255)
        )

    def _format_time(self, now: datetime.datetime) -> str:
        if self._clock_format == "12h":
            return now.strftime("%I:%M %p")
        return now.strftime("%H:%M")

    def _format_date(self, now: datetime.datetime) -> str:
        # Windows-specific: %#d for no-leading-zero day
        return now.strftime("%A, %B %#d, %Y")

    def render_frame(self) -> FrameData:
        W, H = self._width, self._height
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        now = datetime.datetime.now()
        time_str = self._format_time(now)
        date_str = self._format_date(now)

        font_time = _load_font(self._font_name, 72)
        font_date = _load_font(self._font_name, 28)

        # Stacked centering: time on top, date below
        t_bbox = draw.textbbox((0, 0), time_str, font=font_time)
        d_bbox = draw.textbbox((0, 0), date_str, font=font_date)
        tw, th = t_bbox[2] - t_bbox[0], t_bbox[3] - t_bbox[1]
        dw, dh = d_bbox[2] - d_bbox[0], d_bbox[3] - d_bbox[1]
        gap = 24
        total_h = th + gap + dh
        start_y = (H - total_h) // 2

        tx = (W - tw) // 2 - t_bbox[0]
        ty = start_y - t_bbox[1]
        draw.text((tx, ty), time_str, font=font_time, fill=self._time_color)

        dx = (W - dw) // 2 - d_bbox[0]
        dy = start_y + th + gap - d_bbox[1]
        draw.text((dx, dy), date_str, font=font_date, fill=self._text_color)

        return FrameData(
            widget_id=self.widget_id,
            width=W,
            height=H,
            rgba_bytes=img.tobytes(),
        )

    def run(self) -> None:
        while True:
            # Poll config updates
            new_cfg = self.poll_config_update()
            if new_cfg:
                settings = new_cfg.get("settings", {})
                if "clock_format" in settings:
                    self._clock_format = settings["clock_format"]
                if "font" in settings:
                    self._font_name = settings["font"]
                if "time_color" in settings:
                    self._time_color = _safe_hex_color(settings["time_color"], (255, 255, 255, 255))
                if "date_color" in settings:
                    self._text_color = _safe_hex_color(settings["date_color"], (220, 220, 220, 255))

            frame = self.render_frame()
            try:
                self.out_queue.put(frame, block=False)
            except queue.Full:
                pass

            time.sleep(1.0)  # 1Hz update — CAL-01


def run_calendar_widget(widget_id: str, config: dict, out_queue, in_queue) -> None:
    """Subprocess entry point. Called by ProcessManager."""
    widget = CalendarWidget(widget_id, config, out_queue, in_queue)
    widget.run()
