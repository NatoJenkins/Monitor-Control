from dataclasses import dataclass, field
from typing import Any
import time


@dataclass
class FrameData:
    widget_id: str
    width: int
    height: int
    rgba_bytes: bytes  # raw RGBA32, width*height*4 bytes
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConfigUpdateMessage:
    """Sent host -> widget via in_queue to deliver updated settings."""
    widget_id: str
    config: dict[str, Any]
