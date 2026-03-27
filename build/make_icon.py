"""Generate build/icon.ico -- a multi-size ICO for MonitorControl.

Run: python build/make_icon.py
Output: build/icon.ico (16x16, 32x32, 48x48, 256x256)
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

OUTPUT = Path(__file__).parent / "icon.ico"
SIZES = [(16, 16), (32, 32), (48, 48), (256, 256)]


def make_base_image(size: int) -> Image.Image:
    """Create a simple 'MC' icon at the given size."""
    img = Image.new("RGBA", (size, size), (30, 30, 46, 255))  # dark background
    draw = ImageDraw.Draw(img)
    # Draw a rounded-feel rectangle border
    border = max(1, size // 16)
    draw.rectangle(
        [border, border, size - border - 1, size - border - 1],
        outline=(100, 149, 237, 255),  # cornflower blue
        width=border,
    )
    # Draw "MC" text centered
    font_size = size // 3
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except (OSError, IOError):
        font = ImageFont.load_default()
    bbox = draw.textbbox((0, 0), "MC", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = (size - tw) // 2
    y = (size - th) // 2
    draw.text((x, y), "MC", fill=(100, 149, 237, 255), font=font)
    return img


if __name__ == "__main__":
    # Create a 256x256 base image; Pillow resizes it to all requested sizes when
    # saving as ICO. Using the sizes= parameter is the correct approach for
    # multi-size ICO generation with Pillow's IcoImagePlugin.
    base = make_base_image(256)
    base.save(str(OUTPUT), format="ICO", sizes=SIZES)
    print(f"Created {OUTPUT} with sizes {SIZES}")
