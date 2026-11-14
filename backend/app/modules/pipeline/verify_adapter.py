"""Bridge between the pipeline (results.py models) and Person 2's verification engine (contract.py models).

The two model sets are field-compatible, so conversion is a dump/validate round trip. The adapter also
shapes extracted values the way the engine expects them (see PROGRESS.md):
  - line_item: engine sums all line items it sees, so pass only the itemised bill's items when one exists
    (otherwise the final bill's), never both (double counting would raise a false V4 mismatch).
  - referenced_document: pass the reference as written ("prescription no. RX-7781"), not a bare doc type.
"""

from __future__ import annotations

from app.modules.pipeline.context import VerificationContext, VerificationResult
from app.modules.verification.helpers import parse_amount
from app.modules.verification.policy_facts import PolicyFacts, WaitingFact, find_associated_expenses
from app.schemas import contract as c
from app.schemas.results import Finding


def _fields(ctx: VerificationContext) -> list[c.ExtractedField]:
    doc_type = {d.id: d.doc_type for d in ctx.documents}
    has_itemised = any(f.key == "line_item" and doc_type.get(f.evidence.document_id) == "itemised_bill"
                       for f in ctx.fields)
    out: list[c.ExtractedField] = []
    for f in ctx.fields:
        if f.key == "line_item":
            dt = doc_type.get(f.evidence.document_id)
            if has_itemised and dt != "itemised_bill":
                continue
        data = f.model_dump(mode="json", exclude={"method"})
        if f.key == "referenced_document" and f.raw_text:
            data["value"] = f.raw_text
        if data["evidence"].get("quote") is None and data["evidence"].get("value") is None:
            data["evidence"]["value"] = None if f.value is None else str(f.value)
        out.append(c.ExtractedField.model_validate(data))
    return out


def _evidence(e) -> c.EvidenceRef:
    data = e.model_dump(mode="json")
    if data.get("source", "document") == "document" and data.get("quote") is None and data.get("value") is None:
        data["value"] = "policy"  # keep policy evidence valid even without a located quote
    return c.EvidenceRef.model_validate(data)


def _policy_facts(ctx: VerificationContext) -> PolicyFacts | None:
    """Policy values for the policy-aware rules (V10 room rent, V11 waiting period)."""
    s = ctx.policy_summary
    if s is None:
        return None
    cap = s.room_rent_cap
    return PolicyFacts(
        associated_expenses=find_associated_expenses(ctx.clauses),
        room_rent_cap_per_day=parse_amount(cap.value) if cap else None,
        room_rent_cap_evidence=_evidence(cap.evidence) if cap else None,
        waiting_periods=[WaitingFact(name=w.name, days=int(w.days), evidence=_evidence(w.evidence))
                         for w in s.waiting_periods],
    )


def run_engine(ctx: VerificationContext) -> VerificationResult:
    from app.modules.verification import run_verification  # Person 2 (M3)

    sha = {d.id: d.sha256 for d in ctx.claim.documents}
    documents = [c.DocumentInfo(id=d.id, filename=d.filename, doc_type=d.doc_type, sha256=sha.get(d.id),
                                status=d.status) for d in ctx.documents if d.status != "failed"]
    claim = c.ClaimInput(claim_type=ctx.claim.claim_type.value, claimed_amount=ctx.claim.claimed_amount,
                         patient_name=ctx.claim.patient_name)
    # the checklist is the one place that decides which documents a claim needs; plain-required items only
    # (documents merely referenced by another file are reported by the referenced-document check)
    required = [c.category for c in ctx.checklist if c.required and c.evidence is None]
    res = run_verification(_fields(ctx), documents, claim, _policy_facts(ctx), required_documents=required)
    findings = [Finding.model_validate(f.model_dump(mode="json")) for f in res.findings]
    return VerificationResult(findings=findings, checks_passed=list(res.checks_passed))
