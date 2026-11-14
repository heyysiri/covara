"""Shared contract v1 (DRAFT by Person 2, for Person 1 to review/adopt).

Mirrors section 4 of docs/DIVISION_OF_WORK.md, plus two gaps found while building the
claim B fixture:
  * EvidenceRef.source can be "claim_form" (e.g. the claimed amount) or "checklist"
    (e.g. a required document that is missing) - not only "document".
  * AnalysisResults.checks_passed is a separate list (a consistent item has no finding).

USP invariants enforced here in the models:
  I1  a Finding must carry at least one EvidenceRef
  I3  an Action must reference at least one finding
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class FindingKind(str, Enum):
    CONFIRMED = "confirmed"  # hard, rule-based mismatch
    POSSIBLE = "possible"  # needs human review


class FindingStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class ClauseType(str, Enum):
    COVERAGE = "coverage"
    EXCLUSION = "exclusion"
    SUBLIMIT = "sublimit"
    WAITING_PERIOD = "waiting_period"
    CONDITION = "condition"
    DEFINITION = "definition"


class ClauseVerdict(str, Enum):
    APPLIES = "applies"
    MAY_APPLY = "may_apply"
    DOES_NOT_APPLY = "does_not_apply"


class ActionOwner(str, Enum):
    USER = "user"
    HOSPITAL = "hospital"
    DOCTOR = "doctor"
    INSURER = "insurer"


class ActionGroup(str, Enum):
    UPLOAD = "upload"
    VERIFY_OR_CORRECT = "verify_or_correct"
    POLICY_REVIEW = "policy_review"
    ASK_INSURER = "ask_insurer"


class ReadinessStatus(str, Enum):
    READY = "ready"
    NEEDS_ATTENTION = "needs_attention"
    INCOMPLETE = "incomplete"


class AnalysisStatus(str, Enum):
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETE = "complete"
    FAILED = "failed"


class EvidenceRef(BaseModel):
    """Where a fact came from. Never optional on a Finding (I1)."""

    source: Literal["document", "claim_form", "checklist"] = "document"
    document_id: str | None = None
    filename: str | None = None
    page_number: int | None = Field(default=None, ge=1)
    bbox: list[float] | None = None  # [x0, y0, x1, y1] normalised 0-1
    quote: str | None = None
    field: str | None = None  # for claim_form / checklist evidence
    value: Any = None

    @field_validator("bbox")
    @classmethod
    def _bbox(cls, v: list[float] | None) -> list[float] | None:
        if v is not None and (len(v) != 4 or any(not 0 <= x <= 1 for x in v)):
            raise ValueError("bbox must be [x0, y0, x1, y1] with values between 0 and 1")
        return v

    @model_validator(mode="after")
    def _shape(self) -> "EvidenceRef":
        if self.source == "document":
            if not self.document_id or self.page_number is None:
                raise ValueError("document evidence needs document_id and page_number")
            if not self.quote and self.value is None:
                raise ValueError("document evidence needs a quote or a value")
        elif not self.field:
            raise ValueError(f"{self.source} evidence needs a field name")
        return self


class ExtractedField(BaseModel):
    id: str
    key: str
    value: Any = None  # None = unknown (never guessed)
    raw_text: str | None = None
    confidence: float = Field(ge=0, le=1)
    evidence: EvidenceRef
    user_confirmed: bool = False


class PolicyClause(BaseModel):
    id: str
    clause_ref: str
    type: ClauseType
    title: str
    text: str
    document_id: str
    filename: str
    page_number: int = Field(ge=1)


class ClauseLink(BaseModel):
    clause_id: str
    verdict: ClauseVerdict
    quote: str  # must be verbatim from the clause text (I9)


class Explanation(BaseModel):
    rule: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    why_it_matters: str


class Finding(BaseModel):
    id: str
    rule_id: str  # "V1".."V14"
    issue_type: str
    severity: Severity
    kind: FindingKind
    title: str
    description: str
    evidence: list[EvidenceRef]
    extracted_value: str | None = None
    comparison_value: str | None = None
    clause_links: list[ClauseLink] = Field(default_factory=list)
    exposure_amount: float | None = None  # INR, informational estimate only
    blocking: bool = False
    explanation: Explanation
    requires_human_review: bool = True
    status: FindingStatus = FindingStatus.OPEN

    @field_validator("evidence")
    @classmethod
    def _evidence_required(cls, v: list[EvidenceRef]) -> list[EvidenceRef]:
        if not v:
            raise ValueError("a finding must carry at least one EvidenceRef (invariant I1)")
        return v


class Action(BaseModel):
    id: str
    title: str
    why: str
    how: list[str] = Field(default_factory=list)
    owner: ActionOwner
    blocking: bool = False
    group: ActionGroup
    finding_ids: list[str]
    clause_ids: list[str] = Field(default_factory=list)
    draft_message: str | None = None
    done: bool = False

    @field_validator("finding_ids")
    @classmethod
    def _finding_required(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("an action must reference at least one finding (invariant I3)")
        return v


class DocumentItem(BaseModel):
    id: str
    filename: str
    doc_type: str  # policy | final_bill | itemised_bill | discharge_summary | prescription | diagnostic_report | payment_receipt | other
    status: str = "processed"
    error: str | None = None


class AnalysisResults(BaseModel):
    claim_id: str
    status: AnalysisStatus
    stage: str
    progress: float = Field(ge=0, le=1)
    readiness_status: ReadinessStatus
    readiness_explanation: str
    documents: list[DocumentItem] = Field(default_factory=list)
    documents_failed: list[DocumentItem] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    clauses: list[PolicyClause] = Field(default_factory=list)
    policy_summary: dict[str, Any] = Field(default_factory=dict)
    action_plan: list[Action] = Field(default_factory=list)
    checks_passed: list[str] = Field(default_factory=list)
    checklist: dict[str, Any] = Field(default_factory=dict)
    packet_status: str = ""
    disclaimer: str = ""


# ---- Inputs to the verification engine (not part of the API response) ----------------


class DocumentInfo(BaseModel):
    id: str
    filename: str
    doc_type: str
    sha256: str | None = None
    status: str = "processed"


class ClaimInput(BaseModel):
    claim_type: Literal["reimbursement", "cashless"] = "reimbursement"
    claimed_amount: float | None = None
    patient_name: str | None = None
