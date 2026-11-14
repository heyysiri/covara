"""Interface between the pipeline (Person 1) and verification rules (Person 2, M3).

Person 2 implements, in app/modules/verification/service.py:

    def run_verification(ctx: VerificationContext) -> list[Finding]: ...

The pipeline calls it after extraction + normalisation + policy summary, then links each returned
Finding to policy clauses (M4) and builds the action plan (M6). If the module does not exist yet,
the pipeline runs with no rule findings (checklist-based actions still appear).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.claim import ClaimOut
from app.schemas.results import ChecklistItem, DocumentResult, ExtractedField, PolicyClause, PolicySummary


@dataclass
class VerificationContext:
    claim: ClaimOut  # claim_type, claimed_amount, patient_name (claim form values)
    documents: list[DocumentResult]  # doc_type per document, sha256 via claim.documents
    fields: list[ExtractedField]  # normalised; user-confirmed values have method="user"
    policy_summary: PolicySummary | None
    clauses: list[PolicyClause]
    checklist: list[ChecklistItem]
    page_texts: dict[str, list[str]] = field(default_factory=dict)  # document_id -> page texts (1-based order)

    def fields_for(self, key: str) -> list[ExtractedField]:
        return [f for f in self.fields if f.key == key and f.value is not None]

    def doc_type_of(self, document_id: str) -> str | None:
        return next((d.doc_type for d in self.documents if d.id == document_id), None)
