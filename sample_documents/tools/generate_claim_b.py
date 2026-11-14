"""Generate SYNTHETIC demo claim "B" (the hero demo claim) + its ground-truth expected results.

Run from the repo root with the backend virtualenv (needs reportlab + pymupdf):

    backend/.venv/bin/python sample_documents/tools/generate_claim_b.py

Everything here is fictional. No real person, hospital, insurer or policy.
After writing the PDFs, the script VERIFIES that every quote used as evidence in the
expected results really appears on the stated page of the stated file (the same
"grounding" rule the product enforces).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pymupdf
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

ROOT = Path(__file__).resolve().parents[1]  # sample_documents/
POLICY_DIR = ROOT / "policy"
MEDICAL_DIR = ROOT / "medical"
HELD_BACK_DIR = MEDICAL_DIR / "_held_back"
EXPECTED_DIR = ROOT / "expected_results"

# ----------------------------------------------------------------------------
# Facts of the scenario (single source of truth for PDFs AND expected results)
# ----------------------------------------------------------------------------
INSURER = "Sample Shield Health Insurance Co. Ltd."
PRODUCT = "Sample Shield Care Plus (Individual Mediclaim)"
POLICY_NO = "SSH-2026-004567"
MEMBER_ID = "M-889201"
PATIENT = "Ravi Kumar Sharma"
PATIENT_VARIANT = "Ravi K Sharma"  # used on the receipt on purpose (name-variant check)
AGE = 42
INCEPTION = "01-Apr-2024"
PERIOD_START, PERIOD_END = "01-Apr-2026", "31-Mar-2027"
SUM_INSURED = 500000
ROOM_CAP_PER_DAY = 5000  # 1% of sum insured

HOSPITAL = "Demo City Care Hospital"
UHID = "DCC-55231"
INVOICE_NO = "INV-2026-08-10457"
BILL_DATE = "15-Aug-2026"
ADMISSION, DISCHARGE = "12-Aug-2026", "15-Aug-2026"
SURGERY_DATE = "13-Aug-2026"
DIAGNOSIS = "Acute appendicitis"
PROCEDURE = "Laparoscopic appendectomy"
RX_NO = "RX-7781"
DOCTOR = "Dr. Anil Menon"
RECEIPT_NO = "RCPT-88231"

ROOM_DAYS = 3
ROOM_RATE = 7500  # above the Rs. 5,000/day cap -> planted issue

# (description, qty, rate, amount, bucket)  bucket: room | associated | other
LINE_ITEMS = [
    ("Room rent - private single room", ROOM_DAYS, ROOM_RATE, ROOM_DAYS * ROOM_RATE, "room"),
    ("Nursing charges", ROOM_DAYS, 1200, ROOM_DAYS * 1200, "associated"),
    ("Surgeon fee", 1, 18000, 18000, "associated"),
    ("Anaesthetist fee", 1, 6000, 6000, "associated"),
    ("Operation theatre charges", 1, 12000, 12000, "associated"),
    ("Laparoscopic surgical consumables", 1, 9500, 9500, "associated"),
    ("Medicines and pharmacy", 1, 7400, 7400, "other"),
    ("Diagnostics (lab and ultrasound)", 1, 5000, 5000, "other"),
    ("Registration and miscellaneous", 1, 1000, 1000, "other"),
]
BILL_TOTAL = sum(i[3] for i in LINE_ITEMS)
CLAIMED_AMOUNT = 95000  # entered on the claim form -> differs from the bill (planted issue)

assert BILL_TOTAL == 85000, BILL_TOTAL

# Final-bill summary buckets (must add up to BILL_TOTAL)
SUMMARY = [
    ("Room rent and nursing", 22500 + 3600),
    ("Professional fees (surgeon, anaesthetist)", 24000),
    ("Operation theatre charges", 12000),
    ("Surgical consumables", 9500),
    ("Medicines and pharmacy", 7400),
    ("Diagnostics", 5000),
    ("Registration and miscellaneous", 1000),
]
assert sum(a for _, a in SUMMARY) == BILL_TOTAL

# Room-rent proportionate-deduction ESTIMATE under clause 4.1 of this synthetic policy
excess_room = (ROOM_RATE - ROOM_CAP_PER_DAY) * ROOM_DAYS
associated_total = sum(i[3] for i in LINE_ITEMS if i[4] == "associated")
ratio = ROOM_CAP_PER_DAY / ROOM_RATE
proportionate_reduction = associated_total * (1 - ratio)
EXPOSURE = round(excess_room + proportionate_reduction)  # 23,867


def inr(n: float) -> str:
    """Indian digit grouping, e.g. 500000 -> 5,00,000."""
    s = f"{int(round(n)):d}"
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    head = re.sub(r"(\d)(?=(\d\d)+$)", r"\1,", head)
    return f"{head},{tail}"


def rs(n: float) -> str:
    return f"Rs. {inr(n)}.00"


# ----------------------------------------------------------------------------
# PDF helpers
# ----------------------------------------------------------------------------
_ss = getSampleStyleSheet()
H1 = ParagraphStyle("H1", parent=_ss["Heading1"], fontSize=15, spaceAfter=6)
H2 = ParagraphStyle("H2", parent=_ss["Heading2"], fontSize=11.5, spaceBefore=8, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=_ss["BodyText"], fontSize=10, leading=14, spaceAfter=5)
SMALL = ParagraphStyle("SMALL", parent=_ss["BodyText"], fontSize=8.5, leading=11, textColor=colors.grey)
CELL = ParagraphStyle("CELL", parent=_ss["BodyText"], fontSize=9.5, leading=12)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")
RIGHT = ParagraphStyle("RIGHT", parent=CELL, alignment=2)
RIGHTB = ParagraphStyle("RIGHTB", parent=RIGHT, fontName="Helvetica-Bold")


def P(text: str, style=BODY) -> Paragraph:
    return Paragraph(text, style)


def kv_table(rows: list[tuple[str, str]]) -> Table:
    data = [[P(k, CELLB), P(v, CELL)] for k, v in rows]
    t = Table(data, colWidths=[55 * mm, 115 * mm])
    t.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return t


def build_pdf(path: Path, doc_label: str, story: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    def decorate(canvas, doc):
        canvas.saveState()
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(colors.grey)
        canvas.drawString(18 * mm, 287 * mm, "SYNTHETIC DEMO DOCUMENT - FICTIONAL - NOT A REAL POLICY OR BILL")
        canvas.drawString(18 * mm, 10 * mm, f"{doc_label}  |  Page {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(
        str(path),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=doc_label,
        author="Covara synthetic demo data",
        invariant=1,  # deterministic bytes -> stable file hashes
    )
    doc.build(story, onFirstPage=decorate, onLaterPages=decorate)


# ----------------------------------------------------------------------------
# Documents
# ----------------------------------------------------------------------------
def make_policy(path: Path) -> None:
    s: list = []
    # ---- Page 1: schedule
    s += [P("POLICY SCHEDULE", H1), P(f"{INSURER}", H2), P(PRODUCT, BODY), Spacer(1, 4)]
    s.append(
        kv_table(
            [
                ("Policy Number", POLICY_NO),
                ("Member ID", MEMBER_ID),
                ("Policyholder / Insured", f"Mr. {PATIENT}"),
                ("Age", f"{AGE} years"),
                ("Policy Inception Date (first enrolment)", INCEPTION),
                ("Current Policy Period", f"{PERIOD_START} to {PERIOD_END}"),
                ("Sum Insured", f"Rs. {inr(SUM_INSURED)}"),
                ("Room Rent Limit", f"1% of Sum Insured per day (Rs. {inr(ROOM_CAP_PER_DAY)} per day)"),
                ("Co-payment", "Nil"),
            ]
        )
    )
    s += [Spacer(1, 6), P("This Schedule must be read together with the Policy Wording (Sections 1 to 7).", SMALL), PageBreak()]

    # ---- Page 2: definitions
    s += [P("SECTION 1 - DEFINITIONS", H1)]
    s += [
        P("<b>1.1 Hospital</b> means an institution registered as a hospital with at least 10 inpatient beds and qualified round-the-clock nursing staff."),
        P("<b>1.2 Inpatient Hospitalisation</b> means admission to a hospital for a minimum continuous period of 24 hours for treatment."),
        P("<b>1.3 Pre-existing Disease</b> means any condition diagnosed or treated within 36 months before the first policy inception date."),
        P(
            "<b>1.4 Associated Medical Expenses</b> means nursing charges, surgeon and anaesthetist fees, "
            "operation theatre charges and surgical consumables incurred during the hospitalisation. "
            "Medicines, diagnostics and registration charges are not Associated Medical Expenses."
        ),
        P("<b>1.5 Reimbursement Claim</b> means a claim where the insured first pays the hospital and then applies to the insurer for repayment."),
        PageBreak(),
    ]

    # ---- Page 3: coverage
    s += [P("SECTION 3 - WHAT IS COVERED", H1)]
    s += [
        P("<b>3.1 Inpatient Hospitalisation.</b> Medically necessary treatment during Inpatient Hospitalisation is covered up to the Sum Insured, subject to the limits in Section 4."),
        P("<b>3.2 Pre-hospitalisation.</b> Relevant medical expenses incurred up to 30 days before admission are covered."),
        P("<b>3.3 Post-hospitalisation.</b> Relevant medical expenses incurred up to 60 days after discharge are covered."),
        P("<b>3.4 Day Care Procedures.</b> Listed day care procedures requiring less than 24 hours of hospitalisation are covered."),
        PageBreak(),
    ]

    # ---- Page 4: limits (room rent clause lives here)
    s += [P("SECTION 4 - LIMITS AND SUB-LIMITS", H1)]
    s += [
        P(
            "<b>4.1 Room Rent.</b> Room rent is payable up to 1% of the Sum Insured per day "
            f"(Rs. {inr(ROOM_CAP_PER_DAY)} per day for a Sum Insured of Rs. {inr(SUM_INSURED)}). "
            "If the Insured opts for a room with a daily rent higher than this limit, the excess room rent is not payable "
            "and all Associated Medical Expenses (see clause 1.4) will be reduced in the same proportion as the eligible "
            "room rent bears to the actual room rent charged (proportionate deduction)."
        ),
        P("<b>4.2 Intensive Care.</b> ICU charges are payable up to 2% of the Sum Insured per day."),
        P("<b>4.3 Co-payment.</b> No co-payment applies under this policy unless stated in the Schedule."),
        PageBreak(),
    ]

    # ---- Page 5: waiting periods
    s += [P("SECTION 5 - WAITING PERIODS", H1)]
    s += [
        P("<b>5.1 Initial Waiting Period.</b> Claims arising within 30 days from the first policy inception date are not payable, except for accidents."),
        P("<b>5.2 Pre-existing Diseases.</b> Pre-existing diseases are covered only after 36 months of continuous coverage."),
        P("<b>5.3 Specified Conditions.</b> Cataract, hernia, hysterectomy and joint replacement are covered only after 24 months of continuous coverage."),
        PageBreak(),
    ]

    # ---- Page 6: exclusions and claim documents
    s += [P("SECTION 6 - EXCLUSIONS", H1)]
    s += [
        P("<b>6.1 Cosmetic Treatment.</b> Cosmetic or plastic surgery unless required after an accident or cancer."),
        P("<b>6.2 Dental Treatment.</b> Dental treatment unless arising from an accident."),
        P("<b>6.3 Non-medical Expenses.</b> Items listed as non-medical in Annexure A (for example, admission kits and toiletries)."),
        P("SECTION 7 - CLAIMS", H1),
        P(
            "<b>7.1 Documents for a Reimbursement Claim.</b> The Insured must submit the duly filled claim form, original final bill, "
            "itemised bill, discharge summary, prescriptions, diagnostic reports and payment receipts."
        ),
        P("<b>7.2 Time Limit.</b> Reimbursement claims must be submitted within 30 days of discharge."),
    ]
    build_pdf(path, "Policy wording and schedule", s)


def _patient_block(variant: str = PATIENT) -> Table:
    return kv_table(
        [
            ("Patient Name", variant),
            ("Age / Sex", f"{AGE} / Male"),
            ("UHID", UHID),
            ("Policy Number", POLICY_NO),
            ("Member ID", MEMBER_ID),
            ("Date of Admission", ADMISSION),
            ("Date of Discharge", DISCHARGE),
        ]
    )


def make_final_bill(path: Path, copy: bool = False) -> None:
    s: list = [P(HOSPITAL, H1), P("12 Demo Road, Sample City - 000000 | Reg. No. DEMO/HOSP/0001", SMALL)]
    s.append(P("FINAL BILL" + (" (PATIENT COPY - REPRINT)" if copy else ""), H2))
    s.append(kv_table([("Invoice Number", INVOICE_NO), ("Bill Date", BILL_DATE)]))
    s.append(Spacer(1, 5))
    s.append(_patient_block())
    s.append(Spacer(1, 6))
    rows = [[P("Particulars", CELLB), P("Amount (Rs.)", RIGHTB)]]
    rows += [[P(name, CELL), P(f"{inr(amt)}.00", RIGHT)] for name, amt in SUMMARY]
    t = Table(rows, colWidths=[120 * mm, 50 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
    s.append(t)
    s.append(Spacer(1, 6))
    s.append(P(f"<b>TOTAL PAYABLE: {rs(BILL_TOTAL)}</b>", BODY))
    s.append(P("Amount in words: Rupees Eighty Five Thousand Only", CELL))
    if copy:
        s.append(Spacer(1, 6))
        s.append(P("Printed again at patient request on 16-Aug-2026 (duplicate print of the same invoice).", SMALL))
    build_pdf(path, "Final bill" + (" (copy)" if copy else ""), s)


def make_itemised_bill(path: Path) -> None:
    s: list = [P(HOSPITAL, H1), P("ITEMISED BILL", H2)]
    s.append(kv_table([("Invoice Number", INVOICE_NO), ("Bill Date", BILL_DATE)]))
    s.append(Spacer(1, 5))
    s.append(_patient_block())
    s.append(Spacer(1, 6))
    rows = [[P("#", CELLB), P("Description", CELLB), P("Qty", RIGHTB), P("Rate", RIGHTB), P("Amount (Rs.)", RIGHTB)]]
    for n, (desc, qty, rate, amt, _) in enumerate(LINE_ITEMS, 1):
        rows.append([P(str(n), CELL), P(desc, CELL), P(str(qty), RIGHT), P(inr(rate), RIGHT), P(f"{inr(amt)}.00", RIGHT)])
    t = Table(rows, colWidths=[10 * mm, 85 * mm, 15 * mm, 25 * mm, 35 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.lightgrey), ("BACKGROUND", (0, 0), (-1, 0), colors.whitesmoke)]))
    s.append(t)
    s.append(Spacer(1, 6))
    s.append(P(f"<b>GRAND TOTAL: {rs(BILL_TOTAL)}</b>", BODY))
    build_pdf(path, "Itemised bill", s)


def make_discharge_summary(path: Path) -> None:
    s: list = [P(HOSPITAL, H1), P("DISCHARGE SUMMARY", H2), _patient_block(), Spacer(1, 6)]
    s += [
        P(f"<b>Diagnosis:</b> {DIAGNOSIS}"),
        P(f"<b>Procedure:</b> {PROCEDURE} performed on {SURGERY_DATE}"),
        P(
            "<b>Course in hospital:</b> The patient was admitted with right lower abdominal pain. Investigations supported the "
            "diagnosis and surgery was performed under general anaesthesia. Recovery was uneventful."
        ),
        P("<b>Condition at discharge:</b> Stable, tolerating oral diet, wound clean."),
        P(
            f"<b>Discharge medication:</b> As per prescription no. {RX_NO} dated {DISCHARGE} "
            "(copy to be attached with the claim documents)."
        ),
        P("<b>Follow-up:</b> Review in the surgical outpatient department after 7 days."),
        Spacer(1, 10),
        P(f"{DOCTOR}, Consultant Surgeon | Reg. No. DEMO-MC-12345"),
    ]
    build_pdf(path, "Discharge summary", s)


def make_receipt(path: Path) -> None:
    s: list = [P(HOSPITAL, H1), P("PAYMENT RECEIPT", H2)]
    s.append(
        kv_table(
            [
                ("Receipt Number", RECEIPT_NO),
                ("Receipt Date", BILL_DATE),
                ("Received from", PATIENT_VARIANT),
                ("Towards Invoice", INVOICE_NO),
                ("Mode of payment", "UPI"),
            ]
        )
    )
    s += [Spacer(1, 8), P(f"<b>AMOUNT RECEIVED: {rs(BILL_TOTAL)}</b>")]
    build_pdf(path, "Payment receipt", s)


def make_prescription(path: Path) -> None:
    s: list = [P(HOSPITAL, H1), P(f"PRESCRIPTION - No. {RX_NO}", H2)]
    s.append(
        kv_table(
            [
                ("Patient Name", PATIENT),
                ("Age / Sex", f"{AGE} / Male"),
                ("UHID", UHID),
                ("Prescription Date", DISCHARGE),
                ("Diagnosis", DIAGNOSIS),
            ]
        )
    )
    s += [
        Spacer(1, 8),
        P("<b>Rx</b>"),
        P("1. Tab Amoxicillin-Clavulanate 625 mg - twice daily for 5 days"),
        P("2. Tab Paracetamol 650 mg - when required for pain"),
        P("3. Tab Pantoprazole 40 mg - once daily before breakfast for 5 days"),
        Spacer(1, 10),
        P(f"{DOCTOR}, Consultant Surgeon | Reg. No. DEMO-MC-12345"),
    ]
    build_pdf(path, "Prescription", s)


# ----------------------------------------------------------------------------
# Expected results (ground truth). Quotes are VERIFIED against the PDFs below.
# ----------------------------------------------------------------------------
F_POLICY = "policy/claim_b_policy.pdf"
F_FINAL = "medical/claim_b_final_bill.pdf"
F_COPY = "medical/claim_b_final_bill_copy.pdf"
F_ITEM = "medical/claim_b_itemised_bill.pdf"
F_DISCH = "medical/claim_b_discharge_summary.pdf"
F_RECEIPT = "medical/claim_b_payment_receipt.pdf"
F_RX = "medical/_held_back/claim_b_prescription_RX-7781.pdf"


def ev(file: str, page: int, quote: str) -> dict:
    return {"file": file, "page": page, "quote": quote}


def field(key, value, raw, file, page, quote) -> dict:
    return {"key": key, "value": value, "raw_text": raw, **ev(file, page, quote)}


def expected() -> dict:
    fields = [
        field("policy_number", POLICY_NO, POLICY_NO, F_POLICY, 1, POLICY_NO),
        field("member_id", MEMBER_ID, MEMBER_ID, F_POLICY, 1, MEMBER_ID),
        field("insurer", INSURER, INSURER, F_POLICY, 1, INSURER),
        field("policyholder_name", PATIENT, f"Mr. {PATIENT}", F_POLICY, 1, f"Mr. {PATIENT}"),
        field("policy_start", "2026-04-01", PERIOD_START, F_POLICY, 1, f"{PERIOD_START} to {PERIOD_END}"),
        field("policy_end", "2027-03-31", PERIOD_END, F_POLICY, 1, f"{PERIOD_START} to {PERIOD_END}"),
        field("sum_insured", SUM_INSURED, f"Rs. {inr(SUM_INSURED)}", F_POLICY, 1, f"Rs. {inr(SUM_INSURED)}"),
        field("room_rent_cap", ROOM_CAP_PER_DAY, f"Rs. {inr(ROOM_CAP_PER_DAY)} per day", F_POLICY, 1, f"(Rs. {inr(ROOM_CAP_PER_DAY)} per day)"),
        field("waiting_period", "initial 30 days; pre-existing 36 months; specified conditions 24 months", "Section 5", F_POLICY, 5, "Claims arising within 30 days from the first policy inception date are not payable"),
        field("patient_name", PATIENT, PATIENT, F_FINAL, 1, PATIENT),
        field("hospital_name", HOSPITAL, HOSPITAL, F_FINAL, 1, HOSPITAL),
        field("bill_number", INVOICE_NO, INVOICE_NO, F_FINAL, 1, INVOICE_NO),
        field("bill_date", "2026-08-15", BILL_DATE, F_FINAL, 1, BILL_DATE),
        field("bill_total", BILL_TOTAL, rs(BILL_TOTAL), F_FINAL, 1, f"TOTAL PAYABLE: {rs(BILL_TOTAL)}"),
        field("admission_date", "2026-08-12", ADMISSION, F_DISCH, 1, ADMISSION),
        field("discharge_date", "2026-08-15", DISCHARGE, F_DISCH, 1, DISCHARGE),
        field("diagnosis", DIAGNOSIS, DIAGNOSIS, F_DISCH, 1, f"Diagnosis: {DIAGNOSIS}"),
        field("treatment", PROCEDURE, f"{PROCEDURE} performed on {SURGERY_DATE}", F_DISCH, 1, f"{PROCEDURE} performed on {SURGERY_DATE}"),
        field("referenced_document", f"prescription {RX_NO}", f"prescription no. {RX_NO}", F_DISCH, 1, f"As per prescription no. {RX_NO}"),
        field("room_rent_charged_per_day", ROOM_RATE, "Room rent - private single room", F_ITEM, 1, "Room rent - private single room"),
        field("receipt_amount", BILL_TOTAL, rs(BILL_TOTAL), F_RECEIPT, 1, f"AMOUNT RECEIVED: {rs(BILL_TOTAL)}"),
        field("receipt_date", "2026-08-15", BILL_DATE, F_RECEIPT, 1, BILL_DATE),
        field("patient_name", PATIENT_VARIANT, PATIENT_VARIANT, F_RECEIPT, 1, PATIENT_VARIANT),
    ]
    for desc, qty, rate, amt, _ in LINE_ITEMS:
        fields.append(
            {"key": "line_item", "value": {"description": desc, "qty": qty, "rate": rate, "amount": amt},
             "raw_text": desc, **ev(F_ITEM, 1, desc)}
        )

    claim_form_ev = {"source": "claim_form", "field": "claimed_amount", "value": CLAIMED_AMOUNT}
    clause_41 = {
        "file": F_POLICY,
        "page": 4,
        "clause_ref": "4.1",
        "type": "sublimit",
        "quote": "Room rent is payable up to 1% of the Sum Insured per day",
    }
    findings = [
        {
            "id": "B-F1",
            "rule_id": "V4",
            "issue_type": "amount_mismatch",
            "kind": "confirmed",
            "severity": "medium",
            "blocking": True,
            "title": "Bill total differs from the amount you are claiming",
            "extracted_value": BILL_TOTAL,
            "comparison_value": CLAIMED_AMOUNT,
            "evidence": [ev(F_FINAL, 1, f"TOTAL PAYABLE: {rs(BILL_TOTAL)}"), claim_form_ev],
            "clause": None,
            "exposure_amount": None,
            "fix": "Correct the claimed amount to the bill total (85000) if the bill is right.",
        },
        {
            "id": "B-F2",
            "rule_id": "V1",
            "issue_type": "duplicate_bill",
            "kind": "confirmed",
            "severity": "high",
            "blocking": True,
            "title": "The same invoice appears in two uploaded files",
            "extracted_value": INVOICE_NO,
            "comparison_value": INVOICE_NO,
            "evidence": [ev(F_FINAL, 1, INVOICE_NO), ev(F_COPY, 1, INVOICE_NO)],
            "clause": None,
            "exposure_amount": None,
            "fix": "Keep one copy of the final bill and remove the other from the upload.",
        },
        {
            "id": "B-F3",
            "rule_id": "V7",
            "issue_type": "referenced_document_missing",
            "kind": "confirmed",
            "severity": "high",
            "blocking": True,
            "title": f"Discharge summary refers to prescription {RX_NO}, which was not uploaded",
            "extracted_value": f"prescription {RX_NO}",
            "comparison_value": None,
            "evidence": [ev(F_DISCH, 1, f"As per prescription no. {RX_NO}")],
            "clause": {
                "file": F_POLICY,
                "page": 6,
                "clause_ref": "7.1",
                "type": "condition",
                "quote": "prescriptions, diagnostic reports and payment receipts",
            },
            "exposure_amount": None,
            "fix": f"Ask {HOSPITAL} for a copy of prescription {RX_NO} and upload it.",
            "owner": "hospital",
        },
        {
            "id": "B-F4",
            "rule_id": "V10",
            "issue_type": "room_rent_above_cap",
            "kind": "possible",
            "severity": "medium",
            "blocking": False,
            "title": "Room rent is above the policy limit; part of the bill may be reduced",
            "extracted_value": ROOM_RATE,
            "comparison_value": ROOM_CAP_PER_DAY,
            "evidence": [ev(F_ITEM, 1, "Room rent - private single room")],
            "clause": clause_41,
            "exposure_amount": EXPOSURE,
            "exposure_calculation": {
                "days": ROOM_DAYS,
                "excess_room_rent": excess_room,
                "associated_medical_expenses": associated_total,
                "eligible_to_actual_ratio": round(ratio, 4),
                "proportionate_reduction": round(proportionate_reduction, 2),
                "note": "Informational estimate under clause 4.1 and 1.4 of this synthetic policy; not a coverage decision.",
            },
            "fix": "Ask the insurer whether proportionate deduction applies to the associated charges.",
            "owner": "insurer",
        },
        {
            "id": "B-F5",
            "rule_id": "V2",
            "issue_type": "name_variant",
            "kind": "possible",
            "severity": "low",
            "blocking": False,
            "title": "Patient name is written differently on the payment receipt",
            "extracted_value": PATIENT_VARIANT,
            "comparison_value": PATIENT,
            "evidence": [ev(F_RECEIPT, 1, PATIENT_VARIANT), ev(F_FINAL, 1, PATIENT)],
            "clause": None,
            "exposure_amount": None,
            "fix": "Confirm it is the same person; ask the hospital to reissue the receipt if needed.",
            "owner": "hospital",
        },
    ]

    return {
        "scenario": "claim_b",
        "title": "Hero demo claim: amount mismatch, duplicate bill, missing prescription, room rent above cap",
        "synthetic": True,
        "claim_input": {
            "domain": "health",
            "claim_type": "reimbursement",
            "claimed_amount": CLAIMED_AMOUNT,
            "patient_name": PATIENT,
        },
        "upload_set": [
            {"file": F_POLICY, "doc_type": "policy", "pages": 6},
            {"file": F_FINAL, "doc_type": "final_bill", "pages": 1},
            {"file": F_COPY, "doc_type": "final_bill", "pages": 1},
            {"file": F_ITEM, "doc_type": "itemised_bill", "pages": 1},
            {"file": F_DISCH, "doc_type": "discharge_summary", "pages": 1},
            {"file": F_RECEIPT, "doc_type": "payment_receipt", "pages": 1},
        ],
        "held_back_for_live_fix": [
            {"file": F_RX, "doc_type": "prescription", "pages": 1, "purpose": "Upload during the demo to resolve B-F3."}
        ],
        "expected_fields": fields,
        "expected_findings": findings,
        "expected_checks_passed": [
            "Admission date is not after discharge date",
            "Admission and discharge fall inside the policy period",
            "Policy number and member ID agree across policy, bill and discharge summary",
            "Line items add up to the bill total (85000)",
            "Receipt amount equals the bill total",
            "All required documents for a reimbursement claim are present (policy, final bill, itemised bill, discharge summary, receipt)",
            "No waiting-period conflict (diagnosis well after the 30-day initial waiting period)",
        ],
        "expected_checklist": {
            "required_present": ["policy", "final_bill", "itemised_bill", "discharge_summary", "payment_receipt"],
            "required_missing": [],
            "referenced_but_missing": ["prescription"],
        },
        "expected_readiness": "needs_attention",
        "expected_packet_status": "INCOMPLETE - 3 blocking items",
        "demo_fix_sequence": [
            "Edit the claimed amount from 95000 to 85000 (resolves B-F1)",
            "Remove claim_b_final_bill_copy.pdf (resolves B-F2)",
            f"Upload {Path(F_RX).name} (resolves B-F3)",
            "Re-check: blocking items drop to 0; B-F4 and B-F5 remain as items to review; packet becomes 'Prepared for submission'",
        ],
        "after_fix": {
            "expected_packet_status": "Prepared for submission",
            "expected_open_findings": ["B-F4", "B-F5"],
            "expected_blocking_count": 0,
        },
    }


# ----------------------------------------------------------------------------
# Verification: every quoted evidence must really be on that page of that file
# ----------------------------------------------------------------------------
def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def verify(exp: dict) -> list[str]:
    errors: list[str] = []
    cache: dict[str, list[str]] = {}

    def page_text(rel: str, page: int) -> str | None:
        if rel not in cache:
            path = ROOT / rel
            if not path.exists():
                return None
            with pymupdf.open(path) as d:
                cache[rel] = [_norm(p.get_text()) for p in d]
        pages = cache[rel]
        return pages[page - 1] if 1 <= page <= len(pages) else None

    def check(file: str, page: int, quote: str, label: str) -> None:
        text = page_text(file, page)
        if text is None:
            errors.append(f"{label}: cannot read {file} page {page}")
        elif _norm(quote) not in text:
            errors.append(f"{label}: quote not found on {file} p.{page}: {quote!r}")

    for f in exp["expected_fields"]:
        check(f["file"], f["page"], f["quote"], f"field {f['key']}")
    for fd in exp["expected_findings"]:
        for e in fd["evidence"]:
            if "file" in e:
                check(e["file"], e["page"], e["quote"], f"finding {fd['id']} evidence")
        if fd.get("clause"):
            c = fd["clause"]
            check(c["file"], c["page"], c["quote"], f"finding {fd['id']} clause")
    for item in exp["upload_set"] + exp["held_back_for_live_fix"]:
        with pymupdf.open(ROOT / item["file"]) as d:
            if d.page_count != item["pages"]:
                errors.append(f"{item['file']}: expected {item['pages']} pages, got {d.page_count}")
    return errors


DOC_IDS = {
    F_POLICY: "doc-policy",
    F_FINAL: "doc-final-bill",
    F_COPY: "doc-final-bill-copy",
    F_ITEM: "doc-itemised-bill",
    F_DISCH: "doc-discharge-summary",
    F_RECEIPT: "doc-receipt",
}

RULE_TEXT = {
    "V1": ("Duplicate bill check", "The same invoice number appears in more than one uploaded file.",
           "Submitting the same bill twice can cause confusion or delay."),
    "V2": ("Patient identity check", "Compares the patient name written on each document.",
           "Names that differ between documents may need to be explained to the insurer."),
    "V4": ("Amount check", "Compares the bill total with the amount entered on the claim form.",
           "A claimed amount that does not match the bill is a common reason for queries."),
    "V7": ("Required / referenced documents check",
           "Looks for documents that other documents refer to, and for documents the policy asks for.",
           "The policy lists prescriptions among the documents to submit (clause 7.1)."),
    "V10": ("Room-rent limit check", "Compares the daily room rent on the bill with the policy limit.",
            "If room rent is above the limit, clause 4.1 may reduce related charges in proportion."),
}


def _evidence_ref(e: dict) -> dict:
    if "file" in e:
        return {"source": "document", "document_id": DOC_IDS.get(e["file"], "doc-held-back"),
                "filename": Path(e["file"]).name, "page_number": e["page"], "bbox": None, "quote": e["quote"]}
    return {"source": "claim_form", "document_id": None, "filename": None, "page_number": None,
            "bbox": None, "quote": None, "field": e["field"], "value": e["value"]}


def build_results_fixture(exp: dict) -> dict:
    """AnalysisResults-shaped mock (section 4 of docs/DIVISION_OF_WORK.md). Used by the frontend and pipeline stubs."""
    fields = []
    for n, f in enumerate(exp["expected_fields"], 1):
        fields.append({
            "id": f"fld-{n:03d}", "key": f["key"], "value": f["value"], "raw_text": f["raw_text"],
            "confidence": 0.95, "user_confirmed": False,
            "evidence": _evidence_ref({"file": f["file"], "page": f["page"], "quote": f["quote"]}),
        })

    clauses = [
        {"id": "c-1.4", "clause_ref": "1.4", "type": "definition", "title": "Associated Medical Expenses",
         "text": "Associated Medical Expenses means nursing charges, surgeon and anaesthetist fees, operation theatre charges and surgical consumables incurred during the hospitalisation. Medicines, diagnostics and registration charges are not Associated Medical Expenses.",
         "document_id": "doc-policy", "filename": "claim_b_policy.pdf", "page_number": 2},
        {"id": "c-4.1", "clause_ref": "4.1", "type": "sublimit", "title": "Room Rent",
         "text": "Room rent is payable up to 1% of the Sum Insured per day (Rs. 5,000 per day for a Sum Insured of Rs. 5,00,000). If the Insured opts for a room with a daily rent higher than this limit, the excess room rent is not payable and all Associated Medical Expenses (see clause 1.4) will be reduced in the same proportion as the eligible room rent bears to the actual room rent charged (proportionate deduction).",
         "document_id": "doc-policy", "filename": "claim_b_policy.pdf", "page_number": 4},
        {"id": "c-5.1", "clause_ref": "5.1", "type": "waiting_period", "title": "Initial Waiting Period",
         "text": "Claims arising within 30 days from the first policy inception date are not payable, except for accidents.",
         "document_id": "doc-policy", "filename": "claim_b_policy.pdf", "page_number": 5},
        {"id": "c-7.1", "clause_ref": "7.1", "type": "condition", "title": "Documents for a Reimbursement Claim",
         "text": "The Insured must submit the duly filled claim form, original final bill, itemised bill, discharge summary, prescriptions, diagnostic reports and payment receipts.",
         "document_id": "doc-policy", "filename": "claim_b_policy.pdf", "page_number": 6},
    ]
    clause_by_ref = {c["clause_ref"]: c["id"] for c in clauses}

    findings = []
    for f in exp["expected_findings"]:
        title, rule, why = RULE_TEXT[f["rule_id"]]
        clause_links = []
        if f.get("clause"):
            clause_links.append({"clause_id": clause_by_ref[f["clause"]["clause_ref"]],
                                 "verdict": "may_apply" if f["rule_id"] == "V10" else "applies",
                                 "quote": f["clause"]["quote"]})
        findings.append({
            "id": f["id"], "rule_id": f["rule_id"], "issue_type": f["issue_type"],
            "severity": f["severity"], "kind": f["kind"], "title": f["title"],
            "description": f["fix"], "evidence": [_evidence_ref(e) for e in f["evidence"]],
            "extracted_value": None if f["extracted_value"] is None else str(f["extracted_value"]),
            "comparison_value": None if f["comparison_value"] is None else str(f["comparison_value"]),
            "clause_links": clause_links, "exposure_amount": f["exposure_amount"],
            "blocking": f["blocking"],
            "explanation": {"rule": f"{f['rule_id']} - {title}: {rule}", "inputs": f.get("exposure_calculation") or {
                "extracted_value": f["extracted_value"], "comparison_value": f["comparison_value"]}, "why_it_matters": why},
            "requires_human_review": True, "status": "open",
        })

    def msg(text: str) -> str:
        return text

    actions = [
        {"id": "a-1", "title": "Correct the amount you are claiming", "why": f"Your claim form says {inr(CLAIMED_AMOUNT)} but the hospital bill total is {inr(BILL_TOTAL)}.",
         "how": ["Check the final bill total on page 1.", f"If the bill is right, change the claimed amount to {inr(BILL_TOTAL)}."],
         "owner": "user", "blocking": True, "group": "verify_or_correct", "finding_ids": ["B-F1"], "clause_ids": [], "draft_message": None, "done": False},
        {"id": "a-2", "title": "Keep only one copy of the final bill", "why": f"Invoice {INVOICE_NO} appears in two uploaded files.",
         "how": ["Remove claim_b_final_bill_copy.pdf (or the other copy) from the upload."],
         "owner": "user", "blocking": True, "group": "verify_or_correct", "finding_ids": ["B-F2"], "clause_ids": [], "draft_message": None, "done": False},
        {"id": "a-3", "title": f"Get prescription {RX_NO} from the hospital and upload it", "why": f"The discharge summary refers to prescription {RX_NO}; the policy asks for prescriptions (clause 7.1).",
         "how": [f"Ask {HOSPITAL} for a signed copy.", "Upload it with the other documents."],
         "owner": "hospital", "blocking": True, "group": "upload", "finding_ids": ["B-F3"], "clause_ids": ["c-7.1"],
         "draft_message": f"Hello {HOSPITAL} records team, my discharge summary (UHID {UHID}, admitted {ADMISSION}, discharged {DISCHARGE}) refers to prescription no. {RX_NO} dated {DISCHARGE}. Please share a signed copy so I can submit it with my reimbursement claim. Thank you.",
         "done": False},
        {"id": "a-4", "title": "Ask the insurer how the room-rent limit applies", "why": f"Room rent was Rs. {inr(ROOM_RATE)} per day against a limit of Rs. {inr(ROOM_CAP_PER_DAY)} per day (clause 4.1). This is an estimate to review, not a decision: about Rs. {inr(EXPOSURE)} could be affected.",
         "how": ["Ask whether proportionate deduction applies to nursing, surgeon, anaesthetist, theatre and consumable charges (clause 1.4)."],
         "owner": "insurer", "blocking": False, "group": "ask_insurer", "finding_ids": ["B-F4"], "clause_ids": ["c-4.1", "c-1.4"],
         "draft_message": f"Hello {INSURER}, for policy {POLICY_NO}, my room rent was Rs. {inr(ROOM_RATE)} per day against the Rs. {inr(ROOM_CAP_PER_DAY)} limit in clause 4.1. Please confirm how proportionate deduction would apply to my associated medical expenses before I submit the claim.",
         "done": False},
        {"id": "a-5", "title": "Confirm the name on the payment receipt", "why": f"The receipt says '{PATIENT_VARIANT}' while other documents say '{PATIENT}'.",
         "how": ["Confirm it is the same person.", "Ask the hospital to reissue the receipt if you want the name to match exactly."],
         "owner": "hospital", "blocking": False, "group": "verify_or_correct", "finding_ids": ["B-F5"], "clause_ids": [],
         "draft_message": f"Hello {HOSPITAL}, receipt {RECEIPT_NO} shows the name '{PATIENT_VARIANT}'. My name on the bill is '{PATIENT}'. Could you please reissue the receipt with the full name?", "done": False},
    ]

    return {
        "claim_id": "demo-claim-b",
        "status": "complete", "stage": "complete", "progress": 1.0,
        "readiness_status": exp["expected_readiness"],
        "readiness_explanation": "3 items need to be fixed before this packet is complete, and 2 more are worth reviewing. This is an AI-assisted preparation check, not an insurer decision.",
        "documents": [{"id": DOC_IDS[u["file"]], "filename": Path(u["file"]).name, "doc_type": u["doc_type"], "status": "processed", "error": None} for u in exp["upload_set"]],
        "documents_failed": [],
        "fields": fields,
        "findings": findings,
        "clauses": clauses,
        "policy_summary": {
            "sum_insured": {"value": SUM_INSURED, "evidence": _evidence_ref({"file": F_POLICY, "page": 1, "quote": f"Rs. {inr(SUM_INSURED)}"})},
            "room_rent_cap": {"value": ROOM_CAP_PER_DAY, "evidence": _evidence_ref({"file": F_POLICY, "page": 4, "quote": "Room rent is payable up to 1% of the Sum Insured per day"})},
            "copay": {"value": 0, "evidence": _evidence_ref({"file": F_POLICY, "page": 4, "quote": "No co-payment applies under this policy"})},
            "waiting_periods": [{"label": "Initial", "days": 30, "clause_id": "c-5.1"}, {"label": "Pre-existing", "months": 36}, {"label": "Specified conditions", "months": 24}],
            "exclusions": ["Cosmetic treatment", "Dental treatment unless accident", "Non-medical expenses"],
            "pre_hosp_days": 30, "post_hosp_days": 60,
        },
        "action_plan": actions,
        "checks_passed": exp["expected_checks_passed"],
        "checklist": exp["expected_checklist"],
        "packet_status": exp["expected_packet_status"],
        "disclaimer": "Covara is an AI-assisted preparation tool. It does not decide whether an insurer will approve a claim and does not replace an insurer, doctor, broker or licensed adviser. Demo data is synthetic.",
    }


def main() -> int:
    make_policy(ROOT / F_POLICY)
    make_final_bill(ROOT / F_FINAL)
    make_final_bill(ROOT / F_COPY, copy=True)
    make_itemised_bill(ROOT / F_ITEM)
    make_discharge_summary(ROOT / F_DISCH)
    make_receipt(ROOT / F_RECEIPT)
    make_prescription(ROOT / F_RX)

    exp = expected()
    EXPECTED_DIR.mkdir(parents=True, exist_ok=True)
    out = EXPECTED_DIR / "claim_b.json"
    out.write_text(json.dumps(exp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    fixture = build_results_fixture(exp)
    fx_out = EXPECTED_DIR / "claim_b.results.fixture.json"
    fx_out.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    errors = verify(exp)
    # every action must name a finding (invariant I3) and every finding must carry evidence (I1)
    for a in fixture["action_plan"]:
        if not a["finding_ids"]:
            errors.append(f"action {a['id']} has no finding_ids")
    for f in fixture["findings"]:
        if not f["evidence"]:
            errors.append(f"finding {f['id']} has no evidence")
    print(f"Wrote 7 PDFs, {out.relative_to(ROOT.parent)} and {fx_out.relative_to(ROOT.parent)}")
    print(f"Bill total {BILL_TOTAL}, claimed {CLAIMED_AMOUNT}, room-rent exposure estimate {EXPOSURE}")
    if errors:
        print("\nVERIFICATION FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print(f"Verified {len(exp['expected_fields'])} fields and {len(exp['expected_findings'])} findings against the PDFs: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
