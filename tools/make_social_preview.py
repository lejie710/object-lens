"""Make the 1200 x 630 link preview image from two recorded real-model captures.

Social sites show this image when the showcase link is shared. It needs Pillow
and the Windows Segoe UI fonts; Pillow is not a project dependency, so install
it separately (pip install pillow) only to regenerate the image. The captures
are checked against the hashes recorded in docs/evidence/sample-captures.json.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / "docs" / "screenshots" / "app"
SOURCES = {
    "sample-chelsea.png": "0232a8be9b62c61249b4544c5d40f17adf47dee76582e0fb1461a860172bf6ee",
    "sample-camera.png": "2d88ad8c4c81f9feaa784324b69273d5e1ff48afba58f42af46bd64fe68db696",
}
FONTS = Path(r"C:\Windows\Fonts")
W, H = 1200, 630
BG, INK, MUTED, ACCENT, EDGE = (245, 246, 248), (24, 28, 36), (88, 96, 110), (40, 91, 212), (214, 219, 228)


def font(name, size):
    return ImageFont.truetype(str(FONTS / name), size)


def capture(name, width, height):
    path = CAPTURES / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != SOURCES[name]:
        raise ValueError(f"{name} does not match its recorded capture hash")
    image = Image.open(path).convert("RGB")
    image = image.resize((width, round(image.height * width / image.width)), Image.LANCZOS)
    return image.crop((0, 0, width, height))


def place(card, image, x, y, radius=12):
    shadow = Image.new("RGBA", (image.width + 60, image.height + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((30, 34, image.width + 30, image.height + 34), radius,
                                             fill=(20, 30, 60, 60))
    card.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(14)), (x - 30, y - 30))
    mask = Image.new("L", image.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, image.width - 1, image.height - 1), radius, fill=255)
    card.paste(image, (x, y), mask)
    ImageDraw.Draw(card).rounded_rectangle((x, y, x + image.width - 1, y + image.height - 1), radius,
                                           outline=EDGE, width=1)


def make(output):
    card = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(card)
    # The app's corner-bracket mark, then its name.
    x, y = 56, 50
    for corner in [((10, 0), (0, 0), (0, 10)), ((24, 0), (34, 0), (34, 10)),
                   ((34, 24), (34, 34), (24, 34)), ((10, 34), (0, 34), (0, 24))]:
        draw.line([(x + px, y + py) for px, py in corner], fill=ACCENT, width=4)
    draw.text((x + 50, y - 4), "Object Lens", font=font("segoeuib.ttf", 30), fill=INK)
    draw.text((56, 150), "Object detection", font=font("segoeuib.ttf", 54), fill=INK)
    draw.text((56, 214), "in your browser", font=font("segoeuib.ttf", 54), fill=INK)
    draw.text((58, 300), "Try it on your own photo.", font=font("segoeui.ttf", 26), fill=MUTED)
    # Two captures overlap; the lower one runs off the bottom edge.
    place(card, capture("sample-chelsea.png", 560, 334), 590, 56)
    place(card, capture("sample-camera.png", 560, 352), 626, 300)
    card.convert("RGB").save(output, optimize=True)
    return hashlib.sha256(Path(output).read_bytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "dist" / "social-preview.png")
    args = parser.parse_args()
    print(args.output, make(args.output))
