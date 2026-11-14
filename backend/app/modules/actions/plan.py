"""explain_plan: structured findings + clauses + checklist -> ordered, owned, grounded actions.

Input is structured data only (never raw documents), so every action names real values (I3).
Deterministic templates keep amounts, dates and IDs exact; nothing here can invent a value.
"""

from __future__ import annotations

import hashlib

from app.schemas.results import (
    Action,
    ChecklistItem,
    ExtractedField,
    Finding,
    PolicyClause,
    PolicySummary,
    ReadinessStatus,
    Severity,
)

OWNER_ORDER = {"user": 0, "hospital": 1, "doctor": 2, "insurer": 3}
HOSPITAL_DOCS = {"final_bill", "itemised_bill", "discharge_summary", "payment_receipt", "diagnostic_report"}

# rule_id -> (owner, group)
RULE_ROUTING: dict[str, tuple[str, str]] = {
    "V1": ("user", "verify_or_correct"), "V2": ("hospital", "verify_or_correct"),
    "V3": ("user", "verify_or_correct"), "V4": ("user", "verify_or_correct"),
    "V5": ("hospital", "verify_or_correct"), "V6": ("user", "policy_review"),
    "V7": ("hospital", "upload"), "V8": ("doctor", "verify_or_correct"),
    "V9": ("doctor", "verify_or_correct"), "V10": ("insurer", "ask_insurer"),
    "V11": ("insurer", "ask_insurer"), "V12": ("insurer", "ask_insurer"),
    "V13": ("hospital", "verify_or_correct"), "V14": ("user", "verify_or_correct"),
}


def _id(*parts: str) -> str:
    return "act-" + hashlib.sha1("|".join(parts).encode()).hexdigest()[:10]


def _field(fields: list[ExtractedField], key: str):
    f = next((f for f in fields if f.key == key and f.value not in (None, "")), None)
    return f.value if f else None


def _context(fields: list[ExtractedField]) -> dict[str, str]:
    def fmt(v):
        return str(v) if v not in (None, "") else None
    return {
        "patient": fmt(_field(fields, "patient_name")) or fmt(_field(fields, "policyholder_name")) or "the patient",
        "hospital": fmt(_field(fields, "hospital_name")) or "the hospital",
        "adm": fmt(_field(fields, "admission_date")) or "",
        "dis": fmt(_field(fields, "discharge_date")) or "",
        "policy": fmt(_field(fields, "policy_number")) or "",
        "bill": fmt(_field(fields, "bill_number")) or "",
    }


def _stay(ctx: dict[str, str]) -> str:
    if ctx["adm"] and ctx["dis"]:
        return f" (admitted {ctx['adm']}, discharged {ctx['dis']})"
    return f" (admitted {ctx['adm']})" if ctx["adm"] else ""


def _hospital_message(ctx: dict[str, str], request: str) -> str:
    ref = f" Bill no. {ctx['bill']}." if ctx["bill"] else ""
    return (f"Dear {ctx['hospital']} billing / medical records team,\n\n"
            f"I am preparing a health-insurance claim for {ctx['patient']}{_stay(ctx)}.{ref} "
            f"Could you please {request}?\n\nThank you.")


def _insurer_message(ctx: dict[str, str], question: str) -> str:
    pol = f" under policy {ctx['policy']}" if ctx["policy"] else ""
    return (f"Hello,\n\nI am preparing a claim{pol} for {ctx['patient']}{_stay(ctx)}. "
            f"{question}\n\nThank you.")


def checklist_actions(checklist: list[ChecklistItem], ctx: dict[str, str]) -> list[Action]:
    out: list[Action] = []
    for item in checklist:
        if not item.required or item.received:
            continue
        hospital = item.category in HOSPITAL_DOCS
        owner = "hospital" if hospital else ("doctor" if item.category == "prescription" else "user")
        how = [f"Upload the {item.label.lower()} to this claim and press Re-check."]
        if hospital or owner == "doctor":
            how.insert(0, f"Request a signed copy of the {item.label.lower()} from {ctx['hospital']}.")
        out.append(Action(
            id=_id("upload", item.category), title=f"Upload the {item.label.lower()}",
            why=f"{item.label} is missing. {item.reason}", how=how, owner=owner,  # type: ignore[arg-type]
            blocking=item.category in ("policy", "final_bill", "discharge_summary") or item.evidence is not None,
            group="upload", checklist_category=item.category,
            draft_message=_hospital_message(ctx, f"issue a signed copy of the {item.label.lower()}")
            if owner in ("hospital", "doctor") else None))
    return out


def finding_action(f: Finding, ctx: dict[str, str], clauses: dict[str, PolicyClause]) -> Action:
    owner, group = RULE_ROUTING.get(f.rule_id, ("user", "verify_or_correct"))
    ev = next((e for e in f.evidence if e.source == "document"), f.evidence[0])
    where = (f"{ev.filename}, page {ev.page_number}" if ev.source == "document"
             else "your claim form" if ev.source == "claim_form" else "the document checklist")
    vals = ""
    if f.extracted_value is not None and f.comparison_value is not None:
        vals = f" ({f.extracted_value} vs {f.comparison_value})"
    clause_ids = [c.clause_id for c in f.clause_links if c.clause_id in clauses]
    clause_txt = ""
    if clause_ids:
        c = clauses[clause_ids[0]]
        clause_txt = f" Policy clause {c.clause_ref} (page {c.page_number}) may be relevant."
    how: list[str] = [f"Open {where} and compare it with the value flagged{vals}."]
    msg = None
    title = f.title

    if f.rule_id == "V2":
        title = "Get the patient name corrected so it matches the policy"
        how = [f"Check the name on {where}{vals}.",
               "If it is a spelling difference, ask the hospital for a corrected document, "
               "or keep an ID proof ready that links both spellings."]
        msg = _hospital_message(ctx, f"correct the patient name on the document{vals} to match the insurance policy")
    elif f.rule_id == "V4":
        title = "Make the claimed amount match the bill total"
        how = [f"Check the total on {where}{vals}.",
               "If the bill is right, correct the claimed amount on your claim form; if not, ask the hospital "
               "for a corrected bill.", "Press Re-check after updating."]
    elif f.rule_id == "V1":
        title = "Remove the duplicate bill"
        how = [f"Keep one copy of the bill ({where}) and remove the duplicate upload.",
               "Submitting the same bill twice can trigger queries."]
    elif f.rule_id in ("V5", "V13"):
        msg = _hospital_message(ctx, f"check and re-issue the document with correct details{vals}")
    elif f.rule_id == "V7":
        msg = _hospital_message(ctx, "share the missing document mentioned in the discharge summary")
        how = [f"The document is referenced in {where} but was not uploaded.",
               "Request it and upload it, then press Re-check."]
    elif f.rule_id == "V10":
        title = "Ask the insurer about the room-rent limit"
        exp = f" Estimated exposure to review: ₹{f.exposure_amount:,.0f}." if f.exposure_amount else ""
        how = [f"Room rent on {where}{vals} is above the policy limit.{exp}",
               "Ask the insurer whether a proportionate deduction applies to related charges."]
        msg = _insurer_message(ctx, f"My room rent{vals} appears to be above the policy's room-rent limit. "
                                    "Could you confirm whether a proportionate deduction would apply, "
                                    "and to which charges?")
    elif f.rule_id == "V11":
        title = "Check the waiting period with the insurer"
        how = [f"The treatment date and policy start date on {where}{vals} fall inside a waiting period.",
               "Keep records showing when the condition was first diagnosed, and confirm with the insurer."]
        msg = _insurer_message(ctx, f"The treatment appears to fall within a waiting period{vals}. "
                                    "Could you confirm how the waiting period applies to this claim?")
    elif f.rule_id == "V12":
        how = [f"The treatment on {where} may match a policy exclusion or sub-limit.",
               "Read the clause and ask the insurer to confirm before you submit."]
        msg = _insurer_message(ctx, "Could you confirm whether the treatment is covered or falls under an "
                                    "exclusion or sub-limit in my policy?")
    elif f.rule_id == "V14":
        how = [f"Check the value on {where}{vals} and confirm or correct it in the Extracted data tab."]
    elif owner == "insurer":
        msg = _insurer_message(ctx, f"Could you help me understand this: {f.title}.")
    elif owner in ("hospital", "doctor"):
        msg = _hospital_message(ctx, f"help resolve this: {f.title.lower()}")

    return Action(
        id=_id("finding", f.rule_id, f.title, ev.document_id or ev.field or ""), title=title,
        why=f"{f.description}{clause_txt}", how=how, owner=owner,  # type: ignore[arg-type]
        blocking=f.blocking, group=group,  # type: ignore[arg-type]
        finding_ids=[f.id], clause_ids=clause_ids, draft_message=msg)


def build_plan(findings: list[Finding], checklist: list[ChecklistItem], fields: list[ExtractedField],
               clauses: list[PolicyClause], done: set[str] | None = None) -> list[Action]:
    ctx = _context(fields)
    by_id = {c.id: c for c in clauses}
    actions = checklist_actions(checklist, ctx)
    seen_upload = {a.checklist_category for a in actions}
    for f in findings:
        if f.status == "resolved":
            continue
        a = finding_action(f, ctx, by_id)
        # A V7 finding for a document the checklist already asks for: merge into that action.
        if f.rule_id == "V7":
            dup = next((x for x in actions if x.group == "upload" and x.checklist_category in seen_upload
                        and x.checklist_category and x.checklist_category.replace("_", " ") in f"{f.title} {f.description}".lower()), None)
            if dup:
                dup.finding_ids.append(f.id)
                dup.blocking = dup.blocking or f.blocking
                continue
        actions.append(a)
    done = done or set()
    for a in actions:
        a.done = a.id in done
    actions.sort(key=lambda a: (a.done, not a.blocking, OWNER_ORDER[a.owner]))
    return actions


def readiness(checklist: list[ChecklistItem], findings: list[Finding]) -> tuple[ReadinessStatus, str]:
    """Decision D3 (code, not LLM)."""
    missing_core = [c.label for c in checklist if c.category in ("policy", "final_bill") and not c.received]
    if missing_core:
        return ReadinessStatus.INCOMPLETE, f"Missing: {', '.join(missing_core)}. Covara cannot check the claim without them."
    open_f = [f for f in findings if f.status == "open"]
    blocking = [f for f in open_f if f.blocking or f.severity in (Severity.MEDIUM, Severity.HIGH)]
    missing = [c.label for c in checklist if c.required and not c.received]
    if blocking or missing:
        parts = []
        if blocking:
            parts.append(f"{len(blocking)} issue{'s' if len(blocking) != 1 else ''} to review")
        if missing:
            parts.append(f"{len(missing)} required document{'s' if len(missing) != 1 else ''} missing ({', '.join(missing)})")
        return ReadinessStatus.NEEDS_ATTENTION, "; ".join(parts).capitalize() + "."
    return ReadinessStatus.READY, ("All required documents are present and no blocking issues were found. "
                                   "This is a preparation check, not an insurer decision.")


def summary_is_empty(s: PolicySummary | None) -> bool:
    return s is None or not any([s.sum_insured, s.room_rent_cap, s.copay, s.waiting_periods, s.exclusions])
