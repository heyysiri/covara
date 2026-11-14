"""Tests for the verification engine (rules V1-V5, V7, V14) and the draft contract."""

import json
import re
from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from app.modules.verification import PolicyFacts, WaitingFact, find_associated_expenses, parse_associated_expenses, run_verification
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
def ef(key, value, doc="d1", fname="f.pdf", page=1, conf=0.95, confirmed=False, raw=None):
    return ExtractedField(
        id=f"{key}-{doc}-{value}",
        key=key,
        value=value,
        raw_text=raw if raw is not None else str(value),
        confidence=conf,
        evidence=EvidenceRef(document_id=doc, filename=fname, page_number=page, quote=str(value)),
        user_confirmed=confirmed,
    )


def doc(id, doc_type, sha=None):
    return DocumentInfo(id=id, filename=f"{id}.pdf", doc_type=doc_type, sha256=sha)


def run(fields, docs, policy=None, **claim):
    return run_verification(fields, docs, ClaimInput(**claim), policy)


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
    assert "diagnostic" in g.title and "lab report" in g.title


# ---------------------------------------------------------------- V14
def test_v14_low_confidence_on_critical_fields_only():
    fields = [ef("bill_total", 100, "fb", conf=0.5), ef("diagnosis", "x", "ds", conf=0.4), ef("admission_date", "2026-08-12", "ds", conf=0.6, confirmed=True)]
    r = run(fields, ALL_DOCS)
    got = find(r, "V14")
    assert [f.extracted_value for f in got] == ["100"] and got[0].severity == "low" and not got[0].blocking


# ---------------------------------------------------------------- policy facts helpers (V10 / V11)
def pev(page=4, quote="Room rent is payable up to 1% of the Sum Insured per day"):
    return EvidenceRef(document_id="pol", filename="pol.pdf", page_number=page, quote=quote)


DEFINITION = ("1.4 Associated Medical Expenses means nursing charges, surgeon and anaesthetist fees, operation theatre charges and "
              "surgical consumables incurred during the hospitalisation. Medicines, diagnostics and registration charges are not "
              "Associated Medical Expenses.")


def defn(text=DEFINITION):
    return parse_associated_expenses(text, "pol", "pol.pdf", 2)


def policy(cap=5000.0, waits=(), associated="default"):
    return PolicyFacts(room_rent_cap_per_day=cap, room_rent_cap_evidence=pev(), waiting_periods=list(waits),
                       associated_expenses=defn() if associated == "default" else associated)


def _facts(results):
    """PolicyFacts from the claim B fixture's policy summary (same shape the real pipeline returns)."""
    ps = results.policy_summary
    ev = EvidenceRef.model_validate
    return PolicyFacts(
        room_rent_cap_per_day=ps["room_rent_cap"]["value"],
        room_rent_cap_evidence=ev(ps["room_rent_cap"]["evidence"]),
        waiting_periods=[WaitingFact(w["name"], w["days"], ev(w["evidence"])) for w in ps["waiting_periods"]],
        associated_expenses=find_associated_expenses(results.clauses),
    )


BILL_LINES = [
    ("Room rent - private single room", 22500), ("Nursing charges", 3600), ("Surgeon fee", 18000),
    ("Anaesthetist fee", 6000), ("Operation theatre charges", 12000), ("Laparoscopic surgical consumables", 9500),
    ("Medicines and pharmacy", 7400), ("Diagnostics (lab and ultrasound)", 5000), ("Registration and miscellaneous", 1000),
]


def line_items(lines=BILL_LINES):
    return [ef("line_item", amt, "ib", raw=desc) for desc, amt in lines]


# ---------------------------------------------------------------- V10
def test_v10_exposure_matches_a_hand_calculation():
    # excess room rent: (7500 - 5000) x 3 days = 7500
    # associated charges: 3600 + 18000 + 6000 + 12000 + 9500 = 49100, reduced by (1 - 5000/7500) = 16366.67
    r = run(line_items() + [ef("room_rent_charged_per_day", 7500, "ib")], ALL_DOCS, policy())
    (f,) = find(r, "V10", "room_rent_above_cap")
    assert f.exposure_amount == 23867
    assert f.kind == "possible" and f.severity == "medium" and not f.blocking
    i = f.explanation.inputs
    assert i["days"] == 3 and i["excess_room_rent"] == 7500 and i["associated_charges"] == 49100
    assert i["eligible_to_actual_ratio"] == 0.6667 and "estimate" in i["assumption"].lower() and i["definition_found"]
    assert [e.filename for e in f.evidence] == ["f.pdf", "pol.pdf", "pol.pdf"]  # the bill, the cap, and the policy's definition
    assert "not a decision" in f.description


def test_v10_medicines_diagnostics_and_registration_are_not_associated():
    r = run(line_items() + [ef("room_rent_charged_per_day", 7500, "ib")], ALL_DOCS, policy())
    items = find(r, "V10")[0].explanation.inputs["associated_items"]
    assert "Nursing charges" in items and not any("Medicines" in d or "Diagnostics" in d or "Registration" in d for d in items)


def test_v10_within_the_limit_passes():
    r = run(line_items() + [ef("room_rent_charged_per_day", 5000, "ib")], ALL_DOCS, policy())
    assert not find(r, "V10") and any("within the policy limit" in t for t in r.checks_passed)


def test_v10_days_come_from_the_dates_when_there_is_no_room_line():
    fields = [ef("room_rent_charged_per_day", 7500, "ib"), ef("admission_date", "2026-08-12", "ds"), ef("discharge_date", "2026-08-15", "ds")]
    (f,) = find(run(fields, ALL_DOCS, policy()), "V10")
    assert f.explanation.inputs["days"] == 3 and f.exposure_amount == 7500  # only the excess room rent


def test_v10_without_days_flags_but_gives_no_amount():
    (f,) = find(run([ef("room_rent_charged_per_day", 7500, "ib")], ALL_DOCS, policy()), "V10")
    assert f.exposure_amount is None and "estimate" not in f.description


def test_v10_is_skipped_without_the_inputs():
    rate = [ef("room_rent_charged_per_day", 7500, "ib")]
    assert not find(run(rate, ALL_DOCS), "V10")  # no policy facts
    assert not find(run(rate, ALL_DOCS, policy(cap=None)), "V10")  # cap unknown
    assert not find(run([], ALL_DOCS, policy()), "V10")  # no room rate on the bill


# ---------------------------------------------------------------- V11
def wp(name, days, quote):
    return WaitingFact(name, days, pev(5, quote))


INITIAL = wp("Initial waiting period", 30, "Claims arising within 30 days from the first policy inception date are not payable")
SPECIFIED = wp("Specified conditions", 730, "Cataract, hernia, hysterectomy and joint replacement are covered only after 24 months")
PREEXISTING = wp("Pre-existing diseases", 1094, "Pre-existing diseases are covered only after 36 months of continuous coverage")


def waiting_inputs(start="2026-08-01", admission="2026-08-12", diagnosis="Acute appendicitis", **extra):
    fields = [ef("policy_start", start, "pol"), ef("admission_date", admission, "ds"), ef("diagnosis", diagnosis, "ds")]
    return fields + [ef(k, v, "pol" if "policy" in k else "ds") for k, v in extra.items()]


def test_v11_initial_waiting_period_is_flagged_as_possible_not_blocking():
    r = run(waiting_inputs(), ALL_DOCS, policy(waits=[INITIAL]))
    (f,) = find(r, "V11", "waiting_period_conflict")
    assert f.kind == "possible" and f.severity == "high" and not f.blocking
    assert f.extracted_value == "11 days" and f.comparison_value == "30 days" and len(f.evidence) == 3
    assert "first-enrolment date was not found" in f.description  # honest about the date used


def test_v11_prefers_the_first_enrolment_date_when_it_is_known():
    r = run(waiting_inputs(policy_inception="2024-04-01"), ALL_DOCS, policy(waits=[INITIAL]))
    assert not find(r, "V11") and any("first enrolment" in t for t in r.checks_passed)


def test_v11_outside_the_window_passes():
    r = run(waiting_inputs(start="2026-04-01"), ALL_DOCS, policy(waits=[INITIAL]))
    assert not find(r, "V11") and any("No waiting-period conflict" in t for t in r.checks_passed)


def test_v11_specified_condition_only_when_the_policy_names_it():
    hernia = run(waiting_inputs(start="2025-08-12", diagnosis="Inguinal hernia"), ALL_DOCS, policy(waits=[SPECIFIED]))
    (f,) = find(hernia, "V11")
    assert f.explanation.inputs["waiting_period"] == "Specified conditions" and f.comparison_value == "730 days"
    other = run(waiting_inputs(start="2025-08-12", diagnosis="Acute appendicitis"), ALL_DOCS, policy(waits=[SPECIFIED]))
    assert not find(other, "V11")


def test_v11_pre_existing_conditions_are_never_guessed_from_documents():
    assert not find(run(waiting_inputs(start="2026-07-01", diagnosis="Diabetes"), ALL_DOCS, policy(waits=[PREEXISTING])), "V11")


def test_v11_uses_the_diagnosis_date_when_present_and_reports_the_longest_period():
    fields = waiting_inputs(start="2026-01-01", admission="2026-09-01", diagnosis="Hernia", diagnosis_date="2026-01-20")
    (f,) = find(run(fields, ALL_DOCS, policy(waits=[INITIAL, SPECIFIED])), "V11")
    assert f.explanation.inputs["treatment_date"] == "2026-01-20" and f.explanation.inputs["waiting_days"] == 730
    assert f.explanation.inputs["other_waiting_periods_matched"] == ["Initial waiting period"]


def test_v11_is_skipped_without_the_inputs():
    assert not find(run(waiting_inputs(), ALL_DOCS), "V11")
    assert not find(run(waiting_inputs(), ALL_DOCS, policy()), "V11")  # policy lists no waiting periods
    assert not find(run([ef("diagnosis", "x", "ds")], ALL_DOCS, policy(waits=[INITIAL])), "V11")  # no dates


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
IMPLEMENTED = {"V1", "V2", "V3", "V4", "V5", "V7", "V14", "V10", "V11"}


def test_fixture_matches_the_contract(claim_b):
    results, *_ = claim_b
    assert results.readiness_status == "needs_attention"
    assert sum(f.blocking for f in results.findings) == 3
    assert all(a.finding_ids for a in results.action_plan)


def test_claim_b_findings_match_ground_truth(claim_b):
    results, docs, expected, _ = claim_b
    r = run_verification(results.fields, docs, ClaimInput(**CLAIM_B), _facts(results))
    got = {(f.rule_id, f.issue_type, f.kind.value, f.severity.value, f.blocking) for f in r.findings}
    want = {(f["rule_id"], f["issue_type"], f["kind"], f["severity"], f["blocking"])
            for f in expected["expected_findings"] if f["rule_id"] in IMPLEMENTED}
    assert got == want, f"unexpected: {got - want}; missing: {want - got}"
    assert sum(f.blocking for f in r.findings) == 3
    (v10,) = [f for f in r.findings if f.rule_id == "V10"]
    assert v10.exposure_amount == next(f["exposure_amount"] for f in expected["expected_findings"] if f["rule_id"] == "V10")


def test_claim_b_evidence_quotes_really_are_on_the_pdf_page(claim_b):
    """Invariant I1/I2 spirit: every document quote a finding cites exists on the cited page."""
    results, docs, _, files = claim_b
    r = run_verification(results.fields, docs, ClaimInput(**CLAIM_B), _facts(results))
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
    texts = " | ".join(run_verification(results.fields, docs, ClaimInput(**CLAIM_B), _facts(results)).checks_passed)
    for needle in ("Admission date is not after", "inside the policy period", "Policy number and member ID agree",
                   "Line items add up", "Receipt amount equals", "All required documents", "No waiting-period conflict"):
        assert needle in texts, needle


def test_claim_b_demo_fix_sequence_clears_every_blocking_item(claim_b):
    """The re-check story: fix the amount, remove the duplicate, upload the prescription."""
    results, docs, _, _ = claim_b
    fields = [f for f in results.fields if f.evidence.document_id != "doc-final-bill-copy"]
    docs = [d for d in docs if d.id != "doc-final-bill-copy"] + [DocumentInfo(id="doc-rx", filename="rx.pdf", doc_type="prescription", sha256="rx")]
    r = run_verification(fields, docs, ClaimInput(**{**CLAIM_B, "claimed_amount": 85000}), _facts(results))
    assert not [f for f in r.findings if f.blocking]
    assert [f.issue_type for f in r.findings] == ["room_rent_above_cap", "name_variant"]  # both just to review


# ---------------------------------------------------------------- nothing is tuned to one policy or one claim
def test_associated_expenses_are_read_from_whatever_words_the_policy_uses():
    other = parse_associated_expenses(
        "Associated expenses include doctor consultation fees, nursing and OT charges. "
        "Implants and pharmacy are excluded from associated expenses.", "p", "other.pdf", 3)
    assert other is not None
    assert other.classify("Doctor consultation fee") == "associated"
    assert other.classify("Nursing charges") == "associated" and other.classify("OT Charges") == "associated"
    assert other.classify("Cardiac stent implant") == "excluded" and other.classify("Pharmacy") == "excluded"
    assert other.classify("MRI scan") is None  # the policy says nothing about it, so it is not counted
    assert other.evidence.page_number == 3 and other.quote in other.evidence.quote


def test_no_definition_in_the_policy_means_none_is_assumed():
    assert parse_associated_expenses("5.1 Initial waiting period of 30 days applies.", "p", "x.pdf", 1) is None
    assert find_associated_expenses([]) is None


def test_exclusion_wins_over_inclusion():
    d = parse_associated_expenses("Associated expenses means nursing charges and pharmacy. Pharmacy is not an associated expense.", "p", "x.pdf", 1)
    assert d.classify("Pharmacy") == "excluded" and d.classify("Nursing") == "associated"


def test_v10_without_a_definition_estimates_only_the_excess_room_rent():
    r = run(line_items() + [ef("room_rent_charged_per_day", 7500, "ib")], ALL_DOCS, policy(associated=None))
    (f,) = find(r, "V10")
    assert f.exposure_amount == 7500 and f.explanation.inputs["definition_found"] is False
    assert f.explanation.inputs["associated_charges"] == 0 and "not found" in f.explanation.inputs["assumption"]
    assert len(f.evidence) == 2  # no definition clause was used, so none is cited


def test_v10_estimate_follows_the_policys_own_wording():
    """Change the policy's definition and the estimate changes: it is not a fixed list of bill words."""
    only_surgeon = defn("Associated Medical Expenses means surgeon fees.")
    r = run(line_items() + [ef("room_rent_charged_per_day", 7500, "ib")], ALL_DOCS, policy(associated=only_surgeon))
    (f,) = find(r, "V10")
    assert f.explanation.inputs["associated_items"] == ["Surgeon fee"]
    assert f.exposure_amount == round(7500 + 18000 * (1 - 5000 / 7500))  # 13,500


def test_v10_finds_the_room_line_from_the_evidence_quote_not_from_a_word_list():
    lines = [("Deluxe suite accommodation", 30000), ("Nursing charges", 3600)]
    rate = ef("room_rent_charged_per_day", 10000, "ib")
    rate.evidence.quote = "Deluxe suite accommodation 3 10,000 30,000"
    (f,) = find(run(line_items(lines) + [rate], ALL_DOCS, policy()), "V10")
    assert f.explanation.inputs["days"] == 3 and f.explanation.inputs["associated_items"] == ["Nursing charges"]


def test_v10_does_not_guess_the_room_line_when_two_lines_fit():
    lines = [("Stay A", 20000), ("Stay B", 30000)]  # both are whole days at 10,000 a day
    rate = ef("room_rent_charged_per_day", 10000, "ib")
    rate.evidence.quote = "10,000 per day"
    (f,) = find(run(line_items(lines) + [rate] + [ef("admission_date", "2026-08-12", "ds"), ef("discharge_date", "2026-08-14", "ds")],
                    ALL_DOCS, policy()), "V10")
    assert f.explanation.inputs["days"] == 2  # fell back to the dates instead of picking a line


def test_thresholds_come_from_the_config_not_the_rules():
    from app.modules.verification import VerificationConfig

    fields = [ef("bill_total", 85000, "fb")]
    assert find(run(fields, ALL_DOCS, claimed_amount=95000), "V4", "amount_mismatch")
    loose = run_verification(fields, ALL_DOCS, ClaimInput(claimed_amount=95000), config=VerificationConfig(amount_tolerance_inr=20000))
    assert not find(loose, "V4", "amount_mismatch")
    strict = run_verification([ef("bill_total", 100, "fb", conf=0.8)], ALL_DOCS, config=VerificationConfig(low_confidence=0.9))
    assert find(strict, "V14") and not find(run([ef("bill_total", 100, "fb", conf=0.8)], ALL_DOCS), "V14")


def test_required_documents_can_be_supplied_by_the_checklist():
    only_policy = [doc("pol", "policy")]
    assert find(run([], only_policy), "V7", "missing_required_document")  # default = the checklist rules for the claim type
    assert not find(run_verification([], only_policy, ClaimInput(), required_documents=["policy"]), "V7")


def test_critical_fields_and_review_threshold_are_the_pipelines_shared_values():
    from app.modules.verification import DEFAULT_CONFIG
    from app.schemas.results import CRITICAL_KEYS, REVIEW_THRESHOLD

    assert DEFAULT_CONFIG.critical_keys == frozenset(CRITICAL_KEYS) and DEFAULT_CONFIG.low_confidence == REVIEW_THRESHOLD


# ---------------------------------------------------------------- regression: a misread room rate must not raise V10
DAYCARE = [("Room rent - day-care ward", 3500), ("Nursing charges", 800), ("Surgeon fee", 22000), ("Medicines", 3200)]


def test_v10_prefers_the_itemised_rooms_own_rate_over_a_combined_summary_line():
    """Seen in a real run: the final bill's 'Room rent and nursing 4,300' was read as a daily room rate."""
    fields = line_items(DAYCARE) + [ef("room_rent_charged_per_day", 4300, "fb"), ef("room_rent_charged_per_day", 3500, "ib")]
    assert not find(run(fields, ALL_DOCS, policy(cap=4000.0)), "V10")  # 3,500 is within the 4,000 limit


def test_v10_is_silent_when_the_only_rate_matches_no_bill_line():
    fields = line_items(DAYCARE) + [ef("room_rent_charged_per_day", 4300, "fb")]
    assert not find(run(fields, ALL_DOCS, policy(cap=4000.0)), "V10")


def test_v10_skips_a_room_line_combined_with_another_charge():
    fields = line_items([("Room rent and nursing", 4300), ("Surgeon fee", 22000)]) + [ef("room_rent_charged_per_day", 4300, "ib", raw="Room rent and nursing")]
    assert not find(run(fields, ALL_DOCS, policy(cap=4000.0)), "V10")  # nursing is an associated charge in this policy


def test_v10_still_fires_for_a_genuine_excess():
    fields = line_items([("Room rent - private room", 15000), ("Nursing charges", 3000)]) + [ef("room_rent_charged_per_day", 5000, "ib")]
    (f,) = find(run(fields, ALL_DOCS, policy(cap=4000.0)), "V10")
    assert f.explanation.inputs["days"] == 3 and f.exposure_amount is not None
