"""Make synthetic documents look like phone photos of paper: image-only pages, slightly rotated, soft, off-white.

Deterministic (seeded) so regenerating gives the same bytes on the same machine. The handwritten prescription is
drawn with a handwriting-style system font; if that font is missing a plain font is used and the result is less
realistic but still image-only.
"""

from __future__ import annotations

import io
import random
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .scenario import Scenario, fmt_date

_HANDWRITING_FONTS = ["/System/Library/Fonts/Supplemental/Bradley Hand Bold.ttf", "/System/Library/Fonts/Noteworthy.ttc",
                      "/System/Library/Fonts/Supplemental/SnellRoundhand.ttc"]
PAPER = (246, 243, 236)


def degrade(img: Image.Image, rnd: random.Random, angle: float = 0.9) -> Image.Image:
    """Slight rotation, soft focus, paper tint and uneven light, like a quick photo."""
    img = img.convert("RGB").rotate(rnd.uniform(-angle, angle), resample=Image.BICUBIC, fillcolor=PAPER)
    img = img.filter(ImageFilter.GaussianBlur(0.7))
    img = ImageEnhance.Contrast(img).enhance(0.9)
    tint = Image.new("RGB", img.size, PAPER)
    img = Image.blend(img, Image.composite(img, tint, Image.new("L", img.size, 255)), 1.0)
    w, h = img.size
    shade = Image.linear_gradient("L").resize((w, h)).point(lambda v: int(255 - v * 0.10))  # darker toward the bottom
    return Image.composite(img, Image.new("RGB", img.size, (205, 200, 190)), shade)


def scan_pdf(path: Path, seed: int, dpi: int = 120) -> None:
    """Replace a text PDF by an image-only PDF of the same pages (no text layer, so extraction must read the image)."""
    rnd = random.Random(seed)
    out = pymupdf.open()
    with pymupdf.open(path) as src:
        for page in src:
            pix = page.get_pixmap(dpi=dpi)
            img = degrade(Image.frombytes("RGB", (pix.width, pix.height), pix.samples), rnd)
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=60)
            new = out.new_page(width=page.rect.width, height=page.rect.height)
            new.insert_image(page.rect, stream=buf.getvalue())
    tmp = path.with_suffix(".tmp.pdf")
    out.save(tmp, garbage=3, deflate=True)
    out.close()
    tmp.replace(path)


def _font(size: int) -> ImageFont.ImageFont:
    for f in _HANDWRITING_FONTS:
        if Path(f).exists():
            return ImageFont.truetype(f, size)
    return ImageFont.load_default(size)


def handwritten_prescription(s: Scenario, path: Path, seed: int) -> None:
    """A photo of a handwritten prescription pad page (JPEG)."""
    rnd = random.Random(seed)
    img = Image.new("RGB", (1000, 1300), PAPER)
    d = ImageDraw.Draw(img)
    big, mid = _font(44), _font(33)
    ink = (28, 38, 92)
    lines = [(s.hospital, big), (f"Rx No. {s.rx_no}", mid), (f"Patient: {s.patient}   {s.age}/{s.sex[0]}", mid),
             (f"Date: {fmt_date(s.discharge)}", mid), (f"Dx: {s.diagnosis}", mid), ("", mid), ("Rx", big)]
    lines += [(f"{i}. {item}", mid) for i, item in enumerate(s.rx_items, 1)]
    lines += [("", mid), (s.doctor, big), (f"Reg. {s.doctor_reg}", mid)]
    y = 90
    for text, font in lines:
        if text:
            d.text((70 + rnd.randint(-6, 6), y + rnd.randint(-5, 5)), text, fill=ink, font=font)
        y += 92
    img = degrade(img, rnd, angle=1.4)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "JPEG", quality=70)
