"""Required-document checklist (decision D4). Deterministic; works before any AI runs.

Required: policy, final bill, itemised bill, discharge summary, payment receipt (reimbursement only).
Prescription / diagnostic report: required only when another document references them.
An itemised bill is satisfied by a final bill that lists line items.
"""

from __future__ import annotations

from app.schemas.results import ChecklistItem, DocumentResult, DocType, ExtractedField

LABELS: dict[str, str] = {
    "policy": "Insurance policy / schedule",
    "final_bill": "Hospital final bill",
    "itemised_bill": "Itemised bill",
    "discharge_summary": "Discharge summary",
    "payment_receipt": "Payment receipt",
    "prescription": "Prescription",
    "diagnostic_report": "Diagnostic / lab report",
}
REQUIRED_ALWAYS: list[DocType] = ["policy", "final_bill", "itemised_bill", "discharge_summary"]
REQUIRED_IF_REFERENCED: list[DocType] = ["prescription", "diagnostic_report"]


def build_checklist(claim_type: str, documents: list[DocumentResult],
                    fields: list[ExtractedField] | None = None) -> list[ChecklistItem]:
    fields = fields or []
    by_type: dict[str, list[str]] = {}
    for d in documents:
        if d.status != "failed":
            by_type.setdefault(d.doc_type, []).append(d.id)

    required = list(REQUIRED_ALWAYS)
    if claim_type == "reimbursement":
        required.append("payment_receipt")

    items: list[ChecklistItem] = []
    for cat in required:
        ids = by_type.get(cat, [])
        reason = "Required for a health-insurance claim."
        if cat == "payment_receipt":
            reason = "Required for reimbursement claims (proof of payment)."
        if cat == "itemised_bill" and not ids:
            bill_ids = by_type.get("final_bill", [])
            items_in_bill = [f for f in fields if f.key == "line_item" and f.evidence.document_id in bill_ids]
            if len(items_in_bill) >= 2:
                ids = bill_ids
                reason = f"Satisfied by the final bill, which lists {len(items_in_bill)} line items."
        items.append(ChecklistItem(category=cat, label=LABELS[cat], required=True, received=bool(ids),
                                   document_ids=ids, reason=reason))

    refs = {str(f.value): f for f in fields if f.key == "referenced_document"}
    for cat in REQUIRED_IF_REFERENCED:
        ids = by_type.get(cat, [])
        ref = refs.get(cat)
        if ref:
            reason = f"Referenced in {ref.evidence.filename} (page {ref.evidence.page_number})."
        else:
            reason = "Needed only if another document refers to it."
        items.append(ChecklistItem(category=cat, label=LABELS[cat], required=ref is not None,
                                   received=bool(ids), document_ids=ids, reason=reason,
                                   evidence=ref.evidence if ref else None))
    return items
