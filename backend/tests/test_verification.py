"""Tests for the verification engine (rules V1-V5, V7, V14) and the draft contract."""

import json
import re
from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from app.modules.verification import run_verification
from app.modules.verification.helpers import compare_names, parse_amount, parse_date
from app.schemas.contract import (
    Action,
    AnalysisResults,
    ClaimInput,
    DocumentInfo,
    EvidenceRef,
    ExtractedField,
    Finding,
)

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample_documents"
FIXTURE = SAMPLES / "expected_results" / "claim_b.results.fixture.json"
EXPECTED = SAMPLES / "expected_results" / "claim_b.json"


# ---------------------------------------------------------------- builders
def ef(key, value, doc="d1", fname="f.pdf", page=1, conf=0.95, confirmed=False):
    return ExtractedField(
        id=f"{key}-{doc}-{value}",
        key=key,
        value=value,
        raw_text=str(value),
        confidence=conf,
        evidence=EvidenceRef(document_id=doc, filename=fname, page_number=page, quote=str(value)),
        user_confirmed=confirmed,
    )


def doc(id, doc_type, sha=None):
    return DocumentInfo(id=id, filename=f"{id}.pdf", doc_type=doc_type, sha256=sha)


def run(fields, docs, **claim):
    return run_verification(fields, docs, ClaimInput(**claim))


def find(result, rule, issue=None):
    return [f for f in result.findings if f.rule_id == rule and (issue is None or f.issue_type == issue)]


ALL_DOCS = [
    doc("pol", "policy"), doc("fb", "final_bill"), doc("ib", "itemised_bill"),
    doc("ds", "discharge_summary"), doc("rc", "payment_receipt"),
]


# ---------------------------------------------------------------- helpers
@pytest.mark.parametrize(
    "a,b,expected",
    [
        ("Ravi Kumar Sharma", "ravi kumar sharma", "same"),
        ("Mr. Ravi Kumar Sharma", "Ravi Kumar Sharma", "same"),
        ("Ravi K Sharma", "Ravi Kumar Sharma", "variant"),
        ("Ravi K. Sharma", "Ravi Kumar Sharma", "variant"),
        ("Ravi Sharma", "Ravi Kumar Sharma", "variant"),
        ("Sharma Ravi Kumar", "Ravi Kumar Sharma", "variant"),
        ("Priya Sharma", "Pria Sharma", "variant"),
        ("Ravi Kumar Sharma", "Anita Verma", "different"),
        ("Ravi Sharma", "Raj Sharma", "different"),
        ("", "Ravi", "different"),
    ],
)
def test_compare_names(a, b, expected):
    assert compare_names(a, b) == expected


def test_parsers():
    assert parse_amount("Rs. 85,000.00") == 85000.0
    assert parse_amount(85000) == 85000.0
    assert parse_amount({"amount": 1200}) == 1200.0
    assert parse_amount("n/a") is None and parse_amount(None) is None
    assert str(parse_date("12-Aug-2026")) == "2026-08-12"
    assert str(parse_date("2026-08-12")) == "2026-08-12"
    assert parse_date("garbage") is None


# ---------------------------------------------------------------- V1
def test_v1_identical_files():
    r = run([], [doc("a", "final_bill", "x"), doc("b", "final_bill", "x")])
    (f,) = find(r, "V1", "duplicate_file")
    assert f.blocking and f.kind == "confirmed"


def test_v1_same_invoice_in_two_final_bills():
    fields = [ef("bill_number", "INV-1", "a", "a.pdf"), ef("bill_number", "inv-1 ", "b", "b.pdf")]
    r = run(fields, [doc("a", "final_bill"), doc("b", "final_bill")])
    (f,) = find(r, "V1", "duplicate_bill")
    assert f.blocking and len(f.evidence) == 2 and f.severity == "high"


def test_v1_final_and_itemised_bill_may_share_an_invoice_number():
    fields = [ef("bill_number", "INV-1", "a"), ef("bill_number", "INV-1", "b")]
    r = run(fields, [doc("a", "final_bill"), doc("b", "itemised_bill")])
    assert not find(r, "V1")


def test_v1_possible_duplicate_with_different_invoice_numbers():
    fields = []
    for d, n in (("a", "INV-1"), ("b", "INV-2")):
        fields += [ef("bill_number", n, d), ef("hospital_name", "City Care", d), ef("bill_date", "2026-08-15", d), ef("bill_total", 5000, d)]
    r = run(fields, [doc("a", "final_bill"), doc("b", "final_bill")])
    (f,) = find(r, "V1", "possible_duplicate_bill")
    assert f.kind == "possible" and not f.blocking


# ---------------------------------------------------------------- V2
def test_v2_initial_variant_is_possible_not_blocking():
    r = run([ef("patient_name", "Ravi Kumar Sharma", "a"), ef("patient_name", "Ravi K Sharma", "b")], [doc("a", "final_bill"), doc("b", "payment_receipt")])
    (f,) = find(r, "V2")
    assert f.issue_type == "name_variant" and f.kind == "possible" and f.severity == "low" and not f.blocking


def test_v2_different_person_is_confirmed_and_blocking():
    r = run([ef("patient_name", "Ravi Kumar Sharma", "a"), ef("patient_name", "Anita Verma", "b")], [doc("a", "final_bill"), doc("b", "payment_receipt")])
    (f,) = find(r, "V2")
    assert f.issue_type == "name_mismatch" and f.kind == "confirmed" and f.blocking


def test_v2_uses_claim_form_name_as_reference_and_records_it_as_evidence():
    r = run([ef("patient_name", "Anita Verma", "a")], [doc("a", "final_bill")], patient_name="Ravi Kumar Sharma")
    (f,) = find(r, "V2")
    assert {e.source for e in f.evidence} == {"document", "claim_form"}


def test_v2_consistent_names_pass():
    r = run([ef("patient_name", "Ravi Kumar Sharma", "a"), ef("patient_name", "Mr. Ravi Kumar Sharma", "b")], ALL_DOCS)
    assert not find(r, "V2") and any("Patient name is consistent" in t for t in r.checks_passed)


# ---------------------------------------------------------------- V3
def test_v3_policy_number_mismatch_against_policy_document():
    fields = [ef("policy_number", "SSH-1", "pol"), ef("policy_number", "SSH-2", "fb")]
    r = run(fields, ALL_DOCS)
    (f,) = find(r, "V3", "policy_number_mismatch")
    assert f.blocking and f.comparison_value == "SSH-1"


def test_v3_member_id_mismatch_and_formatting_tolerance():
    r = run([ef("member_id", "M-889201", "pol"), ef("member_id", "m-889201 ", "fb"), ef("member_id", "M-000000", "ds")], ALL_DOCS)
    assert [f.issue_type for f in find(r, "V3")] == ["member_id_mismatch"]


def test_v3_matching_ids_pass():
    r = run([ef("policy_number", "SSH-1", "pol"), ef("policy_number", "ssh-1", "fb")], ALL_DOCS)
    assert not find(r, "V3") and any("Policy number and member ID agree" in t for t in r.checks_passed)


# ---------------------------------------------------------------- V4
def test_v4_claimed_above_bill_is_confirmed_and_blocking():
    r = run([ef("bill_total", 85000, "fb")], ALL_DOCS, claimed_amount=95000)
    (f,) = find(r, "V4", "amount_mismatch")
    assert f.kind == "confirmed" and f.blocking and f.severity == "medium"
    assert {e.source for e in f.evidence} == {"document", "claim_form"}
    assert f.explanation.inputs == {"bill_total": 85000.0, "claimed_amount": 95000.0}


def test_v4_claimed_below_bill_is_only_possible():
    r = run([ef("bill_total", 85000, "fb")], ALL_DOCS, claimed_amount=80000)
    (f,) = find(r, "V4", "amount_mismatch")
    assert f.kind == "possible" and not f.blocking


def test_v4_equal_amounts_pass_and_unknown_claim_is_skipped():
    r = run([ef("bill_total", "Rs. 85,000.00", "fb")], ALL_DOCS, claimed_amount=85000)
    assert not find(r, "V4") and any("matches the claimed amount" in t for t in r.checks_passed)
    assert not find(run([ef("bill_total", 85000, "fb")], ALL_DOCS), "V4")


def test_v4_line_items_must_add_up():
    items = [ef("line_item", {"description": "a", "amount": 100}, "ib"), ef("line_item", {"description": "b", "amount": 250}, "ib")]
    r = run(items + [ef("bill_total", 400, "fb")], ALL_DOCS)
    (f,) = find(r, "V4", "line_items_mismatch")
    assert f.blocking and f.extracted_value == "350"
    ok = run(items + [ef("bill_total", 350, "fb")], ALL_DOCS)
    assert not find(ok, "V4") and any("Line items add up" in t for t in ok.checks_passed)


def test_v4_receipts_vs_bill():
    r = run([ef("bill_total", 1000, "fb"), ef("receipt_amount", 600, "rc")], ALL_DOCS)
    (f,) = find(r, "V4", "receipt_amount_mismatch")
    assert f.kind == "possible" and not f.blocking
    ok = run([ef("bill_total", 1000, "fb"), ef("receipt_amount", 400, "rc"), ef("receipt_amount", 600, "rc2")], ALL_DOCS)
    assert not find(ok, "V4")


# ---------------------------------------------------------------- V5
def test_v5_admission_after_discharge():
    r = run([ef("admission_date", "2026-08-15", "ds"), ef("discharge_date", "2026-08-12", "ds")], ALL_DOCS)
    (f,) = find(r, "V5", "admission_after_discharge")
    assert f.blocking and f.kind == "confirmed"


def test_v5_treatment_outside_policy_period():
    fields = [ef("admission_date", "2027-04-02", "ds"), ef("discharge_date", "2027-04-05", "ds"),
              ef("policy_start", "2026-04-01", "pol"), ef("policy_end", "2027-03-31", "pol")]
    (f,) = find(run(fields, ALL_DOCS), "V5", "treatment_outside_policy_period")
    assert f.blocking


def test_v5_dates_that_disagree_between_documents():
    fields = [ef("admission_date", "2026-08-12", "ds"), ef("admission_date", "2026-08-13", "fb")]
    (f,) = find(run(fields, ALL_DOCS), "V5", "admission_date_conflict")
    assert f.blocking and len(f.evidence) == 2


def test_v5_bill_dated_before_discharge_is_a_soft_flag():
    fields = [ef("admission_date", "2026-08-12", "ds"), ef("discharge_date", "2026-08-15", "ds"), ef("bill_date", "2026-08-14", "fb")]
    (f,) = find(run(fields, ALL_DOCS), "V5", "bill_dated_before_discharge")
    assert f.kind == "possible" and not f.blocking


def test_v5_clean_dates_pass():
    fields = [ef("admission_date", "12-Aug-2026", "ds"), ef("discharge_date", "2026-08-15", "ds"), ef("bill_date", "2026-08-15", "fb"),
              ef("policy_start", "2026-04-01", "pol"), ef("policy_end", "2027-03-31", "pol")]
    r = run(fields, ALL_DOCS)
    assert not find(r, "V5") and len([t for t in r.checks_passed if "date" in t.lower() or "policy period" in t.lower()]) == 2


# ---------------------------------------------------------------- V7
def test_v7_missing_required_documents_follow_claim_type():
    docs = [doc("pol", "policy"), doc("fb", "final_bill"), doc("ds", "discharge_summary"), doc("ib", "itemised_bill")]
    r = run([], docs, claim_type="reimbursement")
    (f,) = find(r, "V7", "missing_required_document")
    assert f.blocking and f.evidence[0].source == "checklist" and f.evidence[0].field == "payment_receipt"
    assert not find(run([], docs, claim_type="cashless"), "V7")


def test_v7_referenced_but_missing_document():
    r = run([ef("referenced_document", "prescription no. RX-7781", "ds", "ds.pdf")], ALL_DOCS)
    (f,) = find(r, "V7", "referenced_document_missing")
    assert f.blocking and "prescription" in f.title and f.evidence[0].filename == "ds.pdf"


def test_v7_reference_satisfied_or_other_type():
    f = [ef("referenced_document", "prescription no. RX-7781", "ds")]
    assert not find(run(f, ALL_DOCS + [doc("rx", "prescription")]), "V7", "referenced_document_missing")
    (g,) = find(run([ef("referenced_document", "see ultrasound report", "ds")], ALL_DOCS), "V7", "referenced_document_missing")
    assert "diagnostic report" in g.title


# ---------------------------------------------------------------- V14
def test_v14_low_confidence_on_critical_fields_only():
    fields = [ef("bill_total", 100, "fb", conf=0.5), ef("diagnosis", "x", "ds", conf=0.4), ef("admission_date", "2026-08-12", "ds", conf=0.6, confirmed=True)]
    r = run(fields, ALL_DOCS)
    got = find(r, "V14")
    assert [f.extracted_value for f in got] == ["100"] and got[0].severity == "low" and not got[0].blocking


# ---------------------------------------------------------------- engine + contract invariants
def test_findings_sorted_blocking_first():
    r = run([ef("bill_total", 85000, "fb"), ef("patient_name", "Ravi K Sharma", "a"), ef("patient_name", "Ravi Kumar Sharma", "b")], ALL_DOCS, claimed_amount=95000)
    flags = [f.blocking for f in r.findings]
    assert flags == sorted(flags, reverse=True)


def test_finding_without_evidence_is_rejected_I1():
    base = dict(id="x", rule_id="V1", issue_type="t", severity="low", kind="possible", title="t", description="d",
                explanation={"rule": "r", "why_it_matters": "w"})
    with pytest.raises(ValidationError):
        Finding(**base, evidence=[])


def test_action_without_finding_is_rejected_I3():
    with pytest.raises(ValidationError):
        Action(id="a", title="t", why="w", owner="user", group="upload", finding_ids=[])


@pytest.mark.parametrize(
    "kwargs",
    [dict(source="document", document_id="d", quote="q"),  # no page
     dict(source="document", document_id="d", page_number=1),  # no quote or value
     dict(source="claim_form"),  # no field
     dict(source="document", document_id="d", page_number=1, quote="q", bbox=[0, 0, 2, 1])],
)
def test_bad_evidence_is_rejected(kwargs):
    with pytest.raises(ValidationError):
        EvidenceRef(**kwargs)


# ---------------------------------------------------------------- claim B end to end (real fixture + real PDFs)
@pytest.fixture(scope="module")
def claim_b():
    if not FIXTURE.exists():
        pytest.skip("claim B fixture not generated")
    results = AnalysisResults.model_validate_json(FIXTURE.read_text())
    files = {p.name: p for p in SAMPLES.rglob("*.pdf")}
    import hashlib
    docs = [
        DocumentInfo(id=d.id, filename=d.filename, doc_type=d.doc_type,
                     sha256=hashlib.sha256(files[d.filename].read_bytes()).hexdigest())
        for d in results.documents
    ]
    expected = json.loads(EXPECTED.read_text())
    return results, docs, expected, files


CLAIM_B = dict(claim_type="reimbursement", claimed_amount=95000, patient_name="Ravi Kumar Sharma")
IMPLEMENTED = {"V1", "V2", "V3", "V4", "V5", "V7", "V14"}


def test_fixture_matches_the_contract(claim_b):
    results, *_ = claim_b
    assert results.readiness_status == "needs_attention"
    assert sum(f.blocking for f in results.findings) == 3
    assert all(a.finding_ids for a in results.action_plan)


def test_claim_b_findings_match_ground_truth(claim_b):
    results, docs, expected, _ = claim_b
    r = run_verification(results.fields, docs, ClaimInput(**CLAIM_B))
    got = {(f.rule_id, f.issue_type, f.kind.value, f.severity.value, f.blocking) for f in r.findings}
    want = {(f["rule_id"], f["issue_type"], f["kind"], f["severity"], f["blocking"])
            for f in expected["expected_findings"] if f["rule_id"] in IMPLEMENTED}
    assert got == want, f"unexpected: {got - want}; missing: {want - got}"
    assert sum(f.blocking for f in r.findings) == 3


def test_claim_b_evidence_quotes_really_are_on_the_pdf_page(claim_b):
    """Invariant I1/I2 spirit: every document quote a finding cites exists on the cited page."""
    results, docs, _, files = claim_b
    r = run_verification(results.fields, docs, ClaimInput(**CLAIM_B))
    checked = 0
    for f in r.findings:
        for e in f.evidence:
            if e.source != "document":
                continue
            with pymupdf.open(files[e.filename]) as d:
                text = re.sub(r"\s+", " ", d[e.page_number - 1].get_text())
            assert re.sub(r"\s+", " ", e.quote) in text, (f.id, e.filename, e.quote)
            checked += 1
    assert checked >= 5


def test_claim_b_checks_that_should_pass_do_pass(claim_b):
    results, docs, _, _ = claim_b
    texts = " | ".join(run_verification(results.fields, docs, ClaimInput(**CLAIM_B)).checks_passed)
    for needle in ("Admission date is not after", "inside the policy period", "Policy number and member ID agree",
                   "Line items add up", "Receipt amount equals", "All required documents"):
        assert needle in texts, needle


def test_claim_b_demo_fix_sequence_clears_every_blocking_item(claim_b):
    """The re-check story: fix the amount, remove the duplicate, upload the prescription."""
    results, docs, _, _ = claim_b
    fields = [f for f in results.fields if f.evidence.document_id != "doc-final-bill-copy"]
    docs = [d for d in docs if d.id != "doc-final-bill-copy"] + [DocumentInfo(id="doc-rx", filename="rx.pdf", doc_type="prescription", sha256="rx")]
    r = run_verification(fields, docs, ClaimInput(**{**CLAIM_B, "claimed_amount": 85000}))
    assert not [f for f in r.findings if f.blocking]
    assert [f.issue_type for f in r.findings] == ["name_variant"]
