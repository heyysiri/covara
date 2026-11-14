"""Ingest: page text with page numbers, text-layer detection, quote location.

Pure code, no network. Page text is the ground truth used to verify every quote (I1/I2).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

LOW_TEXT_CHARS = 40  # fewer characters than this on every page => treat as scanned


@dataclass
class Page:
    number: int  # 1-based
    text: str
    width: float = 0
    height: float = 0


@dataclass
class IngestedDoc:
    document_id: str
    filename: str
    path: Path
    content_type: str
    sha256: str
    pages: list[Page] = field(default_factory=list)
    ocr_source: str | None = None  # "sarvam" when the page text came from OCR rather than a PDF text layer
    ocr_blocks: dict[int, list[tuple[str, list[float]]]] = field(default_factory=dict)  # page -> (text, bbox)

    @property
    def has_text_layer(self) -> bool:
        return any(len(p.text.strip()) >= LOW_TEXT_CHARS for p in self.pages)

    @property
    def full_text(self) -> str:
        return "\n".join(f"[page {p.number}]\n{p.text}" for p in self.pages)


def ingest(document_id: str, filename: str, path: Path, content_type: str, sha256: str) -> IngestedDoc:
    doc = IngestedDoc(document_id, filename, path, content_type, sha256)
    if content_type == "application/pdf":
        with pymupdf.open(path) as pdf:
            for i, page in enumerate(pdf):
                doc.pages.append(Page(i + 1, page.get_text("text"), page.rect.width, page.rect.height))
    else:  # images: one page, no text layer (needs a vision model)
        doc.pages.append(Page(1, ""))
    return doc


_WS = re.compile(r"\s+")


def norm_ws(s: str) -> str:
    return _WS.sub(" ", s).strip().lower()


def squash(s: str) -> str:
    """Lower-case letters/digits only: compares text ignoring spaces, punctuation and line breaks."""
    return re.sub(r"[\W_]+", "", s.lower())


def locate_quote(doc: IngestedDoc, quote: str | None, hint_page: int | None = None) -> int | None:
    """Return the page number where `quote` appears verbatim (whitespace/case-insensitive)."""
    if not quote or not quote.strip():
        return None
    q = norm_ws(quote)
    sq = squash(quote)
    order = sorted(doc.pages, key=lambda p: (p.number != hint_page, p.number))
    for p in order:
        if q in norm_ws(p.text):
            return p.number
    if len(sq) >= 6:  # same words, different punctuation / line breaks ("Name: X" vs "Name\nX")
        for p in order:
            if sq in squash(p.text):
                return p.number
    return None


def apply_ocr(doc: IngestedDoc, pages) -> None:
    """Replace page text with OCR output (list of sarvam.OcrPage) and remember block boxes for highlighting."""
    doc.pages = [Page(p.number, p.text) for p in pages]
    doc.ocr_source = "sarvam"
    doc.ocr_blocks = {p.number: [(b.text, b.bbox) for b in p.blocks] for p in pages}


def find_bbox(doc: IngestedDoc, page_number: int, quote: str) -> list[float] | None:
    """Normalised bbox of the first occurrence of `quote` on the page (PDF text layer, or OCR block)."""
    if doc.ocr_source and quote:
        q = norm_ws(quote)
        for text, bbox in doc.ocr_blocks.get(page_number, []):
            t = norm_ws(text)
            if t and (q in t or t in q):
                return bbox  # approximate: OCR block / table-row region
        return None
    if doc.content_type != "application/pdf" or not quote:
        return None
    try:
        with pymupdf.open(doc.path) as pdf:
            page = pdf[page_number - 1]
            hits = page.search_for(quote.strip()[:200])
            if not hits:
                return None
            r = hits[0]
            for h in hits[1:]:
                if abs(h.y0 - r.y1) < 30:  # merge multi-line hit
                    r |= h
            w, h = page.rect.width, page.rect.height
            return [round(r.x0 / w, 4), round(r.y0 / h, 4), round(r.x1 / w, 4), round(r.y1 / h, 4)]
    except Exception:
        return None
