"""Notification widget — subprocess-safe, renders via Pillow."""
import asyncio
import datetime
import queue
import time
import pathlib
import textwrap
from PIL import Image, ImageDraw, ImageFont
from shared.message_schema import FrameData
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


class NotificationWidget(WidgetBase):
    """Displays Windows toast notifications. Renders via Pillow at 0.5Hz (2s poll interval)."""

    def __init__(self, widget_id, config, out_queue, in_queue):
        super().__init__(widget_id, config, out_queue, in_queue)
        self._width = config.get("width", 640)
        self._height = config.get("height", 515)
        settings = config.get("settings", {})
        self._font_name = settings.get("font", "Inter")
        self._auto_dismiss_seconds = settings.get("auto_dismiss_seconds", 30)
        self._blocked_apps = set(settings.get("blocked_apps", []))

        # Notification display state
        self._current_notif = None       # tuple (app_name, title, body, timestamp_str) or None
        self._display_since = 0.0        # time.monotonic() when current notification was first displayed
        self._last_notif_id = None       # ID of the notification currently shown (or last seen)

        # Colors (same dark palette as CalendarWidget)
        self._bg_color = (26, 26, 46, 255)          # #1a1a2e
        self._text_color = (220, 220, 220, 255)
        self._muted_color = (140, 140, 160, 255)
        self._title_color = (255, 255, 255, 255)

    def _get_winrt_listener(self):
        """Import and return WinRT listener + status enum. Deferred to avoid import at module level."""
        from winrt.windows.ui.notifications.management import (
            UserNotificationListener,
            UserNotificationListenerAccessStatus,
        )
        return UserNotificationListener.current, UserNotificationListenerAccessStatus

    def _is_allowed(self) -> bool:
        """Return True if notification access is ALLOWED."""
        listener, status_enum = self._get_winrt_listener()
        return listener.get_access_status() == status_enum.ALLOWED

    @staticmethod
    def _safe_app_name(n) -> str:
        """Extract app display name from a UserNotification, falling back on any WinRT error.

        Some system/legacy notifications have app_info.display_info properties that
        raise E_NOTIMPL (0x80004001) when accessed — guard every level individually.
        """
        try:
            if n.app_info is None:
                return "Unknown"
            display_info = n.app_info.display_info
            if display_info is None:
                return "Unknown"
            name = display_info.display_name
            return name if name else "Unknown"
        except Exception:
            return "Unknown"

    def _fetch_latest(self) -> tuple | None:
        """Poll WinRT for the most recent toast notification. Returns (id, app_name, title, body, ts) or None."""
        if not self._is_allowed():
            return None

        listener, _ = self._get_winrt_listener()

        async def _fetch():
            from winrt.windows.ui.notifications import NotificationKinds
            return await listener.get_notifications_async(NotificationKinds.TOAST)

        notifs = asyncio.run(_fetch())

        # Filter blocked apps — guard display_info access per-notification;
        # some system/legacy notifications raise E_NOTIMPL on .display_info.display_name.
        filtered = [
            n for n in notifs
            if self._safe_app_name(n) not in self._blocked_apps
        ]

        if not filtered:
            return None

        # Select most recent by creation_time
        n = max(filtered, key=lambda x: x.creation_time)

        app_name = self._safe_app_name(n)

        # Extract title and body from toast binding.
        # 04-01 spike confirmed: use get_binding("ToastGeneric") string form.
        # Guard binding + text access — non-ToastGeneric notifications (legacy templates,
        # system alerts) may raise E_NOTIMPL on .visual or .get_binding().
        try:
            binding = n.notification.visual.get_binding("ToastGeneric")
            # Convert WinRT IVectorView to a plain Python list before indexing;
            # IVectorView does not support len() reliably in winrt 3.2.1.
            # Guard each element's .text against None (empty toast nodes send None).
            text_elements = list(binding.get_text_elements()) if binding else []
            title = (text_elements[0].text or "") if len(text_elements) > 0 else ""
            body = (text_elements[1].text or "") if len(text_elements) > 1 else ""
        except Exception:
            title = ""
            body = ""

        # Format timestamp — creation_time is Python datetime (UTC-aware) per 04-01 spike
        timestamp_str = n.creation_time.astimezone().strftime("%H:%M")

        return (n.id, app_name, title, body, timestamp_str)

    def _render_notification(self, app_name: str, title: str, body: str, timestamp: str) -> FrameData:
        """Render a notification card with app name, title, body, and timestamp."""
        W, H = self._width, self._height
        img = Image.new("RGBA", (W, H), self._bg_color)
        draw = ImageDraw.Draw(img)

        font_small = _load_font(self._font_name, 18)
        font_medium = _load_font(self._font_name, 28)

        # Word-wrap body to 3 lines max, fitting within W - 40px padding
        wrapped_lines = textwrap.wrap(body, width=50)
        if len(wrapped_lines) > 3:
            wrapped_lines = wrapped_lines[:3]
            # Truncate last line with ellipsis if we cut it
            last = wrapped_lines[2]
            if len(last) > 47:
                wrapped_lines[2] = last[:47] + "..."
            else:
                wrapped_lines[2] = last + "..."

        # Measure each layer
        app_bbox = draw.textbbox((0, 0), app_name, font=font_small)
        title_bbox = draw.textbbox((0, 0), title, font=font_medium)
        line_bboxes = [draw.textbbox((0, 0), line, font=font_small) for line in wrapped_lines]
        ts_bbox = draw.textbbox((0, 0), timestamp, font=font_small)

        def bbox_h(bb):
            return bb[3] - bb[1]

        def bbox_w(bb):
            return bb[2] - bb[0]

        gap = 10
        total_h = (bbox_h(app_bbox) + gap
                   + bbox_h(title_bbox) + gap
                   + sum(bbox_h(lb) for lb in line_bboxes) + gap * max(0, len(line_bboxes) - 1) + gap
                   + bbox_h(ts_bbox))
        start_y = (H - total_h) // 2

        # Draw app name (muted, small)
        ax = (W - bbox_w(app_bbox)) // 2 - app_bbox[0]
        ay = start_y - app_bbox[1]
        draw.text((ax, ay), app_name, font=font_small, fill=self._muted_color)
        y = start_y + bbox_h(app_bbox) + gap

        # Draw title (white, medium)
        tx = (W - bbox_w(title_bbox)) // 2 - title_bbox[0]
        ty = y - title_bbox[1]
        draw.text((tx, ty), title, font=font_medium, fill=self._title_color)
        y += bbox_h(title_bbox) + gap

        # Draw body lines (light, small)
        for i, (line, lb) in enumerate(zip(wrapped_lines, line_bboxes)):
            lx = (W - bbox_w(lb)) // 2 - lb[0]
            ly = y - lb[1]
            draw.text((lx, ly), line, font=font_small, fill=self._text_color)
            y += bbox_h(lb)
            if i < len(wrapped_lines) - 1:
                y += gap

        y += gap

        # Draw timestamp (muted, small)
        tsx = (W - bbox_w(ts_bbox)) // 2 - ts_bbox[0]
        tsy = y - ts_bbox[1]
        draw.text((tsx, tsy), timestamp, font=font_small, fill=self._muted_color)

        return FrameData(
            widget_id=self.widget_id,
            width=W,
            height=H,
            rgba_bytes=img.tobytes(),
        )

    def _render_idle(self) -> FrameData:
        """Render the idle bell icon state (no active notification)."""
        W, H = self._width, self._height
        img = Image.new("RGBA", (W, H), self._bg_color)
        draw = ImageDraw.Draw(img)

        cx, cy = W // 2, H // 2

        # Bell shape: body, rim, clapper — scaled to ~60px tall for 515px slot
        # Bell body (polygon approximating a bell)
        draw.polygon([
            (cx - 20, cy + 15),
            (cx - 30, cy - 5),
            (cx - 25, cy - 30),
            (cx + 25, cy - 30),
            (cx + 30, cy - 5),
            (cx + 20, cy + 15),
        ], fill=self._muted_color)

        # Bell rim (horizontal bar at base)
        draw.rectangle([(cx - 35, cy + 15), (cx + 35, cy + 20)], fill=self._muted_color)

        # Bell clapper (small circle below rim)
        draw.ellipse([(cx - 5, cy + 20), (cx + 5, cy + 30)], fill=self._muted_color)

        return FrameData(
            widget_id=self.widget_id,
            width=W,
            height=H,
            rgba_bytes=img.tobytes(),
        )

    def _render_permission_placeholder(self) -> FrameData:
        """Render a placeholder when notification permission is not ALLOWED."""
        W, H = self._width, self._height
        img = Image.new("RGBA", (W, H), self._bg_color)
        draw = ImageDraw.Draw(img)

        font_medium = _load_font(self._font_name, 28)
        font_small = _load_font(self._font_name, 18)

        line1 = "Notification access required"
        line2 = "Grant permission in Windows Settings"

        bb1 = draw.textbbox((0, 0), line1, font=font_medium)
        bb2 = draw.textbbox((0, 0), line2, font=font_small)

        h1 = bb1[3] - bb1[1]
        h2 = bb2[3] - bb2[1]
        w1 = bb1[2] - bb1[0]
        w2 = bb2[2] - bb2[0]
        gap = 16
        total_h = h1 + gap + h2
        start_y = (H - total_h) // 2

        x1 = (W - w1) // 2 - bb1[0]
        y1 = start_y - bb1[1]
        draw.text((x1, y1), line1, font=font_medium, fill=self._title_color)

        x2 = (W - w2) // 2 - bb2[0]
        y2 = start_y + h1 + gap - bb2[1]
        draw.text((x2, y2), line2, font=font_small, fill=self._muted_color)

        return FrameData(
            widget_id=self.widget_id,
            width=W,
            height=H,
            rgba_bytes=img.tobytes(),
        )

    def run(self) -> None:
        """Main loop — polls WinRT every 2 seconds, renders and pushes frames."""
        while True:
            try:
                self._run_once()
            except Exception as exc:  # noqa: BLE001
                # Log the error and render idle so the subprocess keeps running.
                # A crash here would be caught by the drain timer's is_alive() check
                # and the slot would turn dark red — instead, stay alive and idle.
                print(f"[NotificationWidget] error in poll cycle: {exc}", flush=True)
                try:
                    frame = self._render_idle()
                    self.out_queue.put(frame, block=False)
                except Exception:  # noqa: BLE001
                    pass
            time.sleep(2.0)  # Poll interval — 2 seconds per RESEARCH.md recommendation

    def _run_once(self) -> None:
        """One iteration of the polling loop. Separated to allow targeted exception handling."""
        # Poll config updates
        new_cfg = self.poll_config_update()
        if new_cfg:
            settings = new_cfg.get("settings", {})
            self._font_name = settings.get("font", self._font_name)
            self._auto_dismiss_seconds = settings.get(
                "auto_dismiss_seconds", self._auto_dismiss_seconds
            )
            self._blocked_apps = set(settings.get("blocked_apps", self._blocked_apps))

        # Check permission
        if not self._is_allowed():
            frame = self._render_permission_placeholder()
            try:
                self.out_queue.put(frame, block=False)
            except queue.Full:
                pass
            return

        # Fetch latest notification
        latest = self._fetch_latest()
        now = time.monotonic()

        if latest is not None:
            notif_id, app_name, title, body, ts = latest
            if notif_id != self._last_notif_id:
                # New notification — update display and reset timer
                self._current_notif = (app_name, title, body, ts)
                self._last_notif_id = notif_id
                self._display_since = now
            # else: same notification still active — no timer reset needed
        else:
            # No notifications (or all blocked) — if we were showing one that
            # disappeared from Action Center, clear immediately
            if self._current_notif is not None and self._last_notif_id is not None:
                self._current_notif = None
                self._last_notif_id = None

        # Auto-dismiss check
        if self._current_notif is not None:
            elapsed = now - self._display_since
            if elapsed > self._auto_dismiss_seconds:
                self._current_notif = None
                # Do NOT call remove_notification — per CONTEXT.md v1 decision
                # Action Center entry stays; bar just clears to idle

        # Render
        if self._current_notif is not None:
            frame = self._render_notification(*self._current_notif)
        else:
            frame = self._render_idle()

        try:
            self.out_queue.put(frame, block=False)
        except queue.Full:
            pass


def run_notification_widget(widget_id: str, config: dict, out_queue, in_queue) -> None:
    """Subprocess entry point. Called by ProcessManager."""
    widget = NotificationWidget(widget_id, config, out_queue, in_queue)
    widget.run()
