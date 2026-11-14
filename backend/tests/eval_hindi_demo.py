"""Live check of the Hindi demo claim (sample_documents/hindi_demo_upload.zip): Sarvam OCR + Claude.

Uploads every file with category "other" (the chat flow does this), so document types must be detected
automatically. Expected: V4 amount mismatch (Hindi bill 85,000 vs claimed 95,000), V2 name variant on the
receipt, no missing prescription; after correcting the amount the packet reads "Prepared for submission".

    cd backend && .venv/bin/python -m tests.eval_hindi_demo
"""

from __future__ import annotations

import re
import sys
import tempfile
import zipfile
from pathlib import Path

from fastapi.testclient import TestClient

ZIP = Path(__file__).resolve().parents[2] / "sample_documents" / "hindi_demo_upload.zip"
EXPECT_TYPES = {"hindi_final_bill_scan.jpg": "final_bill", "hindi_prescription_scan.jpg": "prescription",
                "claim_b_policy.pdf": "policy", "claim_b_itemised_bill.pdf": "itemised_bill",
                "claim_b_discharge_summary.pdf": "discharge_summary", "claim_b_payment_receipt.pdf": "payment_receipt"}


def main() -> int:
    from app.config import get_settings
    from app.main import app
    from app.modules.pipeline import runner
    from app.schemas.results import AnalysisResults
    from app.services import claim_store

    s = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="covara-hi-"))
    s.upload_dir, s.cache_dir = tmp / "uploads", tmp / "cache"
    claim_store.reset()
    runner.reset()
    client = TestClient(app)
    cid = client.post("/claims", json={"claimed_amount": 95000, "patient_name": "Ravi Kumar Sharma",
                                       "consent_given": True}).json()["id"]
    with zipfile.ZipFile(ZIP) as z:
        for name in z.namelist():
            mime = "image/jpeg" if name.endswith(".jpg") else "application/pdf"
            r = client.post(f"/claims/{cid}/documents", data={"category": "other"}, files=[("files", (name, z.read(name), mime))])
            assert r.status_code == 201, r.text
    print("analysing...", flush=True)
    client.post(f"/claims/{cid}/analyze")
    res = AnalysisResults.model_validate(client.get(f"/claims/{cid}/results").json())
    assert res.status == "complete", res.error

    squash = lambda t: re.sub(r"[^a-z0-9]", "", str(t).lower())
    docs = {d.filename: d for d in res.documents}
    fields = {(f.key, f.evidence.filename): f for f in res.fields}
    by_rule = {(f.rule_id, f.issue_type): f for f in res.findings}
    checks = {
        **{f"type of {n} detected as {t}": docs[n].doc_type == t for n, t in EXPECT_TYPES.items()},
        "Hindi bill read by Sarvam": docs["hindi_final_bill_scan.jpg"].extraction_method.startswith("sarvam"),
        "Hindi prescription read by Sarvam": docs["hindi_prescription_scan.jpg"].extraction_method.startswith("sarvam"),
        "bill_total 85000 from Hindi bill": (f := fields.get(("bill_total", "hindi_final_bill_scan.jpg"))) is not None and f.value == 85000,
        "bill_number from Hindi bill": (f := fields.get(("bill_number", "hindi_final_bill_scan.jpg"))) is not None and squash(f.value) == "inv20260810457",
        "patient name transliterated (Hindi bill)": (f := fields.get(("patient_name", "hindi_final_bill_scan.jpg"))) is not None and squash(f.value) == "ravikumarsharma",
        "admission date ISO (Hindi bill)": (f := fields.get(("admission_date", "hindi_final_bill_scan.jpg"))) is not None and f.value == "2026-08-12",
        "Hindi bill quote has a highlight box": (f := fields.get(("bill_total", "hindi_final_bill_scan.jpg"))) is not None and f.evidence.bbox is not None,
        "V4 amount mismatch found (blocking)": ("V4", "amount_mismatch") in by_rule and by_rule[("V4", "amount_mismatch")].blocking,
        "V2 name variant found": ("V2", "name_variant") in by_rule,
        "prescription NOT reported missing": ("V7", "referenced_document_missing") not in by_rule,
        "no duplicate-bill false alarm": ("V1", "duplicate_bill") not in by_rule,
    }
    client.patch(f"/claims/{cid}", json={"claimed_amount": 85000})
    client.post(f"/claims/{cid}/analyze")
    after = AnalysisResults.model_validate(client.get(f"/claims/{cid}/results").json())
    checks["after correcting the amount: Prepared for submission"] = after.packet_status == "Prepared for submission"

    bad = [k for k, v in checks.items() if not v]
    for k, v in checks.items():
        print(("PASS " if v else "FAIL ") + k)
    print(f"\n{len(checks) - len(bad)}/{len(checks)} checks; providers: {res.providers_used}; "
          f"model calls: {len(res.llm_calls)} ({sum(c.ok for c in res.llm_calls)} ok)")
    print("open findings:", sorted(f"{f.rule_id}:{f.issue_type}" for f in res.findings))
    print("low-confidence fields:", [(f.key, f.evidence.filename, f.confidence, f.value) for f in res.fields
                                     if f.confidence < 0.75 and f.key in __import__("app.schemas.results", fromlist=["x"]).CRITICAL_KEYS])
    print("warnings:", res.warnings)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
