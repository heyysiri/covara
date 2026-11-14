"""M7: Readiness Report, Claim Packet and claim.json, built from a real (offline) pipeline run on claim B."""

import hashlib
import json
from pathlib import Path

import pymupdf
import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.modules.packet.data import money
from app.modules.packet.pdf_common import safe
from app.modules.pipeline import runner
from app.services import claim_store

SAMPLES = Path(__file__).resolve().parents[2] / "sample_documents"
TRUTH = SAMPLES / "expected_results" / "claim_b.json"
pytestmark = pytest.mark.skipif(not TRUTH.exists(), reason="sample documents not generated")

TITLE_ON_PAGE = {  # text printed on the first page of each original, to prove the right page is bookmarked
    "claim_b_policy.pdf": "POLICY SCHEDULE", "claim_b_final_bill.pdf": "FINAL BILL", "claim_b_final_bill_copy.pdf": "FINAL BILL",
    "claim_b_itemised_bill.pdf": "ITEMISED BILL", "claim_b_discharge_summary.pdf": "DISCHARGE SUMMARY",
    "claim_b_payment_receipt.pdf": "PAYMENT RECEIPT",
}


@pytest.fixture
def analysed(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(s, "cache_dir", tmp_path / "cache")
    for key in ("anthropic_api_key", "gemini_api_key", "groq_api_key"):
        monkeypatch.setattr(s, key, "")
    monkeypatch.setattr(s, "claude_use_cli", False)  # rules-only path: offline and deterministic
    claim_store.reset()
    runner.reset()
    client = TestClient(app)
    truth = json.loads(TRUTH.read_text())
    cid = client.post("/claims", json={**truth["claim_input"], "consent_given": True}).json()["id"]
    for item in truth["upload_set"]:
        p = SAMPLES / item["file"]
        r = client.post(f"/claims/{cid}/documents", data={"category": item["doc_type"]},
                        files=[("files", (p.name, p.read_bytes(), "application/pdf"))])
        assert r.status_code == 201
    client.post(f"/claims/{cid}/analyze")
    assert client.get(f"/claims/{cid}/results").json()["status"] == "complete"
    return client, cid


def pdf_pages(data: bytes) -> list[str]:
    with pymupdf.open("pdf", data) as d:
        return [p.get_text() for p in d]


def set_status(cid: str, status: str, clear_findings: bool = False) -> None:
    res = runner.get_results(cid)
    res.packet_status = status
    if clear_findings:
        res.findings = []


# ---------------------------------------------------------------- helpers
def test_money_uses_indian_grouping():
    assert money(500000) == "Rs. 5,00,000" and money(85000) == "Rs. 85,000" and money(999) == "Rs. 999"
    assert money(1234.5) == "Rs. 1,234.50" and money(12345678) == "Rs. 1,23,45,678" and money(None) == "Not found"


def test_rupee_sign_is_mapped_for_the_built_in_pdf_fonts():
    assert safe("about ₹23,867 could be affected") == "about Rs. 23,867 could be affected"


# ---------------------------------------------------------------- report
def test_report_has_every_planned_section_and_the_claims_facts(analysed):
    client, cid = analysed
    r = client.get(f"/claims/{cid}/report")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    text = "\n".join(pdf_pages(r.content))
    for heading in ("Claim Readiness Report", "1. Claim summary", "2. Documents received", "3. Extracted information",
                    "4. Readiness status", "5. Issues and supporting evidence", "6. Relevant policy clauses",
                    "7. Recommended next actions", "8. Missing-document checklist", "9. Important"):
        assert heading in text, heading
    for fact in ("Ravi Kumar Sharma", "Rs. 95,000", "INV-2026-08-10457", "claim_b_final_bill_copy.pdf"):
        assert fact in text, fact
    # the offline rules path does not read every field; the report must say so instead of guessing
    assert "Hospital" in text and "Not found" in text
    assert "not an insurer decision" in text.lower() or "does not decide whether an insurer" in text


def test_report_cites_evidence_and_never_uses_alarming_words(analysed):
    client, cid = analysed
    text = "\n".join(pdf_pages(client.get(f"/claims/{cid}/report").content))
    assert "Evidence:" in text and "page 1" in text
    for word in ("fraud", "will be rejected", "will be approved", "guaranteed"):
        assert word not in text.lower()


# ---------------------------------------------------------------- packet
def test_packet_contains_every_original_in_order_with_correct_bookmarks(analysed):
    client, cid = analysed
    r = client.get(f"/claims/{cid}/packet")
    assert r.status_code == 200 and r.headers["content-type"] == "application/pdf"
    with pymupdf.open("pdf", r.content) as d:
        toc = d.get_toc()
        assert toc[0][1].startswith("Cover") and toc[0][2] == 1
        docs = toc[1:]
        assert len(docs) == 6
        order = [t[1].split(" - ", 1)[1] for t in docs]
        assert order[0] == "claim_b_policy.pdf"  # policy first, receipt last
        assert order[-1] == "claim_b_payment_receipt.pdf"
        for _, title, page in docs:  # each bookmark lands on that document's first page
            name = title.split(" - ", 1)[1]
            assert TITLE_ON_PAGE[name] in d[page - 1].get_text(), (name, page)
        originals = 6 + 1 + 1 + 1 + 1 + 1
        assert d.page_count - originals == docs[0][2] - 1 >= 1  # front matter + 11 original pages


def test_packet_index_page_numbers_match_the_bookmarks(analysed):
    client, cid = analysed
    with pymupdf.open("pdf", client.get(f"/claims/{cid}/packet").content) as d:
        docs = d.get_toc()[1:]
        first = d[0].get_text() + (d[1].get_text() if docs[0][2] > 2 else "")
        for _, title, page in docs:
            name = title.split(" - ", 1)[1]
            assert name in first, name
        assert f"{docs[0][2]}-{docs[0][2] + 5}" in first.replace(" ", "")  # policy occupies 6 pages


def test_incomplete_packet_is_stamped_on_every_page(analysed):
    client, cid = analysed
    status = runner.get_results(cid).packet_status
    assert status.startswith("INCOMPLETE")
    pages = pdf_pages(client.get(f"/claims/{cid}/packet").content)
    assert all("INCOMPLETE" in p for p in pages), [i for i, p in enumerate(pages, 1) if "INCOMPLETE" not in p]
    assert status in pages[0]


def test_prepared_packet_has_no_incomplete_stamp(analysed):
    client, cid = analysed
    set_status(cid, "Prepared for submission", clear_findings=True)
    pages = pdf_pages(client.get(f"/claims/{cid}/packet").content)
    assert "Prepared for submission" in pages[0]
    assert not any("INCOMPLETE" in p for p in pages)
    assert "approved" not in "\n".join(pages).lower().replace("not an insurer decision", "")


def test_stored_originals_are_not_modified_by_building_a_packet(analysed):
    client, cid = analysed
    stored = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in get_settings().upload_dir.rglob("*.pdf")}
    client.get(f"/claims/{cid}/packet")
    assert stored and all(hashlib.sha256(p.read_bytes()).hexdigest() == h for p, h in stored.items())


def test_scanned_image_originals_become_pages(analysed, tmp_path):
    client, cid = analysed
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 200, 120), False)
    pix.set_rect(pix.irect, (230, 230, 230))
    r = client.post(f"/claims/{cid}/documents", data={"category": "prescription"},
                    files=[("files", ("scan.png", pix.tobytes("png"), "image/png"))])
    assert r.status_code == 201
    client.post(f"/claims/{cid}/analyze")
    with pymupdf.open("pdf", client.get(f"/claims/{cid}/packet").content) as d:
        titles = [t[1] for t in d.get_toc()]
        assert any("scan.png" in t for t in titles) and len(titles) == 8


# ---------------------------------------------------------------- claim.json
def test_claim_json_is_structured_and_evidence_linked(analysed):
    client, cid = analysed
    r = client.get(f"/claims/{cid}/packet.json")
    assert r.status_code == 200 and r.headers["content-type"] == "application/json"
    j = r.json()
    assert j["schema"] == "covara.claim.v1" and "not a FHIR resource" in j["note"]
    assert j["claim"]["claimed_amount"] == 95000 and j["claim"]["currency"] == "INR"
    assert j["patient"]["name"] == "Ravi Kumar Sharma" and j["coverage"]["policy_number"] == "SSH-2026-004567"
    assert j["billing"]["total"] == 85000 and j["encounter"]["admission_date"] == "2026-08-12"
    assert len(j["documents"]) == 6 and all(len(d["sha256"]) == 64 for d in j["documents"])
    assert j["status"]["packet"] == runner.get_results(cid).packet_status
    assert j["findings"] and all(f["evidence"] for f in j["findings"])  # I1 holds in the export too


# ---------------------------------------------------------------- errors
def test_nothing_is_generated_before_the_analysis_completes(analysed):
    client, _ = analysed
    cid = client.post("/claims", json={"consent_given": True}).json()["id"]
    for path in ("report", "packet", "packet.json"):
        r = client.get(f"/claims/{cid}/{path}")
        assert r.status_code == 409 and "analysis" in r.json()["detail"].lower()
    assert client.get("/claims/nope/report").status_code == 404
