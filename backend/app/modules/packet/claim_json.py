"""claim.json: the packet's contents as structured data.

Field names are chosen so this can later be mapped to an NHCX-style FHIR claim bundle (patient, coverage,
provider, encounter, billing, documents). It is NOT a FHIR resource and no exchange integration is built.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.claim import ClaimOut
from app.schemas.results import AnalysisResults

from . import data


def _num(v: object) -> float | None:
    try:
        return float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def build_claim_json(claim: ClaimOut, results: AnalysisResults) -> dict:
    v = lambda key: data.value_of(results, key)  # noqa: E731
    open_f = data.open_findings(results)
    ps = results.policy_summary
    doc_meta = {d.id: d for d in results.documents}
    final_bill = next((d.id for d in results.documents if d.doc_type == "itemised_bill"), None)
    line_items = [
        {"description": f.raw_text, "amount": _num(f.value), "source": f.evidence.filename}
        for f in results.fields if f.key == "line_item" and (final_bill is None or f.evidence.document_id == final_bill)
    ]
    return {
        "schema": "covara.claim.v1",
        "note": "Field names are chosen so this can later be mapped to an NHCX-style FHIR bundle. This is not a FHIR resource.",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": {
            "packet": results.packet_status,
            "readiness": results.readiness_status.value if results.readiness_status else None,
            "open_findings": len(open_f),
            "blocking_findings": len(data.blocking_findings(results)),
        },
        "claim": {"id": claim.id, "type": claim.claim_type.value, "domain": claim.domain.value,
                  "claimed_amount": claim.claimed_amount, "currency": "INR",
                  "consent_at": claim.consent_at.isoformat() if claim.consent_at else None},
        "patient": {"name": v("patient_name"), "age": v("age")},
        "coverage": {"insurer": v("insurer"), "policy_number": v("policy_number"), "member_id": v("member_id"),
                     "first_enrolment": v("policy_inception"), "period_start": v("policy_start"), "period_end": v("policy_end"),
                     "sum_insured": ps.sum_insured.value if ps and ps.sum_insured else v("sum_insured"),
                     "room_rent_cap_per_day": ps.room_rent_cap.value if ps and ps.room_rent_cap else None},
        "provider": {"name": v("hospital_name")},
        "encounter": {"admission_date": v("admission_date"), "discharge_date": v("discharge_date"),
                      "diagnosis_as_written": v("diagnosis"), "treatment_as_written": v("treatment")},
        "billing": {"invoice_number": v("bill_number"), "bill_date": v("bill_date"), "total": _num(v("bill_total")),
                    "line_items": line_items,
                    "receipts": [{"amount": _num(f.value), "source": f.evidence.filename} for f in results.fields if f.key == "receipt_amount"]},
        "documents": [
            {"id": d.id, "filename": d.original_filename, "type": t, "pages": pages or None, "sha256": d.sha256,
             "received_at": d.uploaded_at.isoformat(), "status": doc_meta[d.id].status if d.id in doc_meta else d.status.value}
            for d, t, pages in data.ordered_documents(claim, results)
        ],
        "findings": [
            {"id": f.id, "rule": f.rule_id, "type": f.issue_type, "severity": f.severity.value, "kind": f.kind,
             "blocking": f.blocking, "title": f.title, "exposure_estimate_inr": f.exposure_amount,
             "evidence": [{"source": e.source, "document_id": e.document_id, "filename": e.filename, "page": e.page_number,
                           "quote": e.quote, "field": e.field, "value": e.value} for e in f.evidence],
             "clauses": [{"clause_id": l.clause_id, "verdict": l.verdict, "quote": l.quote} for l in f.clause_links]}
            for f in open_f
        ],
        "clauses": [{"id": c.id, "ref": c.clause_ref, "type": c.type, "title": c.title, "filename": c.filename, "page": c.page_number}
                    for c in results.clauses if c.id in {l.clause_id for f in open_f for l in f.clause_links}],
        "disclaimer": results.disclaimer,
    }
