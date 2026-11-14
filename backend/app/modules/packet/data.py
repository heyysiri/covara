"""Facts shown in the report, the packet and claim.json, read from the analysis results.

Everything here comes from already-verified results (extracted fields with evidence, findings, clauses).
Nothing is generated or guessed: a value that was not found is shown as "Not found".
"""

from __future__ import annotations

from datetime import date, datetime

from app.modules.intake.checklist import LABELS
from app.schemas.claim import ClaimOut
from app.schemas.results import AnalysisResults, ExtractedField

# Labels and the order documents appear in come from the checklist, the single place that knows document types.
DOC_LABEL = {**LABELS, "other": "Other document"}
DOC_ORDER = [*LABELS, "other"]


def _indian_grouping(n: int) -> str:
    """500000 -> '5,00,000'."""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def money(v: float | int | str | None) -> str:
    try:
        n = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return "Not found"
    whole = int(abs(n))
    paise = round((abs(n) - whole) * 100)
    text = _indian_grouping(whole) + (f".{paise:02d}" if paise else "")
    return f"Rs. {'-' if n < 0 else ''}{text}"


def pretty_date(v: object) -> str:
    try:
        d = v if isinstance(v, date) else datetime.strptime(str(v), "%Y-%m-%d").date()
        return f"{d.day} {d.strftime('%b %Y')}"
    except (TypeError, ValueError):
        return str(v) if v not in (None, "") else "Not found"


def pick(results: AnalysisResults, key: str) -> ExtractedField | None:
    """The field to display for a key: user-confirmed first, then highest confidence, then document order."""
    fields = [f for f in results.fields if f.key == key and f.value not in (None, "")]
    if not fields:
        return None
    doc_type = {d.id: d.doc_type for d in results.documents}
    order = {t: i for i, t in enumerate(DOC_ORDER)}
    return min(fields, key=lambda f: (not f.user_confirmed, -f.confidence, order.get(doc_type.get(f.evidence.document_id or "", ""), len(order))))


def value_of(results: AnalysisResults, key: str) -> object | None:
    f = pick(results, key)
    return f.value if f else None


def display(key: str, value: object) -> str:
    if value in (None, ""):
        return "Not found"
    if key.endswith("_date") or key in ("policy_start", "policy_end", "policy_inception"):
        return pretty_date(value)
    if key in ("bill_total", "sum_insured", "receipt_amount", "room_rent_cap", "room_rent_charged_per_day"):
        return money(value)  # type: ignore[arg-type]
    return str(value)


def summary_rows(claim: ClaimOut, results: AnalysisResults) -> list[tuple[str, str, ExtractedField | None]]:
    """(label, display value, source field) for the claim summary."""
    def row(label: str, key: str) -> tuple[str, str, ExtractedField | None]:
        f = pick(results, key)
        return label, display(key, f.value if f else None), f

    period = (pick(results, "policy_start"), pick(results, "policy_end"))
    rows = [
        ("Claim type", claim.claim_type.value.capitalize(), None),
        ("Amount claimed", money(claim.claimed_amount) if claim.claimed_amount is not None else "Not entered", None),
        row("Patient", "patient_name"), row("Insurer", "insurer"), row("Policy number", "policy_number"),
        row("Member ID", "member_id"),
        row("First enrolled", "policy_inception"),
        ("Policy period", " to ".join(display("x_date", f.value) for f in period if f) or "Not found", period[0]),
        row("Hospital", "hospital_name"), row("Admission", "admission_date"), row("Discharge", "discharge_date"),
        row("Diagnosis (as written in the records)", "diagnosis"),
        row("Treatment (as written in the records)", "treatment"),
        row("Invoice number", "bill_number"), row("Bill total", "bill_total"),
    ]
    return rows


def ordered_documents(claim: ClaimOut, results: AnalysisResults):
    """Uploaded documents in packet order, each with its effective type and page count."""
    meta = {d.id: d for d in results.documents}
    docs = []
    for d in claim.documents:
        m = meta.get(d.id)
        doc_type = (m.doc_type if m else d.category.value) or "other"
        docs.append((d, doc_type, m.pages if m and m.pages else 0))
    order = {t: i for i, t in enumerate(DOC_ORDER)}
    return sorted(docs, key=lambda x: (order.get(x[1], len(order)), x[0].uploaded_at))


def open_findings(results: AnalysisResults):
    return [f for f in results.findings if f.status == "open"]


def blocking_findings(results: AnalysisResults):
    return [f for f in open_findings(results) if f.blocking]


def is_incomplete(results: AnalysisResults) -> bool:
    return bool(results.packet_status and results.packet_status.upper().startswith("INCOMPLETE"))
