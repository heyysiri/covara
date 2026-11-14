"""Generate the Hindi demo claim (SYNTHETIC): two scan-style Hindi documents + four English ones.

    python sample_documents/tools/generate_hindi_demo.py

Output:
  sample_documents/hindi_demo/hindi_final_bill_scan.jpg      Hindi final bill, image only (no text layer)
  sample_documents/hindi_demo/hindi_prescription_scan.jpg    Hindi/English prescription, image only
  sample_documents/hindi_demo_upload.zip                     those two + claim B's English policy,
                                                             itemised bill, discharge summary, receipt

The two images are printed-style scans (rotation, paper tint, grain). They are NOT real handwriting.
Same patient and policy as claim B, so the planted problems are the same and checkable:
  * Hindi bill total 85,000 vs claimed amount 95,000 (enter 95000 on the claim form)  -> V4, blocking
  * the receipt writes the patient as "Ravi K Sharma"                                  -> V2, to review
  * prescription RX-7781 (referenced by the discharge summary) IS included             -> no V7 finding
"""

from __future__ import annotations

import random
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "hindi_demo"
FONT_DIR = Path("/usr/share/fonts/truetype/noto")
REG = FONT_DIR / "NotoSansDevanagari-Regular.ttf"
BOLD = FONT_DIR / "NotoSansDevanagari-Bold.ttf"
W, H = 1240, 1754  # A4 at 150 dpi
INK = (28, 28, 34)


LAT_REG = FONT_DIR / "NotoSans-Regular.ttf"
LAT_BOLD = FONT_DIR / "NotoSans-Bold.ttf"


class Face:
    def __init__(self, size: int, bold: bool = False):
        self.size, self.bold = size, bold


def font(size: int, bold: bool = False) -> Face:
    return Face(size, bold)


def _ft(path: Path, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(path), size, layout_engine=ImageFont.Layout.RAQM)


class Pen:
    """ImageDraw wrapper that draws each script with a font that has its glyphs (Devanagari vs Latin),
    on a shared baseline, so mixed Hindi/English lines render without missing-glyph boxes."""

    def __init__(self, img: Image.Image):
        self.d = ImageDraw.Draw(img)

    def __getattr__(self, name):
        return getattr(self.d, name)

    def text(self, xy, text, font: Face, fill):
        x, y = xy
        base = y + font.size
        dev = _ft(BOLD if font.bold else REG, font.size)
        lat = _ft(LAT_BOLD if font.bold else LAT_REG, font.size)
        runs: list[tuple[str, str]] = []
        for ch in text:
            kind = "dev" if "\u0900" <= ch <= "\u097f" else ("same" if ch == " " else "lat")
            if kind == "same":
                kind = runs[-1][0] if runs else "lat"
            if runs and runs[-1][0] == kind:
                runs[-1] = (kind, runs[-1][1] + ch)
            else:
                runs.append((kind, ch))
        for kind, run in runs:
            f = dev if kind == "dev" else lat
            self.d.text((x, base), run, font=f, fill=fill, anchor="ls")
            x += f.getlength(run)


def page() -> tuple[Image.Image, Pen]:
    img = Image.new("RGB", (W, H), (252, 251, 246))
    return img, Pen(img)


def scanify(img: Image.Image, seed: int) -> Image.Image:
    """Make it look photocopied: slight rotation, paper tint, grain, a touch of blur."""
    rnd = random.Random(seed)
    img = img.rotate(rnd.uniform(-1.4, 1.4), resample=Image.BICUBIC, expand=False, fillcolor=(236, 234, 226))
    noise = Image.effect_noise((W, H), 14).convert("RGB")
    img = Image.blend(img, noise, 0.06).filter(ImageFilter.GaussianBlur(0.6))
    return img


def header(d: Pen, title: str) -> int:
    d.text((70, 60), "SYNTHETIC DEMO DOCUMENT - FICTIONAL / काल्पनिक दस्तावेज़", font=font(22), fill=(150, 40, 40))
    d.text((70, 110), "डेमो सिटी केयर हॉस्पिटल", font=font(54, True), fill=INK)
    d.text((70, 185), "Demo City Care Hospital, Pune", font=font(28), fill=INK)
    d.line((70, 235, W - 70, 235), fill=INK, width=3)
    d.text((70, 262), title, font=font(42, True), fill=INK)
    return 345


def rows(d: Pen, y: int, items: list[tuple[str, str]], gap: int = 62) -> int:
    for label, value in items:
        d.text((70, y), label, font=font(32), fill=(70, 70, 80))
        d.text((520, y), value, font=font(34, True), fill=INK)
        y += gap
    return y


def bill() -> Image.Image:
    img, d = page()
    y = header(d, "अंतिम बिल (Final Bill)")
    y = rows(d, y, [
        ("बिल संख्या:", "INV-2026-08-10457"),
        ("बिल दिनांक:", "15-08-2026"),
        ("मरीज़ का नाम:", "श्री रवि कुमार शर्मा"),
        ("आयु:", "42 वर्ष"),
        ("पॉलिसी संख्या:", "SSH-2026-004567"),
        ("सदस्य आईडी:", "M-889201"),
        ("भर्ती की तिथि:", "12-08-2026"),
        ("छुट्टी की तिथि:", "15-08-2026"),
        ("निदान:", "तीव्र एपेंडिसाइटिस"),
    ])
    y += 30
    d.rectangle((70, y, W - 70, y + 150), outline=INK, width=4)
    d.text((100, y + 22), "कुल देय राशि", font=font(40, True), fill=INK)
    d.text((100, y + 84), "(Total Payable)", font=font(26), fill=(70, 70, 80))
    d.text((640, y + 38), "₹ 85,000.00", font=font(62, True), fill=INK)
    y += 210
    d.text((70, y), "विस्तृत मदवार बिल अलग से संलग्न है।", font=font(30), fill=(70, 70, 80))
    d.text((70, H - 170), "अधिकृत हस्ताक्षर: ____________________", font=font(30), fill=INK)
    d.text((70, H - 110), "यह कंप्यूटर जनित बिल है।", font=font(24), fill=(90, 90, 100))
    return scanify(img, 1)


def prescription() -> Image.Image:
    img, d = page()
    y = header(d, "नुस्खा (Prescription)")
    y = rows(d, y, [
        ("प्रिस्क्रिप्शन संख्या:", "RX-7781"),
        ("दिनांक:", "15-08-2026"),
        ("मरीज़ का नाम:", "श्री रवि कुमार शर्मा"),
        ("आयु:", "42 वर्ष"),
        ("निदान:", "तीव्र एपेंडिसाइटिस (सर्जरी के बाद)"),
    ], gap=60)
    y += 20
    d.text((70, y), "Rx", font=font(64, True), fill=INK)
    y += 100
    meds = [
        "1. Tab. Paracetamol 650 mg - दिन में 3 बार - 3 दिन",
        "2. Cap. Pantoprazole 40 mg - सुबह खाली पेट - 5 दिन",
        "3. Tab. Amoxicillin-Clavulanate 625 mg - दिन में 2 बार - 5 दिन",
    ]
    for m in meds:
        d.text((90, y), m, font=font(34), fill=INK)
        y += 78
    y += 30
    d.text((70, y), "सलाह: 7 दिन बाद दोबारा दिखाएँ।", font=font(34), fill=INK)
    d.text((70, H - 200), "डॉ. आनंद देशपांडे (काल्पनिक)", font=font(34, True), fill=INK)
    d.text((70, H - 150), "हस्ताक्षर / मुहर: ____________________", font=font(28), fill=(70, 70, 80))
    return scanify(img, 2)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    files = {"hindi_final_bill_scan.jpg": bill(), "hindi_prescription_scan.jpg": prescription()}
    for name, img in files.items():
        img.save(OUT / name, "JPEG", quality=82, dpi=(150, 150))
    english = [
        ROOT / "policy" / "claim_b_policy.pdf",
        ROOT / "medical" / "claim_b_itemised_bill.pdf",
        ROOT / "medical" / "claim_b_discharge_summary.pdf",
        ROOT / "medical" / "claim_b_payment_receipt.pdf",
    ]
    zip_path = ROOT / "hindi_demo_upload.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for name in files:
            z.write(OUT / name, name)
        for p in english:
            z.write(p, p.name)
    print("wrote", [str(OUT / n) for n in files], "and", zip_path, f"({zip_path.stat().st_size // 1024} KB)")


if __name__ == "__main__":
    main()
