"""Person 1 modules: intake (M1), extraction (M2), policy (M4), action plan (M6), pipeline (M8).

Runs fully offline: provider keys are blanked, so extraction uses the rules path.
"""

import sys
import types
import uuid

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.modules.pipeline import runner
from app.schemas.results import Action, EvidenceRef, Explanation, Finding
from app.services import claim_store
from tests.fixtures.make_docs import make_claim


@pytest.fixture
def client(tmp_path, monkeypatch):
    s = get_settings()
    monkeypatch.setattr(s, "upload_dir", tmp_path / "uploads")
    monkeypatch.setattr(s, "cache_dir", tmp_path / "cache")
    for k in ("anthropic_api_key", "gemini_api_key", "groq_api_key", "sarvam_api_key"):
        monkeypatch.setattr(s, k, "")
    monkeypatch.setattr(s, "claude_use_cli", False)  # never spawn the real CLI in tests
    claim_store.reset()
    runner.reset()
    sys.modules.pop("app.modules.verification.service", None)
    return TestClient(app)


@pytest.fixture
def docs(tmp_path):
    return make_claim(tmp_path / "docs")


def _upload(client, cid, category, path):
    r = client.post(f"/claims/{cid}/documents", data={"category": category},
                    files=[("files", (path.name, path.read_bytes(), "application/pdf"))])
    assert r.status_code == 201, r.text
    return r.json()


def _claim_with_docs(client, docs, skip=()):
    r = client.post("/claims", json={"claimed_amount": 95000, "patient_name": "Rajesh Kumar", "consent_given": True})
    cid = r.json()["id"]
    assert r.json()["consent_at"] is not None
    for cat, path in docs.items():
        if cat not in skip:
            _upload(client, cid, cat, path)
    return cid


def _analyze(client, cid):
    r = client.post(f"/claims/{cid}/analyze")
    assert r.status_code == 202
    res = client.get(f"/claims/{cid}/results").json()  # TestClient runs background tasks inline
    assert res["status"] == "complete", res
    return res


def test_full_pipeline_offline(client, docs):
    cid = _claim_with_docs(client, docs)
    res = _analyze(client, cid)
    assert res["progress"] == 1.0
    fields = {(f["key"], f["evidence"]["filename"]): f for f in res["fields"]}
    assert fields[("bill_total", "final_bill.pdf")]["value"] == 85000.0
    assert fields[("patient_name", "final_bill.pdf")]["value"] == "Rajesh Kumaar"
    assert fields[("admission_date", "final_bill.pdf")]["value"] == "2025-09-10"
    # Every field carries evidence with a page; rules quotes exist in the page text.
    assert all(f["evidence"]["page_number"] >= 1 and f["evidence"]["quote"] for f in res["fields"])
    line_items = [f for f in res["fields"] if f["key"] == "line_item"]
    assert sorted(f["value"] for f in line_items) == [5000, 9000, 12000, 24000, 35000]

    s = res["policy_summary"]
    assert s["sum_insured"]["value"] == 500000
    assert s["room_rent_cap"]["value"] == 5000 and s["room_rent_cap_percent"] == 1
    assert s["room_rent_cap"]["evidence"]["page_number"] == 1
    assert s["copay"]["value"] == 10
    assert {w["name"]: w["days"] for w in s["waiting_periods"]}["Pre-existing diseases"] == 1095
    room = next(c for c in res["clauses"] if c["title"] == "Room Rent Limit")
    assert room["type"] == "sublimit" and room["page_number"] == 1

    # Checklist: prescription is referenced by the discharge summary but not uploaded.
    rx = next(c for c in res["checklist"] if c["category"] == "prescription")
    assert rx["required"] and not rx["received"] and "discharge_summary.pdf" in rx["reason"]
    itemised = next(c for c in res["checklist"] if c["category"] == "itemised_bill")
    assert itemised["received"] and "line items" in itemised["reason"]
    upload_rx = next(a for a in res["action_plan"] if a["checklist_category"] == "prescription")
    assert upload_rx["blocking"] and upload_rx["draft_message"] and "City Care Hospital" in upload_rx["draft_message"]
    assert res["readiness_status"] == "needs_attention"
    assert res["packet_status"].startswith("INCOMPLETE")


def test_missing_policy_is_incomplete_and_warns(client, docs):
    cid = _claim_with_docs(client, docs, skip=("policy",))
    res = _analyze(client, cid)
    assert res["readiness_status"] == "incomplete"
    assert any("No policy" in w for w in res["warnings"])
    assert res["policy_summary"] is None


def _fake_verification(ctx):
    """Stand-in for Person 2's module: two findings computed from the context."""
    bill = ctx.fields_for("bill_total")[0]
    rent = ctx.fields_for("room_rent_charged_per_day")[0]
    cap = ctx.policy_summary.room_rent_cap
    return [
        Finding(id=uuid.uuid4().hex[:8], rule_id="V4", issue_type="amount_mismatch", severity="medium",
                kind="confirmed", title="Bill total differs from the claimed amount",
                description="The final bill total does not match the amount on the claim form.",
                evidence=[bill.evidence], extracted_value=str(bill.value),
                comparison_value=str(ctx.claim.claimed_amount), blocking=True,
                explanation=Explanation(rule="V4", inputs={"bill_total": bill.value,
                                                            "claimed_amount": ctx.claim.claimed_amount})),
        Finding(id=uuid.uuid4().hex[:8], rule_id="V10", issue_type="room_rent_cap", severity="medium",
                kind="possible", title="Room rent exceeds the policy limit",
                description="Room rent per day is above the policy's room-rent cap.",
                evidence=[rent.evidence, cap.evidence], extracted_value=str(rent.value),
                comparison_value=str(cap.value), exposure_amount=12000,
                explanation=Explanation(rule="V10", inputs={"charged": rent.value, "cap": cap.value})),
    ]


def test_verification_hook_policy_match_and_plan(client, docs, monkeypatch):
    mod = types.ModuleType("app.modules.verification.service")
    mod.run_verification = _fake_verification
    monkeypatch.setitem(sys.modules, "app.modules.verification.service", mod)
    cid = _claim_with_docs(client, docs)
    res = _analyze(client, cid)
    clauses = {c["id"]: c for c in res["clauses"]}
    v10 = next(f for f in res["findings"] if f["rule_id"] == "V10")
    assert v10["clause_links"], "room-rent finding should link to a clause"
    link = v10["clause_links"][0]
    assert clauses[link["clause_id"]]["title"] == "Room Rent Limit"
    assert link["quote"] in clauses[link["clause_id"]]["text"]  # verbatim (I9)

    acts = {a["title"]: a for a in res["action_plan"]}
    a10 = acts["Ask the insurer about the room-rent limit"]
    assert a10["owner"] == "insurer" and a10["finding_ids"] == [v10["id"]] and a10["clause_ids"]
    assert "6000.0 vs 5000.0" in a10["draft_message"]
    a4 = acts["Make the claimed amount match the bill total"]
    assert a4["blocking"] and "85000.0 vs 95000.0" in " ".join(a4["how"])
    # Blocking actions come first.
    flags = [a["blocking"] for a in res["action_plan"] if not a["done"]]
    assert flags == sorted(flags, reverse=True)


def test_review_edit_and_recheck(client, docs):
    cid = _claim_with_docs(client, docs)
    res = _analyze(client, cid)
    name = next(f for f in res["fields"] if f["key"] == "patient_name" and f["evidence"]["filename"] == "final_bill.pdf")
    r = client.post(f"/claims/{cid}/review", json={"edits": [{"field_id": name["id"], "value": "Rajesh Kumar"}]})
    assert r.status_code == 202
    res2 = client.get(f"/claims/{cid}/results").json()
    edited = next(f for f in res2["fields"] if f["id"] == name["id"])
    assert edited["value"] == "Rajesh Kumar" and edited["user_confirmed"] and edited["method"] == "user"
    assert client.post(f"/claims/{cid}/review", json={"edits": [{"field_id": "nope"}]}).status_code == 422


def test_action_done_persists_across_recheck(client, docs):
    cid = _claim_with_docs(client, docs)
    res = _analyze(client, cid)
    aid = res["action_plan"][0]["id"]
    assert client.patch(f"/claims/{cid}/actions/{aid}", json={"done": True}).json()["done"]
    res2 = _analyze(client, cid)
    assert next(a for a in res2["action_plan"] if a["id"] == aid)["done"]
    assert client.patch(f"/claims/{cid}/actions/missing", json={"done": True}).status_code == 404


def test_duplicate_upload_detected(client, docs):
    cid = _claim_with_docs(client, docs)
    body = _upload(client, cid, "final_bill", docs["final_bill"])
    assert body["duplicates"] and body["duplicates"][0]["duplicate_of"]


def test_checklist_before_analysis_and_file_download(client, docs):
    cid = _claim_with_docs(client, docs, skip=("discharge_summary",))
    items = {c["category"]: c for c in client.get(f"/claims/{cid}/checklist").json()}
    assert items["policy"]["received"] and not items["discharge_summary"]["received"]
    doc = client.get(f"/claims/{cid}/documents").json()[0]
    r = client.get(f"/claims/{cid}/documents/{doc['id']}/file")
    assert r.status_code == 200 and r.content.startswith(b"%PDF")


def test_delete_my_data(client, docs, tmp_path):
    cid = _claim_with_docs(client, docs)
    _analyze(client, cid)
    assert (get_settings().upload_dir / cid).exists()
    assert client.delete(f"/claims/{cid}").status_code == 204
    assert not (get_settings().upload_dir / cid).exists()
    assert client.get(f"/claims/{cid}").status_code == 404
    assert runner.get_results(cid).status == "idle"


def test_patch_claim_amount(client, docs):
    cid = _claim_with_docs(client, docs)
    r = client.patch(f"/claims/{cid}", json={"claimed_amount": 85000})
    assert r.json()["claimed_amount"] == 85000


def test_invariants():
    ev = EvidenceRef(document_id="d", filename="f.pdf", page_number=1)
    with pytest.raises(ValueError):
        Finding(id="x", rule_id="V4", issue_type="t", severity="low", kind="possible", title="t",
                description="d", evidence=[], explanation=Explanation(rule="V4"))
    with pytest.raises(ValueError):
        Action(id="a", title="t", why="w", owner="user", group="verify_or_correct")
    Action(id="a", title="t", why="w", owner="user", group="upload", checklist_category="policy")
    assert ev.page_number == 1


def test_quote_verification_rejects_invented_text():
    from app.modules.policy.match import quote_in_clause
    from app.schemas.results import PolicyClause
    c = PolicyClause(id="c", clause_ref="2", type="sublimit", title="Room Rent Limit",
                     text="Room rent is limited to 1% of the Sum Insured per day.", document_id="d",
                     filename="p.pdf", page_number=1)
    assert quote_in_clause("room rent is   limited to 1% of the sum insured", c)
    assert not quote_in_clause("Room rent is unlimited.", c)


def test_normalizers():
    from app.modules.extraction.normalize import clean_name, parse_amount, parse_date
    assert parse_date("10/09/2025") == "2025-09-10"
    assert parse_date("10 Sep 2025") == "2025-09-10"
    assert parse_date("Sept 10, 2025") == "2025-09-10"
    assert parse_date("2025-09-10") == "2025-09-10"
    assert parse_amount("Rs. 5,00,000/-") == 500000
    assert parse_amount("₹ 2.5 lakh") == 250000
    assert clean_name("Mr. RAJESH  kumar") == "Rajesh Kumar"


def test_gemini_path_with_stub(client, docs, monkeypatch):
    """Gemini output is schema-validated, quote-verified, cached, and topped up by rules."""
    import json
    from app.core import llm
    from app.modules.extraction.extract import extract
    from app.modules.extraction.ingest import ingest
    import hashlib

    monkeypatch.setattr(get_settings(), "anthropic_api_key", "")
    monkeypatch.setattr(get_settings(), "gemini_api_key", "test-key")
    calls_made = []

    def fake(prompt, schema, file_bytes, mime):
        calls_made.append(schema.__name__)
        return json.dumps({"fields": [
            {"key": "bill_total", "value": "Rs. 85,000", "page": 1, "quote": "Total Payable: Rs. 85,000", "confidence": 0.95},
            {"key": "patient_name", "value": "Rajesh Kumaar", "page": 1, "quote": "invented text not on page", "confidence": 0.9},
            {"key": "line_item", "value": "Pharmacy | 9,000", "page": 1, "quote": "Pharmacy   9,000", "confidence": 0.9},
            {"key": "not_a_key", "value": "x", "page": 1, "quote": "x", "confidence": 1},
        ]})

    monkeypatch.setattr(llm, "_call_gemini", fake)
    p = docs["final_bill"]
    doc = ingest("d1", p.name, p, "application/pdf", hashlib.sha256(p.read_bytes()).hexdigest())
    calls = []
    fields, method = extract(doc, "final_bill", calls)
    by = {f.key: f for f in fields}
    assert method == "gemini+rules"
    assert by["bill_total"].value == 85000 and by["bill_total"].confidence == 0.95
    assert by["patient_name"].confidence <= 0.5  # quote not found on page -> forced review
    assert "not_a_key" not in by
    assert by["admission_date"].method == "rules"  # topped up
    assert [f.value for f in fields if f.key == "line_item"] == [9000]
    # Second call is served from cache.
    extract(doc, "final_bill", calls)
    assert len(calls_made) == 1 and calls[-1].cached


def test_policy_summary_handles_label_value_on_separate_lines(tmp_path):
    """Table-style schedules put the label and value on different lines (found on demo claim B)."""
    import hashlib
    import pymupdf
    from app.modules.extraction.ingest import ingest
    from app.modules.policy.index import build_clauses
    from app.modules.policy.summary import rules_summary

    pdf = tmp_path / "p.pdf"
    d = pymupdf.open()
    d.new_page().insert_text((50, 60), "POLICY SCHEDULE\nSum Insured\nRs. 5,00,000\nRoom Rent Limit\n"
                                       "1% of Sum Insured per day (Rs. 5,000 per day)\n", fontsize=10)
    d.save(pdf)
    doc = ingest("d", "p.pdf", pdf, "application/pdf", hashlib.sha256(pdf.read_bytes()).hexdigest())
    s = rules_summary(doc, build_clauses(doc))
    assert s.sum_insured and s.sum_insured.value == 500000
    assert s.room_rent_cap and s.room_rent_cap.value == 5000 and s.room_rent_cap_percent == 1


def test_claim_form_evidence_and_validation():
    ok = EvidenceRef(source="claim_form", field="claimed_amount", value=95000)
    assert ok.page_number is None
    with pytest.raises(ValueError):
        EvidenceRef(source="claim_form")  # needs a field
    with pytest.raises(ValueError):
        EvidenceRef(source="document", document_id="d")  # needs filename + page
    f = Finding(id="f", rule_id="V4", issue_type="amount_mismatch", severity="medium", kind="confirmed",
                title="t", description="d", evidence=[ok], explanation=Explanation(rule="V4"))
    assert f.evidence[0].source == "claim_form"


def test_verification_result_object_checks_passed_and_claim_form_finding(client, docs, monkeypatch):
    from app.modules.pipeline.context import VerificationResult

    def verify(ctx):
        bill = ctx.fields_for("bill_total")[0]
        f = Finding(id="x1", rule_id="V4", issue_type="amount_mismatch", severity="medium", kind="confirmed",
                    title="Bill total differs from the claimed amount", description="Totals differ.",
                    evidence=[ctx.claim_form_ref("claimed_amount"), bill.evidence], blocking=True,
                    extracted_value=str(bill.value), comparison_value=str(ctx.claim.claimed_amount),
                    explanation=Explanation(rule="V4"))
        return VerificationResult(findings=[f], checks_passed=["Admission date is not after discharge date"])

    mod = types.ModuleType("app.modules.verification.service")
    mod.run_verification = verify
    monkeypatch.setitem(sys.modules, "app.modules.verification.service", mod)
    res = _analyze(client, _claim_with_docs(client, docs))
    assert res["checks_passed"] == ["Admission date is not after discharge date"]
    act = next(a for a in res["action_plan"] if a["finding_ids"] == ["x1"])
    assert "final_bill.pdf" in " ".join(act["how"])  # picked the document evidence, not the claim form
    assert res["checklist_summary"]["referenced_but_missing"] == ["prescription"]
    assert "policy" in res["checklist_summary"]["required_present"]


def test_delete_single_document(client, docs):
    cid = _claim_with_docs(client, docs)
    first = client.get(f"/claims/{cid}/documents").json()[0]
    path_dir = get_settings().upload_dir / cid
    n_files = len(list(path_dir.iterdir()))
    assert client.delete(f"/claims/{cid}/documents/{first['id']}").status_code == 204
    assert len(client.get(f"/claims/{cid}/documents").json()) == 3
    assert len(list(path_dir.iterdir())) == n_files - 1
    assert client.delete(f"/claims/{cid}/documents/{first['id']}").status_code == 404


def test_real_engine_runs_in_pipeline(client, docs):
    """No stand-in: Person 2's engine is called through the adapter and its findings reach the plan."""
    res = _analyze(client, _claim_with_docs(client, docs))  # claimed 95,000 vs bill 85,000
    by_rule = {(f["rule_id"], f["issue_type"]): f for f in res["findings"]}
    amount = by_rule[("V4", "amount_mismatch")]
    assert amount["blocking"] and {e["source"] for e in amount["evidence"]} == {"document", "claim_form"}
    assert ("V7", "referenced_document_missing") in by_rule
    assert res["checks_passed"], "passed checks should be listed as 'appears consistent'"
    # The V7 finding and the checklist upload action describe one issue: counted once in the packet status.
    blocking = [f for f in res["findings"] if f["blocking"]]
    assert res["packet_status"] == f"INCOMPLETE - {len(blocking)} blocking items"
    act = next(a for a in res["action_plan"] if amount["id"] in a["finding_ids"])
    assert "85,000 vs 95,000" in " ".join(act["how"]) and act["blocking"]
    # fixing the claimed amount and re-checking clears that finding
    client.patch(f"/claims/{res['claim_id']}", json={"claimed_amount": 85000})
    res2 = _analyze(client, res["claim_id"])
    assert ("V4", "amount_mismatch") not in {(f["rule_id"], f["issue_type"]) for f in res2["findings"]}
