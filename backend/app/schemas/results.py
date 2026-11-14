"""Shared analysis contract (docs/DIVISION_OF_WORK.md section 4).

Mirrored in frontend/src/types/results.ts. Change only via small, announced commits.
USP invariants enforced here: I1 (no finding without evidence) and I3 (no action without a finding,
except checklist "upload" actions which cite the checklist item instead).
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReadinessStatus(str, Enum):
    READY = "ready"
    NEEDS_ATTENTION = "needs_attention"
    INCOMPLETE = "incomplete"


class RunStatus(str, Enum):
    IDLE = "idle"
    PROCESSING = "processing"
    AWAITING_REVIEW = "awaiting_review"
    COMPLETE = "complete"
    FAILED = "failed"


DocType = Literal[
    "policy",
    "final_bill",
    "itemised_bill",
    "discharge_summary",
    "prescription",
    "diagnostic_report",
    "payment_receipt",
    "other",
]

ClauseType = Literal["coverage", "exclusion", "sublimit", "waiting_period", "condition", "definition"]


class EvidenceRef(BaseModel):
    """Where a value comes from: a page of an uploaded document, or the claim form the user filled in."""

    source: Literal["document", "claim_form", "checklist"] = "document"
    document_id: str | None = None
    filename: str | None = None
    page_number: int | None = None  # 1-based
    bbox: list[float] | None = None  # [x0, y0, x1, y1] normalised 0-1
    quote: str | None = None  # exact source text (verified against the page text when possible)
    field: str | None = None  # claim_form / checklist only, e.g. "claimed_amount"
    value: str | float | None = None  # claim_form / checklist only

    @model_validator(mode="after")
    def _document_needs_location(self):
        if self.source == "document" and (self.document_id is None or self.filename is None
                                          or self.page_number is None):
            raise ValueError("document evidence needs document_id, filename and page_number")
        if self.source != "document" and not self.field:
            raise ValueError(f"{self.source} evidence needs a field")
        return self


class ExtractedField(BaseModel):
    id: str
    key: str  # see FIELD_KEYS
    value: str | float | None = None  # normalised value (ISO date, float INR, cleaned name)
    raw_text: str | None = None  # value as written in the document
    confidence: float = Field(ge=0, le=1)
    evidence: EvidenceRef
    user_confirmed: bool = False
    method: Literal["claude", "gemini", "groq", "sarvam", "rules", "user"] = "rules"


FIELD_KEYS = {
    "patient_name", "age", "policyholder_name", "member_id", "insurer", "policy_number",
    "policy_start", "policy_end", "policy_inception", "sum_insured", "room_rent_cap", "room_rent_charged_per_day",
    "waiting_period", "hospital_name", "admission_date", "discharge_date", "diagnosis",
    "diagnosis_date", "treatment", "bill_number", "bill_date", "bill_total", "line_item",
    "billed_item", "prescribed_item", "receipt_amount", "receipt_date", "referenced_document",
}
CRITICAL_KEYS = {
    "patient_name", "policyholder_name", "policy_number", "member_id", "admission_date",
    "discharge_date", "bill_total", "bill_number", "policy_start", "policy_end", "policy_inception", "receipt_amount",
}
REVIEW_THRESHOLD = 0.75


class PolicyClause(BaseModel):
    id: str
    clause_ref: str  # e.g. "4.2"
    type: ClauseType
    title: str
    text: str  # must exist on page_number of the uploaded policy (I2)
    document_id: str
    filename: str
    page_number: int


class SummaryValue(BaseModel):
    value: float | str | None = None
    text: str  # human-readable, e.g. "1% of sum insured per day"
    evidence: EvidenceRef


class WaitingPeriod(BaseModel):
    name: str  # e.g. "Pre-existing diseases"
    days: int
    evidence: EvidenceRef


class PolicySummary(BaseModel):
    sum_insured: SummaryValue | None = None  # value = INR
    room_rent_cap: SummaryValue | None = None  # value = INR per day (computed if % of SI)
    room_rent_cap_percent: float | None = None  # e.g. 1.0 when "1% of sum insured"
    copay: SummaryValue | None = None  # value = percent
    pre_hosp_days: SummaryValue | None = None
    post_hosp_days: SummaryValue | None = None
    waiting_periods: list[WaitingPeriod] = Field(default_factory=list)
    exclusions: list[SummaryValue] = Field(default_factory=list)


class ClauseLink(BaseModel):
    clause_id: str
    verdict: Literal["applies", "may_apply", "does_not_apply"]
    quote: str  # verbatim substring of the clause text (I9)


class Explanation(BaseModel):
    rule: str
    inputs: dict = Field(default_factory=dict)
    why_it_matters: str = ""


class Finding(BaseModel):
    id: str
    rule_id: str  # "V1".."V14"
    issue_type: str
    severity: Severity
    kind: Literal["confirmed", "possible"]
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
    status: Literal["open", "acknowledged", "resolved"] = "open"

    @model_validator(mode="after")
    def _needs_evidence(self):  # I1
        if not self.evidence:
            raise ValueError("A finding must carry at least one EvidenceRef")
        return self


Owner = Literal["user", "hospital", "doctor", "insurer"]
ActionGroup = Literal["upload", "verify_or_correct", "policy_review", "consistent", "ask_insurer"]


class Action(BaseModel):
    id: str
    title: str
    why: str
    how: list[str] = Field(default_factory=list)
    owner: Owner
    blocking: bool = False
    group: ActionGroup
    finding_ids: list[str] = Field(default_factory=list)
    clause_ids: list[str] = Field(default_factory=list)
    checklist_category: str | None = None
    draft_message: str | None = None
    done: bool = False

    @model_validator(mode="after")
    def _grounded(self):  # I3
        if self.group not in ("upload", "consistent") and not self.finding_ids:
            raise ValueError("Actions must cite at least one finding")
        if self.group == "upload" and not (self.finding_ids or self.checklist_category):
            raise ValueError("Upload actions must cite a finding or checklist item")
        return self


class ChecklistSummary(BaseModel):
    """Compact view of the checklist (same shape as the demo fixture)."""

    required_present: list[str] = Field(default_factory=list)
    required_missing: list[str] = Field(default_factory=list)
    referenced_but_missing: list[str] = Field(default_factory=list)


class ChecklistItem(BaseModel):
    category: DocType
    label: str
    required: bool
    received: bool
    document_ids: list[str] = Field(default_factory=list)
    reason: str  # why it is required / how it was satisfied
    evidence: EvidenceRef | None = None  # e.g. where a missing document is referenced


class DocumentResult(BaseModel):
    id: str
    filename: str
    category: DocType  # category chosen by the user at upload
    doc_type: DocType  # effective type (user choice, or auto-detected when "other")
    detected_type: DocType | None = None
    status: Literal["pending", "processed", "failed"] = "pending"
    pages: int = 0
    has_text_layer: bool = True
    extraction_method: str | None = None
    error: str | None = None


class LlmCall(BaseModel):
    provider: str
    model: str
    task: str
    cached: bool
    latency_ms: int
    ok: bool
    error: str | None = None


class AnalysisResults(BaseModel):
    claim_id: str
    status: RunStatus = RunStatus.IDLE
    stage: str = ""
    progress: float = 0.0  # 0..1
    stages: list[str] = Field(default_factory=list)
    readiness_status: ReadinessStatus | None = None
    readiness_explanation: str = ""
    documents: list[DocumentResult] = Field(default_factory=list)
    fields: list[ExtractedField] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    clauses: list[PolicyClause] = Field(default_factory=list)
    policy_summary: PolicySummary | None = None
    action_plan: list[Action] = Field(default_factory=list)
    checklist: list[ChecklistItem] = Field(default_factory=list)
    checklist_summary: ChecklistSummary = Field(default_factory=ChecklistSummary)
    checks_passed: list[str] = Field(default_factory=list)  # consistent items: no finding behind them
    documents_failed: list[str] = Field(default_factory=list)
    providers_used: list[str] = Field(default_factory=list)
    llm_calls: list[LlmCall] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    packet_status: str | None = None
    error: str | None = None
    disclaimer: str = (
        "Covara is an AI-assisted claim-preparation tool. It does not decide whether an insurer will "
        "approve a claim and is not medical, legal or financial advice."
    )
