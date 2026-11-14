"""Readiness report in another language (Hindi).

ReportLab's built-in fonts cannot draw Devanagari, so this builds the same report as HTML and renders it with PyMuPDF using a
bundled open-licence font (Noto Sans Devanagari), which shapes conjuncts correctly. Explanatory text is translated; document
quotes, file names, numbers, dates and IDs are never translated. If translation is unavailable the report is refused rather than
shipped half-translated.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from html import escape
from pathlib import Path

import io

import pymupdf

from app.core import sarvam
from app.schemas.claim import ClaimOut
from app.schemas.results import AnalysisResults

from . import data
from .report import OWNER, evidence_text

FONTS = Path(__file__).resolve().parents[2] / "assets" / "fonts"
CSS = """
@font-face{font-family:nd;src:url(NotoSansDevanagari-Regular.ttf);}
@font-face{font-family:nd;font-weight:bold;src:url(NotoSansDevanagari-Bold.ttf);}
body{font-family:nd,sans-serif;font-size:9.5pt;color:#111;line-height:1.35}
h1{font-size:18pt;margin:0 0 4pt} h2{font-size:12.5pt;margin:12pt 0 4pt;color:#002e6e}
h3{font-size:10.5pt;margin:7pt 0 1pt} p{margin:2pt 0 4pt} .s{font-size:8pt;color:#555}
table{width:100%;border-collapse:collapse} td,th{border:0.5pt solid #bbb;padding:3pt 4pt;text-align:left;vertical-align:top;font-size:8.5pt}
th{background:#f2f2f2}
"""


class TranslationUnavailable(Exception):
    pass


def build_report_translated(claim: ClaimOut, results: AnalysisResults, lang: str) -> bytes:
    if not sarvam.available():
        raise TranslationUnavailable("Translation is not configured.")
    texts: list[str] = []

    def reg(s: str) -> str:
        texts.append(s)
        return s

    # Pass 1 collects every string to translate; pass 2 renders with the translations.
    def render(tr) -> str:
        e = lambda s: escape(tr(s))  # noqa: E731
        h: list[str] = []
        h.append(f"<h1>{e('Claim Readiness Report')}</h1><p class=s>Covara {claim.id[:8]} · {claim.created_at:%d %b %Y}</p>")
        status = {"ready": "Ready to submit", "needs_attention": "Needs attention", "incomplete": "Incomplete"}.get(
            results.readiness_status.value if results.readiness_status else "", "Not assessed")
        h.append(f"<h2>{e(status)}</h2><p>{e(results.readiness_explanation)}</p>")
        if results.packet_status:
            h.append(f"<p class=s>{e('Claim packet status')}: {e(results.packet_status)}</p>")

        h.append(f"<h2>{e('1. Claim summary')}</h2><table>")
        for label, value, _ in data.summary_rows(claim, results):
            v = tr(value) if value in {"Not found", "Not entered", "Reimbursement", "Cashless"} else value
            h.append(f"<tr><th>{e(label)}</th><td>{escape(v)}</td></tr>")
        h.append("</table>")

        h.append(f"<h2>{e('2. Documents received')}</h2><table><tr><th>{e('File')}</th><th>{e('Type')}</th><th>{e('Pages')}</th></tr>")
        for d, doc_type, pages in data.ordered_documents(claim, results):
            h.append(f"<tr><td>{escape(d.original_filename)}</td><td>{e(data.DOC_LABEL.get(doc_type, doc_type))}</td><td>{pages or ''}</td></tr>")
        h.append("</table>")

        open_f = data.open_findings(results)
        clauses = {c.id: c for c in results.clauses}
        h.append(f"<h2>{e('3. Findings and evidence')}</h2>")
        if not open_f:
            h.append(f"<p>{e('No issues were found by the checks Covara ran.')}</p>")
        for f in open_f:
            h.append(f"<h3>{e(f.title)}</h3><p>{e(f.description)}</p>")
            for ev in f.evidence:
                h.append(f"<p class=s>{e('Evidence')}: {escape(evidence_text(ev))}</p>")
            for l in f.clause_links:
                c = clauses.get(l.clause_id)
                if c:
                    h.append(f"<p class=s>{e('Policy clause')} {escape(c.clause_ref)} ({escape(c.filename)}, {e('page')} {c.page_number}): "
                             f"&quot;{escape(l.quote)}&quot;</p>")
        if results.checks_passed:
            h.append(f"<h3>{e('Checks that appear consistent')}</h3><ul>" + "".join(f"<li>{e(c)}</li>" for c in results.checks_passed) + "</ul>")

        h.append(f"<h2>{e('4. What to do next')}</h2>")
        for a in sorted(results.action_plan, key=lambda x: (not x.blocking, x.done)):
            h.append(f"<h3>{e(a.title)} <span class=s>({e(OWNER[a.owner.value if hasattr(a.owner, 'value') else a.owner])})</span></h3>")
            h.append("<ol>" + "".join(f"<li>{e(s)}</li>" for s in a.how) + "</ol>")
            if a.draft_message:
                h.append(f"<p class=s>{e('Message you can send')}: {e(a.draft_message)}</p>")

        h.append(f"<h2>{e('5. Document checklist')}</h2><table><tr><th>{e('Document')}</th><th>{e('Required')}</th><th>{e('Received')}</th></tr>")
        for c in results.checklist:
            h.append(f"<tr><td>{e(c.label)}</td><td>{e('Yes' if c.required else 'No')}</td><td>{e('Yes' if c.received else 'No')}</td></tr>")
        h.append("</table>")
        h.append(f"<h2>{e('Important')}</h2><p>{e(results.disclaimer)}</p>"
                 f"<p class=s>{e('This report is an AI-assisted preparation aid. Findings are observations to review, not conclusions. It does not decide whether an insurer will accept, reduce or reject a claim.')}</p>")
        return "".join(h)

    render(lambda s: reg(s) or s)
    unique = [t for t in dict.fromkeys(texts) if t.strip()]
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            done = dict(zip(unique, pool.map(lambda s: sarvam.translate(s, lang), unique)))
    except sarvam.SarvamError as exc:
        raise TranslationUnavailable("Translation failed.") from exc
    body = render(lambda s: done[s][0] if s in done else s)

    story = pymupdf.Story(body, user_css=CSS, archive=pymupdf.Archive(str(FONTS)))
    out = pymupdf.open()
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    page_rect, where = pymupdf.paper_rect("a4"), pymupdf.paper_rect("a4") + (40, 42, -40, -46)
    more = True
    while more:
        dev = writer.begin_page(page_rect)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    out.close()
    return buf.getvalue()
