"""The synthetic claims, as data. Everything here is fictional.

  A  clean claim: every document agrees, nothing should be flagged (the false-alarm test)
  B  the hero demo: amount mismatch, duplicate bill, missing prescription, room rent above the limit, name variant
  C  a treatment inside the policy's waiting period (cataract surgery 18 days after a new policy began)
"""

from __future__ import annotations

from datetime import date

from .scenario import Line, Scenario

INSURER = "Sample Shield Health Insurance Co. Ltd."
PRODUCT = "Sample Shield Care Plus (Individual Mediclaim)"
SPECIFIED = ["cataract", "hernia", "hysterectomy", "joint replacement"]
COMMON_EXCLUSIONS = [
    ("Cosmetic Treatment", "Cosmetic or plastic surgery unless required after an accident or cancer."),
    ("Dental Treatment", "Dental treatment unless arising from an accident."),
    ("Non-medical Expenses", "Items listed as non-medical in Annexure A (for example, admission kits and toiletries)."),
]


def claim_b() -> Scenario:
    return Scenario(
        key="b", title="Hero demo claim: amount mismatch, duplicate bill, missing prescription, room rent above cap",
        insurer=INSURER, product=PRODUCT, policy_no="SSH-2026-004567", member_id="M-889201", patient="Ravi Kumar Sharma",
        salutation="Mr.", age=42, sex="Male", inception=date(2024, 4, 1), period_start=date(2026, 4, 1), period_end=date(2027, 3, 31),
        sum_insured=500000, specified_conditions=SPECIFIED, exclusions=COMMON_EXCLUSIONS,
        definition_included="nursing charges, surgeon and anaesthetist fees, operation theatre charges and surgical consumables",
        definition_excluded="Medicines, diagnostics and registration charges",
        hospital="Demo City Care Hospital", hospital_address="12 Demo Road, Sample City - 000000 | Reg. No. DEMO/HOSP/0001",
        uhid="DCC-55231", invoice_no="INV-2026-08-10457", bill_date=date(2026, 8, 15), admission=date(2026, 8, 12),
        discharge=date(2026, 8, 15), surgery=date(2026, 8, 13), diagnosis="Acute appendicitis", procedure="Laparoscopic appendectomy",
        course_text=("The patient was admitted with right lower abdominal pain. Investigations supported the diagnosis and surgery "
                     "was performed under general anaesthesia. Recovery was uneventful."),
        follow_up="Review in the surgical outpatient department after 7 days.", doctor="Dr. Anil Menon", doctor_role="Consultant Surgeon",
        doctor_reg="DEMO-MC-12345", rx_no="RX-7781",
        rx_items=["Tab Amoxicillin-Clavulanate 625 mg - twice daily for 5 days", "Tab Paracetamol 650 mg - when required for pain",
                  "Tab Pantoprazole 40 mg - once daily before breakfast for 5 days"],
        receipt_no="RCPT-88231",
        lines=[Line("Room rent - private single room", 3, 7500), Line("Nursing charges", 3, 1200, True), Line("Surgeon fee", 1, 18000, True),
               Line("Anaesthetist fee", 1, 6000, True), Line("Operation theatre charges", 1, 12000, True),
               Line("Laparoscopic surgical consumables", 1, 9500, True), Line("Medicines and pharmacy", 1, 7400),
               Line("Diagnostics (lab and ultrasound)", 1, 5000), Line("Registration and miscellaneous", 1, 1000)],
        summary=[("Room rent and nursing", [0, 1]), ("Professional fees (surgeon, anaesthetist)", [2, 3]), ("Operation theatre charges", [4]),
                 ("Surgical consumables", [5]), ("Medicines and pharmacy", [6]), ("Diagnostics", [7]), ("Registration and miscellaneous", [8])],
        claimed_amount=95000, receipt_name="Ravi K Sharma", duplicate_bill=True, rx_referenced=True, rx_uploaded=False,
    )


def claim_a() -> Scenario:
    return Scenario(
        key="a", title="Clean claim: every document agrees, nothing should be flagged",
        insurer=INSURER, product=PRODUCT, policy_no="SSH-2026-007812", member_id="M-440117", patient="Anita Verma", salutation="Ms.",
        age=36, sex="Female", inception=date(2023, 6, 15), period_start=date(2026, 6, 15), period_end=date(2027, 6, 14),
        sum_insured=300000, specified_conditions=["cataract", "hernia", "knee replacement"], exclusions=COMMON_EXCLUSIONS[:2],
        definition_included="nursing charges and doctor visit fees",
        definition_excluded="Medicines, investigations and registration fees",
        hospital="Lakeview General Hospital", hospital_address="48 Lake Road, Sample City - 000000 | Reg. No. DEMO/HOSP/0002",
        uhid="LGH-30918", invoice_no="LGH-2026-09-22031", bill_date=date(2026, 9, 8), admission=date(2026, 9, 5), discharge=date(2026, 9, 8),
        diagnosis="Acute gastroenteritis with dehydration", procedure="Medical management with intravenous fluids",
        course_text=("The patient presented with vomiting and loose stools. She was rehydrated with intravenous fluids and monitored. "
                     "Symptoms resolved and oral intake was restored."),
        condition_text="Stable, tolerating oral diet.", follow_up="Review with the physician after 5 days if symptoms recur.",
        doctor="Dr. Rekha Iyer", doctor_role="Consultant Physician", doctor_reg="DEMO-MC-23456", rx_no="RX-3302",
        rx_items=["Tab Ondansetron 4 mg - when required for nausea", "Oral rehydration salts - after each loose stool for 3 days",
                  "Probiotic capsule - once daily for 5 days"],
        receipt_no="RCPT-45512", receipt_mode="Card",
        lines=[Line("Room rent - semi-private room", 3, 2800), Line("Nursing charges", 3, 900, True),
               Line("Doctor visits (daily consultation)", 3, 1500, True), Line("IV fluids and medicines", 1, 9800),
               Line("Investigations (blood tests)", 1, 6400), Line("Registration fee", 1, 500)],
        summary=[("Room rent and nursing", [0, 1]), ("Doctor visits", [2]), ("Medicines and fluids", [3]), ("Investigations", [4]), ("Registration", [5])],
        claimed_amount=32300, rx_referenced=True, rx_uploaded=True,
    )


def claim_c() -> Scenario:
    return Scenario(
        key="c", title="Treatment inside the waiting period: cataract surgery 18 days after a new policy began",
        insurer=INSURER, product=PRODUCT, policy_no="SSH-2026-011934", member_id="M-512208", patient="Kiran Reddy", salutation="Mr.",
        age=58, sex="Male", inception=date(2026, 7, 25), period_start=date(2026, 7, 25), period_end=date(2027, 7, 24),
        sum_insured=400000, specified_conditions=SPECIFIED, exclusions=COMMON_EXCLUSIONS,
        definition_included="nursing charges, surgeon and anaesthetist fees and operation theatre charges",
        definition_excluded="Implants, medicines, diagnostics and registration charges",
        hospital="Harbour Eye and Surgical Centre", hospital_address="7 Harbour Lane, Sample City - 000000 | Reg. No. DEMO/HOSP/0003",
        uhid="HES-77120", invoice_no="HES-2026-08-04418", bill_date=date(2026, 8, 13), admission=date(2026, 8, 12), discharge=date(2026, 8, 13),
        surgery=date(2026, 8, 12), diagnosis="Cataract, right eye", procedure="Phacoemulsification with intraocular lens implant",
        course_text=("The patient presented with gradual loss of vision in the right eye. Cataract surgery was performed under local "
                     "anaesthesia. The post-operative period was uneventful."),
        condition_text="Stable, vision improving, eye comfortable.", follow_up="Review in the eye clinic after 1 week.",
        doctor="Dr. Sunita Rao", doctor_role="Consultant Ophthalmologist", doctor_reg="DEMO-MC-34567", rx_no="RX-5120",
        rx_items=["Moxifloxacin eye drops - four times daily for 7 days", "Prednisolone eye drops - tapering dose over 4 weeks",
                  "Lubricant eye drops - as required"],
        receipt_no="RCPT-61804", receipt_mode="UPI",
        lines=[Line("Room rent - day-care ward", 1, 3500), Line("Nursing charges", 1, 800, True), Line("Surgeon fee", 1, 22000, True),
               Line("Anaesthetist fee", 1, 4000, True), Line("Operation theatre charges", 1, 9000, True),
               Line("Intraocular lens (implant)", 1, 12000), Line("Medicines and eye drops", 1, 3200),
               Line("Diagnostics (eye scans)", 1, 2500), Line("Registration and miscellaneous", 1, 800)],
        summary=[("Room rent and nursing", [0, 1]), ("Professional fees (surgeon, anaesthetist)", [2, 3]), ("Operation theatre charges", [4]),
                 ("Intraocular lens", [5]), ("Medicines", [6]), ("Diagnostics", [7]), ("Registration and miscellaneous", [8])],
        claimed_amount=57800, rx_referenced=True, rx_uploaded=True,
    )


SCENARIOS = {"a": claim_a, "b": claim_b, "c": claim_c}
