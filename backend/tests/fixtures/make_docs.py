"""Generate a small synthetic claim (test fixture only; the demo set lives in sample_documents/).

Planted issues (mirrors demo claim B): bill total 85,000 vs claimed 95,000; discharge summary refers to a
prescription that is not included; room rent 6,000/day vs a 1%-of-SI cap (5,000/day); patient name
spelled differently on the bill.

    python -m tests.fixtures.make_docs <out_dir>
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

POLICY_P1 = """SECURECARE HEALTH INSURANCE - POLICY SCHEDULE
Insurer: SecureCare General Insurance Ltd (synthetic)
Policy Number: SCH-2025-0042871
Policyholder Name: Rajesh Kumar
Member ID: MEM-778812
Policy Start Date: 01/04/2025
Policy End Date: 31/03/2026
Sum Insured: Rs. 5,00,000

1. Coverage
In-patient hospitalisation expenses are covered when admission is for at least 24 hours.
Pre-hospitalisation medical expenses are covered for 30 days before admission.
Post-hospitalisation medical expenses are covered for 60 days after discharge.

2. Room Rent Limit
Room rent, boarding and nursing charges are limited to 1% of the Sum Insured per day.
If the room rent exceeds this limit, associated medical expenses will be paid in the same proportion.
"""

POLICY_P2 = """3. Waiting Periods
3.1 Initial waiting period: Claims arising within the first 30 days from the policy start date are not payable, except accidents.
3.2 Pre-existing diseases are covered only after a waiting period of 36 months of continuous coverage.
3.3 Specified illnesses such as cataract and hernia have a waiting period of 24 months.

4. Exclusions
The following are not covered:
- Cosmetic or aesthetic treatment
- Dental treatment unless arising from an accident
- Non-medical items such as toiletries and attendant charges

5. Claim Documents
For reimbursement claims the insured person must submit the original final bill, itemised bill,
discharge summary, payment receipts, prescriptions and investigation reports within 30 days of discharge.

6. Co-payment
A co-payment of 10% applies to every admissible claim.
"""

BILL = """CITY CARE HOSPITAL - FINAL BILL
Hospital Name: City Care Hospital, Pune
Bill No: CCH/IP/2025/1189
Bill Date: 15/09/2025
Patient Name: Rajesh Kumaar
Age: 46
Policy No: SCH-2025-0042871
Date of Admission: 10/09/2025
Date of Discharge: 14/09/2025

Room Rent (4 days @ Rs. 6,000/day)   24,000
Doctor Consultation   12,000
Surgery Charges   35,000
Pharmacy   9,000
Laboratory Investigations   5,000

Total Payable: Rs. 85,000
"""

DISCHARGE = """CITY CARE HOSPITAL - DISCHARGE SUMMARY
Patient Name: Rajesh Kumar
Age: 46
Date of Admission: 10/09/2025
Date of Discharge: 14/09/2025
Final Diagnosis: Acute appendicitis
Treatment: Laparoscopic appendectomy

Course in hospital: Uneventful recovery after surgery.
Discharge medication as per the attached prescription.
Advice: Review after 7 days.
"""

RECEIPT = """CITY CARE HOSPITAL - PAYMENT RECEIPT
Patient Name: Rajesh Kumar
Bill No: CCH/IP/2025/1189
Amount Received: Rs. 85,000
Receipt Date: 15/09/2025
Payment Mode: UPI
"""


def _pdf(path: Path, pages: list[str]) -> Path:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_text((50, 60), text, fontsize=10)
    doc.save(path)
    doc.close()
    return path


def make_claim(out: Path) -> dict[str, Path]:
    out.mkdir(parents=True, exist_ok=True)
    return {
        "policy": _pdf(out / "policy_schedule.pdf", [POLICY_P1, POLICY_P2]),
        "final_bill": _pdf(out / "final_bill.pdf", [BILL]),
        "discharge_summary": _pdf(out / "discharge_summary.pdf", [DISCHARGE]),
        "payment_receipt": _pdf(out / "payment_receipt.pdf", [RECEIPT]),
    }


if __name__ == "__main__":
    paths = make_claim(Path(sys.argv[1] if len(sys.argv) > 1 else "synthetic_claim"))
    for k, p in paths.items():
        print(k, p)
