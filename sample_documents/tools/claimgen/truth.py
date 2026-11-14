"""Ground truth derived from a Scenario, verified against the PDFs that were actually generated.

Expected fields come from where each fact is printed. Expected findings come from the defects the scenario
plants (a bill that differs from the claim, a duplicate file, a missing prescription, a room rate above the policy
limit, a differently spelled name, a treatment inside a waiting period). Every evidence quote is checked against the
page it names, the same grounding rule the product enforces.
"""

from __future__ import annotations

import re
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pymupdf

from .scenario import Scenario, fmt_date, human_list, inr, rs


@dataclass
class Paths:
    """Where each generated file lives, relative to sample_documents/."""

    policy: str
    final: str
    copy: str
    itemised: str
    discharge: str
    receipt: str
    rx: str

    @classmethod
    def for_(cls, s: Scenario) -> "Paths":
        k = s.key
        rx_dir = "medical" if s.rx_uploaded else "medical/_held_back"
        rx_ext = "jpg" if s.handwritten_rx else "pdf"
        return cls(f"policy/claim_{k}_policy.pdf", f"medical/claim_{k}_final_bill.pdf", f"medical/claim_{k}_final_bill_copy.pdf",
                   f"medical/claim_{k}_itemised_bill.pdf", f"medical/claim_{k}_discharge_summary.pdf",
                   f"medical/claim_{k}_payment_receipt.pdf", f"{rx_dir}/claim_{k}_prescription_{s.rx_no}.{rx_ext}")


def ev(file: str, page: int, quote: str) -> dict:
    return {"file": file, "page": page, "quote": quote}


def _field(key, value, raw, file, page, quote) -> dict:
    return {"key": key, "value": value, "raw_text": raw, **ev(file, page, quote)}


def exposure(s: Scenario) -> dict | None:
    """Room-rent proportionate-deduction estimate under this scenario's own clause, if the room rate exceeds the cap."""
    room = s.room
    if room is None or room.rate <= s.room_cap:
        return None
    excess = (room.rate - s.room_cap) * room.qty
    associated = sum(l.amount for l in s.lines[1:] if l.associated)
    ratio = s.room_cap / room.rate
    reduction = associated * (1 - ratio)
    return {"days": room.qty, "excess_room_rent": excess, "associated_medical_expenses": associated,
            "eligible_to_actual_ratio": round(ratio, 4), "proportionate_reduction": round(reduction, 2),
            "exposure": round(excess + reduction),
            "note": "Informational estimate under this synthetic policy's own wording; not a coverage decision."}


def waiting_conflict(s: Scenario) -> dict | None:
    """The longest waiting period that the treatment date falls inside, per the scenario's policy wording."""
    elapsed = (s.admission - s.inception).days  # type: ignore[operator]
    text = f"{s.diagnosis} {s.procedure}".lower()
    hits = []
    if elapsed < s.initial_wait_days:
        hits.append(("Initial waiting period", s.initial_wait_days, f"Claims arising within {s.initial_wait_days} days from the first policy inception date are not payable", "5.1"))
    months_days = round(s.specified_months * 365 / 12)
    if elapsed < months_days and any(c.lower() in text for c in s.specified_conditions):
        hits.append(("Specified conditions", months_days, f"{human_list(s.specified_conditions)} are covered only after {s.specified_months} months of continuous coverage", "5.3"))
    if not hits:
        return None
    top = max(hits, key=lambda h: h[1])
    return {"elapsed_days": elapsed, "name": top[0], "days": top[1], "quote": top[2], "clause_ref": top[3], "all": [h[0] for h in hits]}


def expected_fields(s: Scenario, p: Paths) -> list[dict]:
    pct = f"{s.room_cap_pct:g}%"
    f: list[dict] = [
        _field("policy_number", s.policy_no, s.policy_no, p.policy, 1, s.policy_no),
        _field("member_id", s.member_id, s.member_id, p.policy, 1, s.member_id),
        _field("insurer", s.insurer, s.insurer, p.policy, 1, s.insurer),
        _field("policyholder_name", s.patient, f"{s.salutation} {s.patient}", p.policy, 1, f"{s.salutation} {s.patient}"),
        _field("policy_start", s.period_start.isoformat(), fmt_date(s.period_start), p.policy, 1, f"{fmt_date(s.period_start)} to {fmt_date(s.period_end)}"),
        _field("policy_inception", s.inception.isoformat(), fmt_date(s.inception), p.policy, 1, fmt_date(s.inception)),
        _field("policy_end", s.period_end.isoformat(), fmt_date(s.period_end), p.policy, 1, f"{fmt_date(s.period_start)} to {fmt_date(s.period_end)}"),
        _field("sum_insured", s.sum_insured, f"Rs. {inr(s.sum_insured)}", p.policy, 1, f"Rs. {inr(s.sum_insured)}"),
        _field("room_rent_cap", s.room_cap, f"Rs. {inr(s.room_cap)} per day", p.policy, 1, f"(Rs. {inr(s.room_cap)} per day)"),
        _field("waiting_period", f"initial {s.initial_wait_days} days; pre-existing {s.preexisting_months} months; specified conditions {s.specified_months} months",
               "Section 5", p.policy, 5, f"Claims arising within {s.initial_wait_days} days from the first policy inception date are not payable"),
        _field("patient_name", s.patient, s.patient, p.final, 1, s.patient),
        _field("hospital_name", s.hospital, s.hospital, p.final, 1, s.hospital),
        _field("bill_number", s.invoice_no, s.invoice_no, p.final, 1, s.invoice_no),
        _field("bill_date", s.bill_date.isoformat(), fmt_date(s.bill_date), p.final, 1, fmt_date(s.bill_date)),
        _field("bill_total", s.total, rs(s.total), p.final, 1, f"TOTAL PAYABLE: {rs(s.total)}"),
        _field("policy_number", s.policy_no, s.policy_no, p.final, 1, s.policy_no),
        _field("member_id", s.member_id, s.member_id, p.final, 1, s.member_id),
    ]
    if s.duplicate_bill:
        f += [_field("bill_number", s.invoice_no, s.invoice_no, p.copy, 1, s.invoice_no),
              _field("bill_date", s.bill_date.isoformat(), fmt_date(s.bill_date), p.copy, 1, fmt_date(s.bill_date)),
              _field("bill_total", s.total, rs(s.total), p.copy, 1, f"TOTAL PAYABLE: {rs(s.total)}"),
              _field("patient_name", s.patient, s.patient, p.copy, 1, s.patient),
              _field("hospital_name", s.hospital, s.hospital, p.copy, 1, s.hospital)]
    f.append(_field("bill_number", s.invoice_no, s.invoice_no, p.itemised, 1, s.invoice_no))
    proc = f"{s.procedure} performed on {fmt_date(s.surgery)}" if s.surgery else s.procedure
    f += [_field("admission_date", s.admission.isoformat(), fmt_date(s.admission), p.discharge, 1, fmt_date(s.admission)),
          _field("discharge_date", s.discharge.isoformat(), fmt_date(s.discharge), p.discharge, 1, fmt_date(s.discharge)),
          _field("diagnosis", s.diagnosis, s.diagnosis, p.discharge, 1, f"Diagnosis: {s.diagnosis}"),
          _field("treatment", s.procedure, proc, p.discharge, 1, proc),
          _field("policy_number", s.policy_no, s.policy_no, p.discharge, 1, s.policy_no),
          _field("member_id", s.member_id, s.member_id, p.discharge, 1, s.member_id)]
    if s.rx_referenced:
        f.append(_field("referenced_document", f"prescription {s.rx_no}", f"prescription no. {s.rx_no}", p.discharge, 1, f"As per prescription no. {s.rx_no}"))
    if s.room:
        f.append(_field("room_rent_charged_per_day", s.room.rate, s.room.description, p.itemised, 1, s.room.description))
    if s.handwritten_rx:  # read from a photo: no text layer, so the quote is not checked against the page
        f.append({**_field("patient_name", s.patient, s.patient, p.rx, 1, s.patient), "unverifiable": True})
    f += [_field("receipt_amount", s.total, rs(s.total), p.receipt, 1, f"AMOUNT RECEIVED: {rs(s.total)}"),
          _field("receipt_date", s.bill_date.isoformat(), fmt_date(s.bill_date), p.receipt, 1, fmt_date(s.bill_date)),
          _field("patient_name", s.receipt_display_name, s.receipt_display_name, p.receipt, 1, s.receipt_display_name)]
    for l in s.lines:
        f.append({"key": "line_item", "value": {"description": l.description, "qty": l.qty, "rate": l.rate, "amount": l.amount},
                  "raw_text": l.description, **ev(p.itemised, 1, l.description)})
    return f


def expected_findings(s: Scenario, p: Paths) -> list[dict]:
    claim_form = {"source": "claim_form", "field": "claimed_amount", "value": s.claimed_amount}
    clause_pct = f"{s.room_cap_pct:g}%"
    out: list[dict] = []

    def add(n: int, rule: str, issue: str, kind: str, severity: str, blocking: bool, title: str, extracted, comparison, evidence, clause, fix, **extra) -> None:
        out.append({"id": f"{s.key.upper()}-F{n}", "rule_id": rule, "issue_type": issue, "kind": kind, "severity": severity, "blocking": blocking,
                    "title": title, "extracted_value": extracted, "comparison_value": comparison, "evidence": evidence, "clause": clause,
                    "exposure_amount": None, "fix": fix, **extra})

    if s.claimed_amount != s.total:
        over = s.claimed_amount > s.total
        add(len(out) + 1, "V4", "amount_mismatch", "confirmed" if over else "possible", "medium", over,
            "Bill total differs from the amount you are claiming", s.total, s.claimed_amount,
            [ev(p.final, 1, f"TOTAL PAYABLE: {rs(s.total)}"), claim_form], None,
            f"Correct the claimed amount to the bill total ({s.total}) if the bill is right.")
    if s.duplicate_bill:
        add(len(out) + 1, "V1", "duplicate_bill", "confirmed", "high", True, "The same invoice appears in two uploaded files",
            s.invoice_no, s.invoice_no, [ev(p.final, 1, s.invoice_no), ev(p.copy, 1, s.invoice_no)], None,
            "Keep one copy of the final bill and remove the other from the upload.")
    if s.rx_referenced and not s.rx_uploaded:
        add(len(out) + 1, "V7", "referenced_document_missing", "confirmed", "high", True,
            f"Discharge summary refers to prescription {s.rx_no}, which was not uploaded", f"prescription {s.rx_no}", None,
            [ev(p.discharge, 1, f"As per prescription no. {s.rx_no}")],
            {"file": p.policy, "page": 6, "clause_ref": "7.1", "type": "condition", "quote": "prescriptions, diagnostic reports and payment receipts"},
            f"Ask {s.hospital} for a copy of prescription {s.rx_no} and upload it.", owner="hospital")
    exp = exposure(s)
    if exp:
        add(len(out) + 1, "V10", "room_rent_above_cap", "possible", "medium", False,
            "Room rent is above the policy limit; part of the bill may be reduced", s.room.rate, s.room_cap,
            [ev(p.itemised, 1, s.room.description)],
            {"file": p.policy, "page": 4, "clause_ref": "4.1", "type": "sublimit", "quote": f"Room rent is payable up to {clause_pct} of the Sum Insured per day"},
            "Ask the insurer whether proportionate deduction applies to the associated charges.", owner="insurer")
        out[-1]["exposure_amount"] = exp["exposure"]
        out[-1]["exposure_calculation"] = exp
    if s.receipt_name and s.receipt_name != s.patient:
        add(len(out) + 1, "V2", "name_variant", "possible", "low", False, "Patient name is written differently on the payment receipt",
            s.receipt_name, s.patient, [ev(p.receipt, 1, s.receipt_name), ev(p.final, 1, s.patient)], None,
            "Confirm it is the same person; ask the hospital to reissue the receipt if needed.", owner="hospital")
    wc = waiting_conflict(s)
    if wc:
        add(len(out) + 1, "V11", "waiting_period_conflict", "possible", "high", False,
            "The treatment date may fall inside a policy waiting period", f"{wc['elapsed_days']} days", f"{wc['days']} days",
            [ev(p.discharge, 1, fmt_date(s.admission)),
             ev(p.policy, 1, f"{fmt_date(s.period_start)} to {fmt_date(s.period_end)}"), ev(p.policy, 5, wc["quote"])],
            {"file": p.policy, "page": 5, "clause_ref": wc["clause_ref"], "type": "waiting_period", "quote": wc["quote"]},
            "Ask the insurer how the waiting period applies to this treatment.", owner="insurer", waiting=wc)
    return out


def expected_checks_passed(s: Scenario) -> list[str]:
    checks = ["Admission date is not after discharge date", "Admission and discharge fall inside the policy period",
              "Policy number and member ID agree across policy, bill and discharge summary",
              f"Line items add up to the bill total ({s.total})", "Receipt amount equals the bill total",
              "All required documents for a reimbursement claim are present"]
    if s.claimed_amount == s.total:
        checks.append("Bill total matches the claimed amount")
    if not waiting_conflict(s):
        checks.append("No waiting-period conflict found")
    if s.room and s.room.rate <= s.room_cap:
        checks.append("Room rent per day is within the policy limit")
    if not s.duplicate_bill:
        checks.append("No duplicate files or repeated invoices found")
    if not (s.receipt_name and s.receipt_name != s.patient):
        checks.append("Patient name is consistent across the documents")
    return checks


def build_expected(s: Scenario, p: Paths) -> dict:
    findings = expected_findings(s, p)
    blocking = sum(1 for f in findings if f["blocking"])
    uploads = [{"file": p.policy, "doc_type": "policy", "pages": 6}, {"file": p.final, "doc_type": "final_bill", "pages": 1}]
    if s.duplicate_bill:
        uploads.append({"file": p.copy, "doc_type": "final_bill", "pages": 1})
    uploads += [{"file": p.itemised, "doc_type": "itemised_bill", "pages": 1}, {"file": p.discharge, "doc_type": "discharge_summary", "pages": 1},
                {"file": p.receipt, "doc_type": "payment_receipt", "pages": 1}]
    held = []
    if s.rx_referenced:
        entry = {"file": p.rx, "doc_type": "prescription", "pages": 1}
        (uploads if s.rx_uploaded else held).append(entry)
    fixes = []
    if s.claimed_amount != s.total:
        fixes.append(f"Edit the claimed amount from {s.claimed_amount} to {s.total}")
    if s.duplicate_bill:
        fixes.append(f"Remove {Path(p.copy).name}")
    if held:
        fixes.append(f"Upload {Path(p.rx).name}")
    open_after = [f["id"] for f in findings if not f["blocking"]]
    readiness = "ready" if not findings else "needs_attention"
    return {
        "scenario": f"claim_{s.key}", "title": s.title, "synthetic": True,
        "claim_input": {"domain": "health", "claim_type": "reimbursement", "claimed_amount": s.claimed_amount, "patient_name": s.patient},
        "upload_set": uploads, "held_back_for_live_fix": held, "scanned": list(s.scanned) + (["prescription (handwritten)"] if s.handwritten_rx else []),
        "expected_fields": expected_fields(s, p), "expected_findings": findings,
        "expected_checks_passed": expected_checks_passed(s),
        "expected_checklist": {"required_present": ["policy", "final_bill", "itemised_bill", "discharge_summary", "payment_receipt"],
                               "required_missing": [], "referenced_but_missing": ["prescription"] if held else []},
        "expected_readiness": readiness,
        "expected_packet_status": f"INCOMPLETE - {blocking} blocking items" if blocking else "Prepared for submission",
        "demo_fix_sequence": fixes + (["Re-check: blocking items drop to 0; the rest stay as items to review"] if fixes else []),
        "after_fix": {"expected_packet_status": "Prepared for submission", "expected_open_findings": open_after, "expected_blocking_count": 0},
    }


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def verify(root: Path, exp: dict) -> list[str]:
    """Every quote must be on the page it names; every file must have the page count it claims."""
    errors: list[str] = []
    cache: dict[str, list[str]] = {}

    def page(rel: str, n: int) -> str | None:
        if rel not in cache:
            path = root / rel
            if not path.exists():
                return None
            with pymupdf.open(path) as d:
                cache[rel] = [_norm(pg.get_text()) for pg in d]
        pages = cache[rel]
        return pages[n - 1] if 1 <= n <= len(pages) else None

    def check(file: str, n: int, quote: str, label: str) -> None:
        text = page(file, n)
        if text is None:
            errors.append(f"{label}: cannot read {file} page {n}")
        elif _norm(quote) not in text:
            errors.append(f"{label}: quote not found on {file} p.{n}: {quote!r}")

    for f in exp["expected_fields"]:
        if not f.get("unverifiable"):
            check(f["file"], f["page"], f["quote"], f"field {f['key']}")
    for fd in exp["expected_findings"]:
        for e in fd["evidence"]:
            if "file" in e:
                check(e["file"], e["page"], e["quote"], f"finding {fd['id']}")
        if fd.get("clause"):
            c = fd["clause"]
            check(c["file"], c["page"], c["quote"], f"finding {fd['id']} clause")
    for item in exp["upload_set"] + exp["held_back_for_live_fix"]:
        with pymupdf.open(root / item["file"]) as d:  # images open as one-page documents
            if d.page_count != item["pages"]:
                errors.append(f"{item['file']}: expected {item['pages']} pages, got {d.page_count}")
    return errors


def write_zip(root: Path, exp: dict, path: Path) -> None:
    """The upload set in one zip (not the held-back file), deterministic bytes."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for item in sorted(exp["upload_set"], key=lambda i: i["file"]):
            info = zipfile.ZipInfo(f"{exp['scenario']}/{item['file']}", date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, (root / item["file"]).read_bytes())
