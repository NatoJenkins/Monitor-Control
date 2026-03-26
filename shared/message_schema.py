from dataclasses import dataclass, field
import time


@dataclass
class FrameData:
    widget_id: str
    width: int
    height: int
    rgba_bytes: bytes  # raw RGBA32, width*height*4 bytes
    timestamp: float = field(default_factory=time.time)
