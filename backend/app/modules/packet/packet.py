"""Claim Packet PDF: cover + structured summary, document index, evidence annex, then the original documents.

One merged PDF the user can hand to the insurer. Wording follows decision D5:
  - while blocking items are open it is stamped INCOMPLETE on every page,
  - when none are open it says "Prepared for submission".
It never says "approved" and always carries the disclaimer.
"""

from __future__ import annotations

from pathlib import Path

import pymupdf
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, Spacer

from app.schemas.claim import ClaimOut
from app.schemas.results import AnalysisResults
from app.services import claim_store

from . import data
from .pdf_common import BANNER, BODY, CONTENT_W, GREEN, H1, H2, H3, RED, SMALL, P, build, esc, table
from .report import evidence_text

_WATERMARK = (0.8, 0.1, 0.1)


def _page_counts(claim: ClaimOut, docs) -> list[tuple[object, str, Path, int]]:
    out = []
    for d, doc_type, _ in docs:
        path = claim_store.document_path(claim.id, d)
        if not path.exists():
            continue
        with pymupdf.open(path) as src:
            out.append((d, doc_type, path, max(src.page_count, 1)))
    return out


def _front_matter(claim: ClaimOut, results: AnalysisResults, docs, front_pages: int) -> bytes:
    incomplete = data.is_incomplete(results)
    status = results.packet_status or ("INCOMPLETE" if incomplete else "Prepared for submission")
    color = RED if incomplete else GREEN
    open_f = data.open_findings(results)
    blocking = data.blocking_findings(results)
    clauses = {c.id: c for c in results.clauses}
    s: list = [P("Claim Packet", H1), P(f"Covara claim {claim.id[:8]} - {claim.claim_type.value} claim - prepared {claim.created_at:%d %b %Y}", SMALL)]
    s.append(Paragraph(f'<font color="{color.hexval()}">Status: {esc(status)}</font>', BANNER))
    s.append(P("Draft: some items still need attention before this packet is complete." if incomplete
               else "All blocking checks are clear. Items listed below are for your review; the insurer makes the final decision.", BODY))

    s.append(P("Claim summary", H2))
    s.append(table([[l, v] for l, v, _ in data.summary_rows(claim, results)], [62 * mm, CONTENT_W - 62 * mm], header=False))
    s.append(P(f"Preparation check: {len(blocking)} blocking item(s), {len(open_f) - len(blocking)} item(s) to review.", SMALL))

    s.append(P("Document index", H2))
    rows = [["#", "Document", "Type", "Pages in this packet"]]
    page = front_pages + 1
    for i, (d, doc_type, _path, n) in enumerate(docs, 1):
        rows.append([str(i), d.original_filename, data.DOC_LABEL.get(doc_type, doc_type), f"{page}-{page + n - 1}" if n > 1 else str(page)])
        page += n
    s.append(table(rows, [10 * mm, 82 * mm, 40 * mm, CONTENT_W - 132 * mm]))

    s.append(P("Evidence references", H2))
    s.append(P("Where each point flagged by the preparation check can be found in the documents.", SMALL))
    if not open_f:
        s.append(P("Nothing is flagged."))
    for f in open_f:
        s.append(P(f.title, H3))
        for e in f.evidence:
            s.append(P(evidence_text(e), SMALL))
    linked = {l.clause_id for f in open_f for l in f.clause_links}
    shown = [c for c in results.clauses if c.id in linked]
    if shown:
        s.append(P("Policy clauses referenced", H2))
        for c in shown:
            s.append(P(f"Clause {c.clause_ref} - {c.title} ({c.filename}, page {c.page_number}): {c.text[:400]}", SMALL))
    s.append(Spacer(1, 8))
    s.append(P(results.disclaimer, SMALL))
    s.append(P("This packet was assembled by an AI-assisted preparation tool from the documents provided. It is not an insurer decision and does not "
               "guarantee that a claim will be accepted.", SMALL))
    return build(s, "Covara Claim Packet", None)  # header/footer/watermark are stamped on every page by _stamp()


def _stamp(out: pymupdf.Document, status: str, incomplete: bool, claim_id: str) -> None:
    total = out.page_count
    for i, page in enumerate(out, 1):
        w, h = page.rect.width, page.rect.height
        page.insert_text((w / 2 - 70, h - 12), f"Covara claim packet {claim_id[:8]}  |  page {i} of {total}  |  AI-assisted preparation, not an insurer decision",
                         fontsize=6.5, color=(0.45, 0.45, 0.45), fontname="helv")
        page.insert_text((18, 20), status, fontsize=8, color=_WATERMARK if incomplete else (0.1, 0.43, 0.24), fontname="hebo")
        if incomplete:
            fs = min(w, h) / 9
            origin = pymupdf.Point(w * 0.12, h * 0.62)
            page.insert_text(origin, "INCOMPLETE", fontsize=fs * 1.6, color=_WATERMARK, fill_opacity=0.13, fontname="hebo",
                             morph=(origin, pymupdf.Matrix(45)))


def build_packet(claim: ClaimOut, results: AnalysisResults) -> bytes:
    docs = _page_counts(claim, data.ordered_documents(claim, results))
    incomplete = data.is_incomplete(results)
    status = results.packet_status or ("INCOMPLETE" if incomplete else "Prepared for submission")

    front_pages = 2  # the index shows page numbers that depend on how long the front matter is, so settle it
    for _ in range(4):
        front = _front_matter(claim, results, docs, front_pages)
        with pymupdf.open("pdf", front) as f:
            actual = f.page_count
        if actual == front_pages:
            break
        front_pages = actual

    out = pymupdf.open()
    out.insert_pdf(pymupdf.open("pdf", front))
    toc = [[1, "Cover, summary and index", 1]]
    for d, doc_type, path, _n in docs:
        start = out.page_count + 1
        with pymupdf.open(path) as src:
            body = src if src.is_pdf else pymupdf.open("pdf", src.convert_to_pdf())  # scanned images become pages
            out.insert_pdf(body)
        toc.append([1, f"{data.DOC_LABEL.get(doc_type, doc_type)} - {d.original_filename}", start])
    out.set_toc(toc)
    _stamp(out, status, incomplete, claim.id)
    out.set_metadata({"title": f"Covara claim packet {claim.id[:8]}", "author": "Covara", "subject": status})
    pdf = out.tobytes(garbage=3, deflate=True)
    out.close()
    return pdf
