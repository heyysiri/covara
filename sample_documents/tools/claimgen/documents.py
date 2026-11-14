"""Document builders: one PDF per document type, every fact read from the Scenario."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path
from xml.sax.saxutils import escape as x

from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Spacer

from .pdfkit import BODY, CELL, CELLB, H1, H2, RIGHT, RIGHTB, SMALL, P, build_pdf, grid, kv_table
from .scenario import Scenario, fmt_date, human_list, inr, rs, words


def make_policy(s: Scenario, path: Path) -> None:
    pct = f"{s.room_cap_pct:g}%"
    story: list = [P("POLICY SCHEDULE", H1), P(x(s.insurer), H2), P(x(s.product), BODY), Spacer(1, 4)]
    story.append(kv_table([
        ("Policy Number", s.policy_no), ("Member ID", s.member_id), ("Policyholder / Insured", f"{s.salutation} {s.patient}"),
        ("Age", f"{s.age} years"), ("Policy Inception Date (first enrolment)", fmt_date(s.inception)),
        ("Current Policy Period", f"{fmt_date(s.period_start)} to {fmt_date(s.period_end)}"),
        ("Sum Insured", f"Rs. {inr(s.sum_insured)}"),
        ("Room Rent Limit", f"{pct} of Sum Insured per day (Rs. {inr(s.room_cap)} per day)"), ("Co-payment", "Nil"),
    ]))
    story += [Spacer(1, 6), P("This Schedule must be read together with the Policy Wording (Sections 1 to 7).", SMALL), PageBreak()]

    story += [P("SECTION 1 - DEFINITIONS", H1),
        P("<b>1.1 Hospital</b> means an institution registered as a hospital with at least 10 inpatient beds and qualified round-the-clock nursing staff."),
        P("<b>1.2 Inpatient Hospitalisation</b> means admission to a hospital for a minimum continuous period of 24 hours for treatment."),
        P(f"<b>1.3 Pre-existing Disease</b> means any condition diagnosed or treated within {s.preexisting_months} months before the first policy inception date."),
        P("<b>1.4 Associated Medical Expenses</b> means " + x(s.definition_included) + " incurred during the hospitalisation. "
          + x(s.definition_excluded) + " are not Associated Medical Expenses."),
        P("<b>1.5 Reimbursement Claim</b> means a claim where the insured first pays the hospital and then applies to the insurer for repayment."),
        PageBreak()]

    story += [P("SECTION 3 - WHAT IS COVERED", H1),
        P("<b>3.1 Inpatient Hospitalisation.</b> Medically necessary treatment during Inpatient Hospitalisation is covered up to the Sum Insured, subject to the limits in Section 4."),
        P(f"<b>3.2 Pre-hospitalisation.</b> Relevant medical expenses incurred up to {s.pre_hosp_days} days before admission are covered."),
        P(f"<b>3.3 Post-hospitalisation.</b> Relevant medical expenses incurred up to {s.post_hosp_days} days after discharge are covered."),
        P("<b>3.4 Day Care Procedures.</b> Listed day care procedures requiring less than 24 hours of hospitalisation are covered."),
        PageBreak()]

    story += [P("SECTION 4 - LIMITS AND SUB-LIMITS", H1),
        P(f"<b>4.1 Room Rent.</b> Room rent is payable up to {pct} of the Sum Insured per day "
          f"(Rs. {inr(s.room_cap)} per day for a Sum Insured of Rs. {inr(s.sum_insured)}). "
          "If the Insured opts for a room with a daily rent higher than this limit, the excess room rent is not payable "
          "and all Associated Medical Expenses (see clause 1.4) will be reduced in the same proportion as the eligible "
          "room rent bears to the actual room rent charged (proportionate deduction)."),
        P(f"<b>4.2 Intensive Care.</b> ICU charges are payable up to {s.icu_pct:g}% of the Sum Insured per day."),
        P("<b>4.3 Co-payment.</b> No co-payment applies under this policy unless stated in the Schedule."),
        PageBreak()]

    story += [P("SECTION 5 - WAITING PERIODS", H1),
        P(f"<b>5.1 Initial Waiting Period.</b> Claims arising within {s.initial_wait_days} days from the first policy inception date are not payable, except for accidents."),
        P(f"<b>5.2 Pre-existing Diseases.</b> Pre-existing diseases are covered only after {s.preexisting_months} months of continuous coverage."),
        P(f"<b>5.3 Specified Conditions.</b> {human_list(s.specified_conditions)} are covered only after {s.specified_months} months of continuous coverage."),
        PageBreak()]

    story.append(P("SECTION 6 - EXCLUSIONS", H1))
    story += [P(f"<b>6.{i} {x(title)}.</b> {x(text)}") for i, (title, text) in enumerate(s.exclusions, 1)]
    story += [P("SECTION 7 - CLAIMS", H1),
        P("<b>7.1 Documents for a Reimbursement Claim.</b> The Insured must submit the duly filled claim form, original final bill, "
          "itemised bill, discharge summary, prescriptions, diagnostic reports and payment receipts."),
        P(f"<b>7.2 Time Limit.</b> Reimbursement claims must be submitted within {s.claim_days_limit} days of discharge.")]
    build_pdf(path, "Policy wording and schedule", story)


def patient_block(s: Scenario, name: str | None = None) -> object:
    return kv_table([
        ("Patient Name", name or s.patient), ("Age / Sex", f"{s.age} / {s.sex}"), ("UHID", s.uhid),
        ("Policy Number", s.policy_no), ("Member ID", s.member_id),
        ("Date of Admission", fmt_date(s.admission)), ("Date of Discharge", fmt_date(s.discharge)),
    ])


def make_final_bill(s: Scenario, path: Path, copy: bool = False) -> None:
    story: list = [P(x(s.hospital), H1), P(x(s.hospital_address), SMALL),
                   P("FINAL BILL" + (" (PATIENT COPY - REPRINT)" if copy else ""), H2),
                   kv_table([("Invoice Number", s.invoice_no), ("Bill Date", fmt_date(s.bill_date))]),
                   Spacer(1, 5), patient_block(s), Spacer(1, 6)]
    rows = [[P("Particulars", CELLB), P("Amount (Rs.)", RIGHTB)]]
    for label, idx in s.summary:
        rows.append([P(x(label), CELL), P(f"{inr(sum(s.lines[i].amount for i in idx))}.00", RIGHT)])
    story += [grid(rows, [120 * mm, 50 * mm]), Spacer(1, 6), P(f"<b>TOTAL PAYABLE: {rs(s.total)}</b>", BODY),
              P(f"Amount in words: Rupees {words(s.total)} Only", CELL)]
    if copy:
        again = fmt_date(s.bill_date + timedelta(days=1))
        story += [Spacer(1, 6), P(f"Printed again at patient request on {again} (duplicate print of the same invoice).", SMALL)]
    build_pdf(path, "Final bill" + (" (copy)" if copy else ""), story)


def make_itemised_bill(s: Scenario, path: Path) -> None:
    story: list = [P(x(s.hospital), H1), P("ITEMISED BILL", H2),
                   kv_table([("Invoice Number", s.invoice_no), ("Bill Date", fmt_date(s.bill_date))]),
                   Spacer(1, 5), patient_block(s), Spacer(1, 6)]
    rows = [[P("#", CELLB), P("Description", CELLB), P("Qty", RIGHTB), P("Rate", RIGHTB), P("Amount (Rs.)", RIGHTB)]]
    for n, l in enumerate(s.lines, 1):
        rows.append([P(str(n), CELL), P(x(l.description), CELL), P(str(l.qty), RIGHT), P(inr(l.rate), RIGHT), P(f"{inr(l.amount)}.00", RIGHT)])
    story += [grid(rows, [10 * mm, 85 * mm, 15 * mm, 25 * mm, 35 * mm]), Spacer(1, 6), P(f"<b>GRAND TOTAL: {rs(s.total)}</b>", BODY)]
    build_pdf(path, "Itemised bill", story)


def make_discharge_summary(s: Scenario, path: Path) -> None:
    proc = f"{s.procedure} performed on {fmt_date(s.surgery)}" if s.surgery else s.procedure
    medication = (f"As per prescription no. {s.rx_no} dated {fmt_date(s.discharge)} (copy to be attached with the claim documents)."
                  if s.rx_referenced else "No take-home medication was prescribed.")
    story: list = [P(x(s.hospital), H1), P("DISCHARGE SUMMARY", H2), patient_block(s), Spacer(1, 6),
        P(f"<b>Diagnosis:</b> {x(s.diagnosis)}"), P(f"<b>Procedure:</b> {x(proc)}"),
        P(f"<b>Course in hospital:</b> {x(s.course_text)}"), P(f"<b>Condition at discharge:</b> {x(s.condition_text)}"),
        P(f"<b>Discharge medication:</b> {medication}"), P(f"<b>Follow-up:</b> {x(s.follow_up)}"), Spacer(1, 10),
        P(f"{x(s.doctor)}, {x(s.doctor_role)} | Reg. No. {x(s.doctor_reg)}")]
    build_pdf(path, "Discharge summary", story)


def make_receipt(s: Scenario, path: Path) -> None:
    story: list = [P(x(s.hospital), H1), P("PAYMENT RECEIPT", H2),
        kv_table([("Receipt Number", s.receipt_no), ("Receipt Date", fmt_date(s.bill_date)), ("Received from", s.receipt_display_name),
                  ("Towards Invoice", s.invoice_no), ("Mode of payment", s.receipt_mode)]),
        Spacer(1, 8), P(f"<b>AMOUNT RECEIVED: {rs(s.total)}</b>")]
    build_pdf(path, "Payment receipt", story)


def make_prescription(s: Scenario, path: Path) -> None:
    story: list = [P(x(s.hospital), H1), P(f"PRESCRIPTION - No. {s.rx_no}", H2),
        kv_table([("Patient Name", s.patient), ("Age / Sex", f"{s.age} / {s.sex}"), ("UHID", s.uhid),
                  ("Prescription Date", fmt_date(s.discharge)), ("Diagnosis", s.diagnosis)]),
        Spacer(1, 8), P("<b>Rx</b>")]
    story += [P(f"{i}. {x(item)}") for i, item in enumerate(s.rx_items, 1)]
    story += [Spacer(1, 10), P(f"{x(s.doctor)}, {x(s.doctor_role)} | Reg. No. {x(s.doctor_reg)}")]
    build_pdf(path, "Prescription", story)
