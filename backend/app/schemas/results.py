"""Analysis result contract (PLAN.md section 7).

Schema only - the analysis pipeline that fills these is built in later phases.
"""

from enum import Enum

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ReadinessStatus(str, Enum):
    READY = "ready"
    NEEDS_ATTENTION = "needs_attention"
    INCOMPLETE = "incomplete"


class Finding(BaseModel):
    issue_type: str
    severity: Severity
    title: str
    description: str
    source_document: str | None = None
    page_number: int | None = None
    extracted_value: str | None = None
    comparison_value: str | None = None
    policy_clause: str | None = None
    policy_document: str | None = None
    policy_page_number: int | None = None
    recommended_action: str
    confidence: Confidence = Confidence.MEDIUM
    requires_human_review: bool = True


class AnalysisResults(BaseModel):
    claim_id: str
    readiness_status: ReadinessStatus
    documents_processed: list[str] = Field(default_factory=list)
    extracted_data: dict = Field(default_factory=dict)
    missing_documents: list[str] = Field(default_factory=list)
    inconsistencies: list[Finding] = Field(default_factory=list)
    policy_findings: list[Finding] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)
    evidence_references: list[dict] = Field(default_factory=list)
