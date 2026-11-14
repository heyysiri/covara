"""Readiness Report PDF: the user-facing explanation of the analysis (PLAN.md step 8, sections 1-9)."""

from __future__ import annotations

from reportlab.lib.units import mm
from reportlab.platypus import KeepTogether, PageBreak, Spacer

from app.schemas.claim import ClaimOut
from app.schemas.results import AnalysisResults, EvidenceRef, Finding

from . import data
from .pdf_common import AMBER, BANNER, BODY, CELL, CONTENT_W, GREEN, H1, H2, H3, RED, SMALL, P, build, esc, table
from reportlab.platypus import Paragraph

READINESS = {"ready": ("Ready to submit", GREEN), "needs_attention": ("Needs attention", AMBER), "incomplete": ("Incomplete", RED)}
OWNER = {"user": "You", "hospital": "Hospital", "doctor": "Doctor", "insurer": "Insurer"}


def evidence_text(e: EvidenceRef) -> str:
    if e.source == "document":
        where = f"{e.filename}, page {e.page_number}" + (f", field {e.field.replace('_', ' ')}" if e.field else "")
        return f"{where}: \"{e.quote}\"" if e.quote else where
    if e.source == "claim_form":
        value = data.money(e.value) if (e.field or "").endswith("amount") else e.value
        return f"Claim form, {(e.field or '').replace('_', ' ')}: {value}"
    return f"Document checklist, {(e.field or '').replace('_', ' ')}: {e.value}"


def finding_block(f: Finding, clauses: dict) -> list:
    tags = [f"{f.severity.value} severity", "confirmed mismatch" if f.kind == "confirmed" else "possible, please review"]
    if f.blocking:
        tags.append("blocks the packet")
    out: list = [P(f"{f.title}", H3), P(" | ".join(tags), SMALL), P(f.description)]
    if f.extracted_value is not None and f.comparison_value is not None:
        out.append(P(f"Values compared: {f.extracted_value} vs {f.comparison_value}", SMALL))
    if f.exposure_amount is not None:
        out.append(P(f"Estimated amount to review: {data.money(f.exposure_amount)}. This is an estimate, not a coverage decision.", SMALL))
    for e in f.evidence:
        out.append(P(f"Evidence: {evidence_text(e)}", SMALL))
    for l in f.clause_links:
        c = clauses.get(l.clause_id)
        if c:
            label = {"applies": "applies", "may_apply": "may apply", "does_not_apply": "does not apply"}[l.verdict]
            out.append(P(f"Policy clause {c.clause_ref} ({c.filename}, page {c.page_number}) {label}: \"{l.quote}\"", SMALL))
    return [KeepTogether(out)]


def build_report(claim: ClaimOut, results: AnalysisResults) -> bytes:
    s: list = []
    status_label, color = READINESS.get(results.readiness_status.value if results.readiness_status else "", ("Not assessed", AMBER))
    clauses = {c.id: c for c in results.clauses}
    open_f = data.open_findings(results)

    s += [P("Claim Readiness Report", H1), P(f"Covara claim {claim.id[:8]} - prepared {claim.created_at:%d %b %Y}", SMALL)]
    s.append(Paragraph(f'<font color="{color.hexval()}">Readiness: {esc(status_label)}</font>', BANNER))
    s.append(P(results.readiness_explanation or "", BODY))
    if results.packet_status:
        s.append(P(f"Claim packet status: {results.packet_status}", SMALL))

    # 1 - claim summary
    s.append(P("1. Claim summary", H2))
    s.append(table([[label, value] for label, value, _ in data.summary_rows(claim, results)], [60 * mm, CONTENT_W - 60 * mm], header=False))

    # 2 - documents received
    s.append(P("2. Documents received", H2))
    rows = [["File", "Type", "Pages", "Status"]]
    for d, doc_type, pages in data.ordered_documents(claim, results):
        meta = next((m for m in results.documents if m.id == d.id), None)
        rows.append([d.original_filename, data.DOC_LABEL.get(doc_type, doc_type), str(pages or ""), (meta.status if meta else d.status.value)])
    s.append(table(rows, [78 * mm, 42 * mm, 18 * mm, CONTENT_W - 138 * mm]))

    # 3 - extracted information
    s.append(P("3. Extracted information", H2))
    s.append(P("Values are shown as written in your documents, with where each one was found. Anything not found is marked, never guessed.", SMALL))
    rows = [["Item", "Value", "Source"]]
    for label, value, f in data.summary_rows(claim, results):
        if f is not None:
            src = f"{f.evidence.filename}, p.{f.evidence.page_number}" + (" (low confidence)" if f.confidence < 0.75 and not f.user_confirmed else "")
            rows.append([label, value, src])
    s.append(table(rows, [52 * mm, 58 * mm, CONTENT_W - 110 * mm]))

    # 4 - readiness
    s.append(P("4. Readiness status", H2))
    blocking = data.blocking_findings(results)
    s.append(P(f"{len(blocking)} blocking item(s) and {len(open_f) - len(blocking)} item(s) to review. "
               "Blocking items should be fixed before the claim packet is treated as complete."))
    if results.checks_passed:
        s.append(P("Checks that appear consistent", H3))
        for c in results.checks_passed:
            s.append(P(f"- {c}", CELL))

    # 5 - issues and evidence
    s.append(P("5. Issues and supporting evidence", H2))
    if not open_f:
        s.append(P("No issues were found by the checks Covara ran."))
    for f in open_f:
        s += finding_block(f, clauses)

    # 6 - policy clauses
    s.append(P("6. Relevant policy clauses", H2))
    linked = {l.clause_id for f in open_f for l in f.clause_links}
    shown = [c for c in results.clauses if c.id in linked]
    if not shown:
        s.append(P("No policy clause was linked to the findings. Covara does not invent clauses; if a clause cannot be found it says so."))
    for c in shown:
        s.append(KeepTogether([P(f"Clause {c.clause_ref} - {c.title} ({c.filename}, page {c.page_number})", H3), P(c.text, SMALL)]))
    ps = results.policy_summary
    if ps:
        rows = [["Policy fact", "Value", "Source"]]
        for label, v in (("Sum insured", ps.sum_insured), ("Room-rent limit", ps.room_rent_cap), ("Co-payment", ps.copay),
                         ("Pre-hospitalisation", ps.pre_hosp_days), ("Post-hospitalisation", ps.post_hosp_days)):
            if v:
                rows.append([label, v.text, f"{v.evidence.filename}, p.{v.evidence.page_number}"])
        for w in ps.waiting_periods:
            rows.append([w.name, f"{w.days} days", f"{w.evidence.filename}, p.{w.evidence.page_number}"])
        if len(rows) > 1:
            s += [Spacer(1, 4), table(rows, [52 * mm, 58 * mm, CONTENT_W - 110 * mm])]

    # 7 - actions
    s.append(P("7. Recommended next actions", H2))
    if not results.action_plan:
        s.append(P("No actions are needed."))
    for a in sorted(results.action_plan, key=lambda x: (not x.blocking, x.done)):
        block = [P(f"{a.title}", H3), P(f"For: {OWNER[a.owner]}" + (" | blocking" if a.blocking else "") + (" | done" if a.done else ""), SMALL), P(a.why)]
        block += [P(f"{i}. {h}", CELL) for i, h in enumerate(a.how, 1)]
        if a.draft_message:
            block.append(P(f"Message you can send: {a.draft_message}", SMALL))
        s.append(KeepTogether(block))

    # 8 - checklist
    s.append(P("8. Missing-document checklist", H2))
    rows = [["Document", "Required", "Received", "Note"]]
    for c in results.checklist:
        rows.append([c.label, "Yes" if c.required else "No", "Yes" if c.received else "No", c.reason])
    s.append(table(rows, [42 * mm, 18 * mm, 18 * mm, CONTENT_W - 78 * mm]))

    # 9 - disclaimer
    s.append(P("9. Important", H2))
    s.append(P(results.disclaimer))
    s.append(P("This report is an AI-assisted preparation aid. Findings are observations to review, not conclusions. "
               "It does not decide whether an insurer will accept, reduce or reject a claim, and it does not replace an insurer, "
               "doctor, broker or licensed adviser.", SMALL))
    return build(s, "Covara Claim Readiness Report", f"Covara claim {claim.id[:8]}")
