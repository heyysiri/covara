"""Shared ReportLab helpers: styles, text safety and small table builders."""

from __future__ import annotations

from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Heading1"], fontSize=17, spaceAfter=4)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], fontSize=12.5, spaceBefore=12, spaceAfter=5, keepWithNext=1)
H3 = ParagraphStyle("H3", parent=_ss["Heading3"], fontSize=10.5, spaceBefore=6, spaceAfter=2, keepWithNext=1)
BODY = ParagraphStyle("BODY", parent=_ss["BodyText"], fontSize=9.5, leading=13, spaceAfter=4)
SMALL = ParagraphStyle("SMALL", parent=BODY, fontSize=8, leading=10.5, textColor=colors.HexColor("#555555"))
CELL = ParagraphStyle("CELL", parent=BODY, fontSize=8.5, leading=11, spaceAfter=0)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")
BANNER = ParagraphStyle("BANNER", parent=BODY, fontSize=11, leading=15, fontName="Helvetica-Bold")
MUTED = colors.HexColor("#777777")
RED = colors.HexColor("#b3261e")
GREEN = colors.HexColor("#1b6e3c")
AMBER = colors.HexColor("#8a5a00")

PAGE_W, PAGE_H = A4
CONTENT_W = PAGE_W - 36 * mm


def safe(text: object) -> str:
    """Built-in PDF fonts are Latin-1 only: map the rupee sign and anything else unsupported."""
    s = str(text).replace("₹", "Rs. ").replace("–", "-").replace("—", "-")
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"').replace("…", "...")
    return s.encode("latin-1", "replace").decode("latin-1")


def esc(text: object) -> str:
    return escape(safe(text))


def P(text: object, style: ParagraphStyle = BODY, raw: bool = False) -> Paragraph:
    return Paragraph(text if raw else esc(text), style)  # type: ignore[arg-type]


def table(rows: list[list[object]], widths: list[float], header: bool = True, zebra: bool = False) -> Table:
    data = []
    for i, r in enumerate(rows):
        style = CELLB if header and i == 0 else CELL
        data.append([c if not isinstance(c, str) else P(c, style) for c in r])
    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4), ("RIGHTPADDING", (0, 0), (-1, -1), 4)]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke))
    if zebra:
        cmds += [("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")])]
    t.setStyle(TableStyle(cmds))
    return t


def build(story: list, title: str, footer: str | None, banner: str | None = None, banner_color=RED) -> bytes:
    import io

    buf = io.BytesIO()

    def decorate(canvas, doc):
        if footer is None:  # caller stamps its own header/footer afterwards
            return
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 10 * mm, safe(f"{footer}  |  Page {doc.page}"))
        canvas.drawRightString(PAGE_W - 18 * mm, 10 * mm, "AI-assisted preparation - not an insurer decision")
        if banner:
            canvas.setFillColor(banner_color)
            canvas.setFont("Helvetica-Bold", 8)
            canvas.drawString(18 * mm, PAGE_H - 12 * mm, safe(banner))
        canvas.restoreState()

    SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm,
                      bottomMargin=18 * mm, title=title, author="Covara").build(
        story, onFirstPage=decorate, onLaterPages=decorate)
    return buf.getvalue()
