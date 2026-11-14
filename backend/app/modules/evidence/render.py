"""Render a document page as a PNG with the cited text highlighted (the "show me the evidence" view).

The highlight is found by searching the page's text layer for the quote, the same text the extraction
cited, so what the user sees is what the finding is based on. If the quote cannot be located (scanned
page, reworded quote) we fall back to the stored bounding box, and if there is none we return the plain
page. The caller is told how many highlights were found so the UI can be honest about it.
Highlights are drawn on an in-memory copy; the stored original is never modified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import pymupdf

_YELLOW = (1.0, 0.85, 0.0)
_WINDOW = 6  # words per fallback search window
_MIN_WINDOW = 4  # a shorter leftover is merged into the previous window (tiny windows match unrelated words)
_MIN_SHARE = 0.6  # share of windows that must be found before we trust a piecewise match


class PageOutOfRange(Exception):
    def __init__(self, page: int, count: int) -> None:
        super().__init__(f"page {page} is out of range (document has {count})")
        self.page, self.count = page, count


@dataclass
class Rendered:
    png: bytes
    highlights_found: int  # quotes located in the text layer
    bbox_highlights: int  # boxes drawn from stored coordinates because a quote was not found
    page_count: int
    focused: bool = False  # the image is a close-up around the highlight, not the whole page


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def locate(page: pymupdf.Page, quote: str) -> list[pymupdf.Rect]:
    """Rectangles covering `quote` on the page, or [] if it is not really there.

    Tries the whole quote first. If the text layer breaks it differently (layout, reworded by a model),
    match it in word windows, but only trust the result when most windows are found: highlighting the
    wrong text would be worse than highlighting nothing.
    """
    quote = _norm(quote)
    if not quote:
        return []
    rects = page.search_for(quote)
    if rects:
        return list(rects)
    words = quote.split(" ")
    if len(words) < 2 * _MIN_WINDOW:
        return []
    chunks = [words[i : i + _WINDOW] for i in range(0, len(words), _WINDOW)]
    if len(chunks) > 1 and len(chunks[-1]) < _MIN_WINDOW:
        chunks[-2] += chunks.pop()
    hits = [page.search_for(" ".join(c)) for c in chunks]
    if sum(1 for h in hits if h) / len(chunks) < _MIN_SHARE:
        return []
    return [r for h in hits for r in h]


def render_page(path: Path, page_number: int, quotes: list[str], bboxes: list[list[float]], dpi: int = 110, focus: bool = False) -> Rendered:
    with pymupdf.open(path) as src:  # PDFs and single images both open as documents
        # drawing needs a PDF; a scanned image is wrapped into a one-page PDF in memory
        doc = src if src.is_pdf else pymupdf.open("pdf", src.convert_to_pdf())
        if not 1 <= page_number <= doc.page_count:
            raise PageOutOfRange(page_number, doc.page_count)
        page = doc[page_number - 1]
        located = 0
        marked: list[pymupdf.Rect] = []
        for q in quotes:
            rects = locate(page, q)
            if rects:
                located += 1
                marked += rects
                annot = page.add_highlight_annot(rects)
                annot.set_colors(stroke=_YELLOW)
                annot.update()
        drawn = 0
        if located < len(quotes) or not quotes:
            w, h = page.rect.width, page.rect.height
            for x0, y0, x1, y1 in bboxes:
                box = pymupdf.Rect(x0 * w, y0 * h, x1 * w, y1 * h)
                page.draw_rect(box, color=_YELLOW, width=2.5)
                marked.append(box)
                drawn += 1
        if focus and marked:
            # Close-up for small screens: the highlight with some context, at least ~300pt wide so the text is readable.
            union = pymupdf.Rect(marked[0])
            for r in marked[1:]:
                union |= r
            cx = (union.x0 + union.x1) / 2
            half_w = max((union.width / 2) + 24, 150)
            clip = pymupdf.Rect(cx - half_w, union.y0 - 70, cx + half_w, union.y1 + 70) & page.rect
            pix = page.get_pixmap(dpi=int(dpi * 1.6), annots=True, clip=clip)
            return Rendered(pix.tobytes("png"), located, drawn, doc.page_count, focused=True)
        pix = page.get_pixmap(dpi=dpi, annots=True)
        return Rendered(pix.tobytes("png"), located, drawn, doc.page_count)
