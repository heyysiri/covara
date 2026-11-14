"""ReportLab styling shared by every synthetic document. Output bytes are deterministic (stable file hashes)."""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Heading1"], fontSize=15, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=_ss["BodyText"], fontSize=10, leading=14, spaceAfter=5)
SMALL = ParagraphStyle("SMALL", parent=_ss["BodyText"], fontSize=8.5, leading=11, textColor=colors.grey)
CELL = ParagraphStyle("CELL", parent=_ss["BodyText"], fontSize=9.5, leading=12)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")
RIGHT = ParagraphStyle("RIGHT", parent=CELL, alignment=2)
RIGHTB = ParagraphStyle("RIGHTB", parent=RIGHT, fontName="Helvetica-Bold")

BANNER = "SYNTHETIC DEMO DOCUMENT - FICTIONAL - NOT A REAL POLICY OR BILL"


def P(text: str, style=BODY) -> Paragraph:
    return Paragraph(text, style)


def kv_table(rows: list[tuple[str, str]]) -> Table:
    t = Table([[P(k, CELLB), P(v, CELL)] for k, v in rows], colWidths=[55 * mm, 115 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                           ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def grid(rows: list[list], widths: list[float]) -> Table:
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
    return t


def build_pdf(path: Path, doc_label: str, story: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 287 * mm, BANNER)
        canvas.drawString(18 * mm, 10 * mm, f"{doc_label}  |  Page {doc.page}")
        canvas.restoreState()

    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=20 * mm, bottomMargin=18 * mm,
                      title=doc_label, author="Covara synthetic demo data", invariant=1).build(
        story, onFirstPage=decorate, onLaterPages=decorate)
