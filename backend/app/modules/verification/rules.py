"""Cross-document verification rules (Build Guide catalogue V1-V14, Core subset).

Every rule is deterministic Python (invariant I4). Each finding records the rule id and the
inputs it compared, carries evidence from BOTH sides of the comparison (I1), and is marked
`confirmed` (hard mismatch) or `possible` (needs a human) (I5). Wording is "to review":
never "fraud", never an approval/rejection prediction.

Implemented here: V1, V2, V3, V4, V5, V7, V14.
Later phases: V10 and V11 (need the policy summary), V8, V12, V6, V9, V13.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Callable

from app.schemas.contract import (
    ClaimInput,
    DocumentInfo,
    EvidenceRef,
    Explanation,
    ExtractedField,
    Finding,
    FindingKind,
    Severity,
)

from .helpers import compare_names, money, name_tokens, norm_id, parse_amount, parse_date

CRITICAL_KEYS = {
    "patient_name", "policy_number", "member_id", "admission_date", "discharge_date",
    "bill_total", "bill_number", "receipt_amount", "sum_insured", "policy_start", "policy_end",
    "room_rent_cap", "diagnosis_date",
}
LOW_CONFIDENCE = 0.75

REQUIRED_DOCS = {
    "reimbursement": ["policy", "final_bill", "itemised_bill", "discharge_summary", "payment_receipt"],
    "cashless": ["policy", "final_bill", "itemised_bill", "discharge_summary"],
}
DOC_LABEL = {
    "policy": "policy", "final_bill": "final bill", "itemised_bill": "itemised bill",
    "discharge_summary": "discharge summary", "payment_receipt": "payment receipt",
    "prescription": "prescription", "diagnostic_report": "diagnostic report",
}
RULE_NAME = {
    "V1": "Duplicate bill check", "V2": "Patient identity check", "V3": "Policy number / member ID check",
    "V4": "Amount check", "V5": "Date logic check", "V7": "Required and referenced documents check",
    "V14": "Extraction confidence check",
}


@dataclass
class Passed:
    rule_id: str
    text: str


@dataclass
class Ctx:
    fields: list[ExtractedField]
    documents: list[DocumentInfo]
    claim: ClaimInput
    findings: list[Finding] = field(default_factory=list)
    passed: list[Passed] = field(default_factory=list)
    _counter: Counter = field(default_factory=Counter)

    def __post_init__(self) -> None:
        self.doc_by_id = {d.id: d for d in self.documents}

    # ---- lookups
    def of(self, key: str) -> list[ExtractedField]:
        return [f for f in self.fields if f.key == key and f.value is not None]

    def doc_type(self, f: ExtractedField) -> str | None:
        doc = self.doc_by_id.get(f.evidence.document_id or "")
        return doc.doc_type if doc else None

    def of_in(self, key: str, doc_type: str) -> list[ExtractedField]:
        return [f for f in self.of(key) if self.doc_type(f) == doc_type]

    def docs_of(self, doc_type: str) -> list[DocumentInfo]:
        return [d for d in self.documents if d.doc_type == doc_type]

    def filename(self, f: ExtractedField) -> str:
        return f.evidence.filename or "a document"

    # ---- output
    def add(
        self, rule_id: str, issue_type: str, severity: Severity, kind: FindingKind, blocking: bool,
        title: str, description: str, evidence: list[EvidenceRef], why: str,
        extracted: object = None, comparison: object = None, inputs: dict | None = None,
    ) -> None:
        self._counter[(rule_id, issue_type)] += 1
        n = self._counter[(rule_id, issue_type)]
        self.findings.append(
            Finding(
                id=f"{rule_id.lower()}-{issue_type}-{n}", rule_id=rule_id, issue_type=issue_type,
                severity=severity, kind=kind, blocking=blocking, title=title, description=description,
                evidence=evidence,
                extracted_value=None if extracted is None else str(extracted),
                comparison_value=None if comparison is None else str(comparison),
                explanation=Explanation(
                    rule=f"{rule_id} - {RULE_NAME[rule_id]}",
                    inputs=inputs or {"extracted_value": extracted, "comparison_value": comparison},
                    why_it_matters=why,
                ),
                requires_human_review=True,
            )
        )

    def ok(self, rule_id: str, text: str) -> None:
        self.passed.append(Passed(rule_id, text))


def claim_form_evidence(name: str, value: object) -> EvidenceRef:
    return EvidenceRef(source="claim_form", field=name, value=value)


# ----------------------------------------------------------------------------------------
# V1 - duplicate bill
# ----------------------------------------------------------------------------------------
def v1_duplicates(c: Ctx) -> None:
    why = "Submitting the same bill twice can cause confusion or delay, so it is worth keeping one copy."
    reported = False

    # identical files
    by_hash: dict[str, list[DocumentInfo]] = {}
    for d in c.documents:
        if d.sha256:
            by_hash.setdefault(d.sha256, []).append(d)
    for docs in by_hash.values():
        if len(docs) > 1:
            reported = True
            names = ", ".join(d.filename for d in docs)
            c.add(
                "V1", "duplicate_file", Severity.HIGH, FindingKind.CONFIRMED, True,
                "The same file was uploaded more than once",
                f"{names} are identical files.",
                [EvidenceRef(source="checklist", field="duplicate_file", value=[d.filename for d in docs])],
                why, inputs={"filenames": [d.filename for d in docs]},
            )

    # same invoice number in two documents of the same type (a final bill and its itemised bill legitimately share it)
    for doc_type in ("final_bill", "itemised_bill"):
        groups: dict[str, list[ExtractedField]] = {}
        for f in c.of_in("bill_number", doc_type):
            groups.setdefault(norm_id(f.value), []).append(f)
        for number, fs in groups.items():
            distinct_docs = {f.evidence.document_id for f in fs}
            if len(distinct_docs) > 1:
                reported = True
                label = DOC_LABEL[doc_type]
                c.add(
                    "V1", "duplicate_bill", Severity.HIGH, FindingKind.CONFIRMED, True,
                    "The same invoice appears in two uploaded files",
                    f"Invoice {fs[0].value} is in {', '.join(c.filename(f) for f in fs)}. Both are the {label}.",
                    [f.evidence for f in fs], why,
                    extracted=fs[0].value, comparison=fs[1].value,
                    inputs={"invoice_number": fs[0].value, "files": [c.filename(f) for f in fs]},
                )

    # same hospital + date + total under different invoice numbers -> possible duplicate
    finals = c.docs_of("final_bill")
    if len(finals) > 1:
        sigs: dict[tuple, list[str]] = {}
        for d in finals:
            def pick(key: str) -> ExtractedField | None:
                return next((f for f in c.of_in(key, "final_bill") if f.evidence.document_id == d.id), None)
            h, bd, bt, bn = pick("hospital_name"), pick("bill_date"), pick("bill_total"), pick("bill_number")
            if h and bd and bt:
                sigs.setdefault((str(h.value).lower().strip(), str(bd.value), parse_amount(bt.value)), []).append(d.id)
        for (hospital, bdate, total), ids in sigs.items():
            if len(ids) > 1:
                fs = [f for f in c.of_in("bill_total", "final_bill") if f.evidence.document_id in ids]
                numbers = {norm_id(f.value) for f in c.of_in("bill_number", "final_bill") if f.evidence.document_id in ids}
                if len(numbers) > 1:
                    reported = True
                    c.add(
                        "V1", "possible_duplicate_bill", Severity.MEDIUM, FindingKind.POSSIBLE, False,
                        "Two bills look alike (same hospital, date and amount)",
                        f"Two final bills from {hospital} dated {bdate} both total {money(total)} but have different invoice numbers.",
                        [f.evidence for f in fs], why, extracted=money(total),
                        inputs={"hospital": hospital, "bill_date": bdate, "total": total},
                    )
    if not reported and (len(c.documents) > 1):
        c.ok("V1", "No duplicate files or repeated invoices found")


# ----------------------------------------------------------------------------------------
# V2 - patient identity
# ----------------------------------------------------------------------------------------
def v2_patient_identity(c: Ctx) -> None:
    names = c.of("patient_name")
    if not names:
        return
    if c.claim.patient_name:
        ref_name, ref_ev = c.claim.patient_name, claim_form_evidence("patient_name", c.claim.patient_name)
    else:
        def key(f: ExtractedField) -> str:
            return " ".join(sorted(name_tokens(f.value)))

        top = Counter(key(f) for f in names).most_common(1)[0][0]
        ref_field = next(f for f in names if key(f) == top)
        ref_name, ref_ev = ref_field.value, ref_field.evidence

    differing: dict[str, list[ExtractedField]] = {}
    outcomes: dict[str, str] = {}
    for f in names:
        verdict = compare_names(f.value, ref_name)
        if verdict != "same":
            differing.setdefault(str(f.value), []).append(f)
            outcomes[str(f.value)] = verdict
    if not differing and (len(names) > 1 or c.claim.patient_name):
        c.ok("V2", "Patient name is consistent across the documents")
    for value, fs in differing.items():
        confirmed = outcomes[value] == "different"
        c.add(
            "V2", "name_mismatch" if confirmed else "name_variant",
            Severity.HIGH if confirmed else Severity.LOW,
            FindingKind.CONFIRMED if confirmed else FindingKind.POSSIBLE, confirmed,
            "Patient name differs between documents" if confirmed else "Patient name is written differently on one document",
            f"'{value}' in {c.filename(fs[0])} does not match '{ref_name}'." if confirmed
            else f"'{value}' in {c.filename(fs[0])} looks like a spelling or initial variation of '{ref_name}'.",
            [fs[0].evidence, ref_ev],
            "Names that differ between documents may need to be explained to the insurer.",
            extracted=value, comparison=ref_name,
            inputs={"compared": [value, ref_name], "result": outcomes[value]},
        )


# ----------------------------------------------------------------------------------------
# V3 - policy number / member ID
# ----------------------------------------------------------------------------------------
def v3_policy_ids(c: Ctx) -> None:
    compared = 0
    clean = True
    for key, label in (("policy_number", "Policy number"), ("member_id", "Member ID")):
        fs = c.of(key)
        if len({f.evidence.document_id for f in fs}) < 2:
            continue
        compared += 1
        ref = next((f for f in fs if c.doc_type(f) == "policy"), None)
        if ref is None:
            top = Counter(norm_id(f.value) for f in fs).most_common(1)[0][0]
            ref = next(f for f in fs if norm_id(f.value) == top)
        for f in fs:
            if norm_id(f.value) != norm_id(ref.value):
                clean = False
                c.add(
                    "V3", f"{key}_mismatch", Severity.HIGH, FindingKind.CONFIRMED, True,
                    f"{label} differs between documents",
                    f"{label} '{f.value}' in {c.filename(f)} does not match '{ref.value}' in {c.filename(ref)}.",
                    [f.evidence, ref.evidence],
                    "A policy or member number that does not match the policy is a common reason for a claim query.",
                    extracted=f.value, comparison=ref.value,
                    inputs={"field": key, "values": [f.value, ref.value]},
                )
    if compared and clean:
        c.ok("V3", "Policy number and member ID agree across the documents")


# ----------------------------------------------------------------------------------------
# V4 - amounts
# ----------------------------------------------------------------------------------------
def _bill_total(c: Ctx) -> ExtractedField | None:
    return next(iter(c.of_in("bill_total", "final_bill")), None) or next(iter(c.of("bill_total")), None)


def v4_amounts(c: Ctx) -> None:
    total_field = _bill_total(c)
    total = parse_amount(total_field.value) if total_field else None

    # (a) bill total vs the amount the user is claiming
    if total is not None and c.claim.claimed_amount is not None:
        claimed = float(c.claim.claimed_amount)
        if abs(claimed - total) > 0.5:
            over = claimed > total
            c.add(
                "V4", "amount_mismatch", Severity.MEDIUM,
                FindingKind.CONFIRMED if over else FindingKind.POSSIBLE, over,
                "Bill total differs from the amount you are claiming",
                f"The bill total is {money(total)} but the claimed amount is {money(claimed)}."
                + ("" if over else " Claiming less than the bill is fine if that is intentional."),
                [total_field.evidence, claim_form_evidence("claimed_amount", claimed)],
                "A claimed amount that does not match the bill is a common reason for queries.",
                extracted=money(total), comparison=money(claimed),
                inputs={"bill_total": total, "claimed_amount": claimed},
            )
        else:
            c.ok("V4", f"Bill total matches the claimed amount ({money(total)})")

    # (b) line items vs bill total
    items = [(f, parse_amount(f.value)) for f in c.of("line_item")]
    items = [(f, a) for f, a in items if a is not None]
    if items and total is not None:
        s = sum(a for _, a in items)
        if abs(s - total) > 1.0:
            c.add(
                "V4", "line_items_mismatch", Severity.HIGH, FindingKind.CONFIRMED, True,
                "Line items do not add up to the bill total",
                f"The itemised lines add up to {money(s)} but the bill total is {money(total)}.",
                [total_field.evidence, items[0][0].evidence],
                "Arithmetic differences inside a bill can lead to the bill being questioned.",
                extracted=money(s), comparison=money(total),
                inputs={"line_items_sum": s, "bill_total": total, "line_count": len(items)},
            )
        else:
            c.ok("V4", f"Line items add up to the bill total ({money(total)})")

    # (c) amount paid vs bill total
    receipts = c.of("receipt_amount")
    paid = [parse_amount(f.value) for f in receipts]
    if receipts and total is not None and all(p is not None for p in paid):
        s = sum(paid)  # type: ignore[arg-type]
        if abs(s - total) > 0.5:
            c.add(
                "V4", "receipt_amount_mismatch", Severity.MEDIUM, FindingKind.POSSIBLE, False,
                "Amount paid differs from the bill total",
                f"Receipts add up to {money(s)} while the bill total is {money(total)}.",
                [receipts[0].evidence, total_field.evidence],
                "Payment receipts are expected to support the amount being claimed.",
                extracted=money(s), comparison=money(total),
                inputs={"receipts_sum": s, "bill_total": total},
            )
        else:
            c.ok("V4", "Receipt amount equals the bill total")


# ----------------------------------------------------------------------------------------
# V5 - date logic
# ----------------------------------------------------------------------------------------
def _primary_date(c: Ctx, key: str) -> tuple[ExtractedField, object] | None:
    fs = [(f, parse_date(f.value)) for f in c.of(key)]
    fs = [(f, d) for f, d in fs if d is not None]
    if not fs:
        return None
    pref = next(((f, d) for f, d in fs if c.doc_type(f) == "discharge_summary"), None)
    return pref or fs[0]


def v5_dates(c: Ctx) -> None:
    # the same date written differently in two documents
    for key, label in (("admission_date", "Admission date"), ("discharge_date", "Discharge date")):
        parsed = [(f, parse_date(f.value)) for f in c.of(key)]
        parsed = [(f, d) for f, d in parsed if d]
        if len({d for _, d in parsed}) > 1:
            (f1, d1), (f2, d2) = parsed[0], next(p for p in parsed if p[1] != parsed[0][1])
            c.add(
                "V5", f"{key}_conflict", Severity.HIGH, FindingKind.CONFIRMED, True,
                f"{label} differs between documents",
                f"{c.filename(f1)} says {d1.isoformat()} but {c.filename(f2)} says {d2.isoformat()}.",
                [f1.evidence, f2.evidence],
                "Dates that disagree between documents are a common reason for a claim query.",
                extracted=d1.isoformat(), comparison=d2.isoformat(), inputs={"field": key, "dates": [d1.isoformat(), d2.isoformat()]},
            )

    adm, dis = _primary_date(c, "admission_date"), _primary_date(c, "discharge_date")
    if adm and dis:
        if adm[1] > dis[1]:  # type: ignore[operator]
            c.add(
                "V5", "admission_after_discharge", Severity.HIGH, FindingKind.CONFIRMED, True,
                "Admission date is after the discharge date",
                f"Admitted {adm[1].isoformat()} but discharged {dis[1].isoformat()}.",  # type: ignore[union-attr]
                [adm[0].evidence, dis[0].evidence],
                "Admission must come before discharge for the dates to make sense.",
                extracted=adm[1].isoformat(), comparison=dis[1].isoformat(),  # type: ignore[union-attr]
                inputs={"admission": adm[1].isoformat(), "discharge": dis[1].isoformat()},  # type: ignore[union-attr]
            )
        else:
            c.ok("V5", "Admission date is not after the discharge date")

        start, end = _primary_date(c, "policy_start"), _primary_date(c, "policy_end")
        if start and end:
            if adm[1] < start[1] or dis[1] > end[1]:  # type: ignore[operator]
                c.add(
                    "V5", "treatment_outside_policy_period", Severity.HIGH, FindingKind.CONFIRMED, True,
                    "Treatment dates fall outside the policy period",
                    f"The stay ({adm[1].isoformat()} to {dis[1].isoformat()}) is not inside the policy period "  # type: ignore[union-attr]
                    f"({start[1].isoformat()} to {end[1].isoformat()}).",  # type: ignore[union-attr]
                    [adm[0].evidence, start[0].evidence],
                    "A policy only responds to treatment within its period; please check the policy dates.",
                    extracted=f"{adm[1].isoformat()}..{dis[1].isoformat()}",  # type: ignore[union-attr]
                    comparison=f"{start[1].isoformat()}..{end[1].isoformat()}",  # type: ignore[union-attr]
                    inputs={"admission": adm[1].isoformat(), "discharge": dis[1].isoformat(),  # type: ignore[union-attr]
                            "policy_start": start[1].isoformat(), "policy_end": end[1].isoformat()},  # type: ignore[union-attr]
                )
            else:
                c.ok("V5", "Admission and discharge fall inside the policy period")

        # final bill dated before the patient left
        for f in c.of_in("bill_date", "final_bill"):
            d = parse_date(f.value)
            if d and d < dis[1]:  # type: ignore[operator]
                c.add(
                    "V5", "bill_dated_before_discharge", Severity.LOW, FindingKind.POSSIBLE, False,
                    "Final bill is dated before the discharge date",
                    f"The final bill is dated {d.isoformat()} but discharge was {dis[1].isoformat()}.",  # type: ignore[union-attr]
                    [f.evidence, dis[0].evidence],
                    "A final bill is normally issued on or after discharge.",
                    extracted=d.isoformat(), comparison=dis[1].isoformat(),  # type: ignore[union-attr]
                    inputs={"bill_date": d.isoformat(), "discharge": dis[1].isoformat()},  # type: ignore[union-attr]
                )


# ----------------------------------------------------------------------------------------
# V7 - required and referenced documents
# ----------------------------------------------------------------------------------------
_REFERENCE_TYPES = [
    ("prescription", "prescription"), ("discharge", "discharge_summary"), ("receipt", "payment_receipt"),
    ("itemised", "itemised_bill"), ("diagnostic", "diagnostic_report"), ("report", "diagnostic_report"),
    ("lab", "diagnostic_report"), ("ultrasound", "diagnostic_report"), ("scan", "diagnostic_report"),
    ("x-ray", "diagnostic_report"), ("xray", "diagnostic_report"), ("mri", "diagnostic_report"),
]


def _reference_type(text: str) -> str | None:
    t = text.lower()
    return next((doc_type for needle, doc_type in _REFERENCE_TYPES if needle in t), None)


def v7_documents(c: Ctx) -> None:
    present = {d.doc_type for d in c.documents}
    required = REQUIRED_DOCS.get(c.claim.claim_type, REQUIRED_DOCS["reimbursement"])
    missing = [t for t in required if t not in present]
    for t in missing:
        label = DOC_LABEL[t]
        c.add(
            "V7", "missing_required_document", Severity.HIGH, FindingKind.CONFIRMED, True,
            f"A required document is missing: {label}",
            f"A {c.claim.claim_type} claim normally needs the {label}, and none was uploaded.",
            [EvidenceRef(source="checklist", field=t, value="missing")],
            "Missing documents are one of the most common causes of delay.",
            inputs={"claim_type": c.claim.claim_type, "required": required, "present": sorted(present)},
        )
    if not missing and c.documents:
        names = ", ".join(DOC_LABEL[t] for t in required)
        c.ok("V7", f"All required documents for a {c.claim.claim_type} claim are present ({names})")

    refs: dict[str, list[ExtractedField]] = {}
    for f in c.of("referenced_document"):
        t = _reference_type(str(f.value))
        if t and t not in present:
            refs.setdefault(t, []).append(f)
    for t, fs in refs.items():
        label = DOC_LABEL.get(t, t)
        c.add(
            "V7", "referenced_document_missing", Severity.HIGH, FindingKind.CONFIRMED, True,
            f"{c.filename(fs[0])} refers to a {label} that was not uploaded",
            f"{c.filename(fs[0])} mentions '{fs[0].value}', but no {label} was uploaded.",
            [f.evidence for f in fs],
            "Documents that other documents refer to are usually expected to be submitted too.",
            extracted=fs[0].value, inputs={"referenced": [f.value for f in fs], "missing_type": t},
        )


# ----------------------------------------------------------------------------------------
# V14 - low-confidence critical fields
# ----------------------------------------------------------------------------------------
def v14_confidence(c: Ctx) -> None:
    for f in c.fields:
        if f.key in CRITICAL_KEYS and f.confidence < LOW_CONFIDENCE and not f.user_confirmed:
            c.add(
                "V14", "low_confidence_field", Severity.LOW, FindingKind.POSSIBLE, False,
                f"Please confirm the {f.key.replace('_', ' ')}",
                f"The value '{f.value}' in {c.filename(f)} was read with low confidence ({f.confidence:.2f}).",
                [f.evidence],
                "Checks that depend on this value are only as reliable as how well it was read.",
                extracted=f.value, inputs={"field": f.key, "confidence": f.confidence, "threshold": LOW_CONFIDENCE},
            )


RULES: list[Callable[[Ctx], None]] = [
    v1_duplicates, v2_patient_identity, v3_policy_ids, v4_amounts, v5_dates, v7_documents, v14_confidence,
]
