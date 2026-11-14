"""Claim session and uploaded-document schemas."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class InsuranceDomain(str, Enum):
    """Hackathon scope is health only; others are future scope."""

    HEALTH = "health"


class ClaimType(str, Enum):
    REIMBURSEMENT = "reimbursement"
    CASHLESS = "cashless"


class ClaimStatus(str, Enum):
    CREATED = "created"
    DOCUMENTS_UPLOADED = "documents_uploaded"
    ANALYZING = "analyzing"
    ANALYZED = "analyzed"
    FAILED = "failed"


class DocumentCategory(str, Enum):
    POLICY = "policy"
    FINAL_BILL = "final_bill"
    ITEMISED_BILL = "itemised_bill"
    DISCHARGE_SUMMARY = "discharge_summary"
    PRESCRIPTION = "prescription"
    DIAGNOSTIC_REPORT = "diagnostic_report"
    PAYMENT_RECEIPT = "payment_receipt"
    OTHER = "other"


class DocumentStatus(str, Enum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


class ClaimCreate(BaseModel):
    domain: InsuranceDomain = InsuranceDomain.HEALTH
    claim_type: ClaimType = ClaimType.REIMBURSEMENT


class DocumentOut(BaseModel):
    id: str
    claim_id: str
    original_filename: str
    category: DocumentCategory
    content_type: str
    size_bytes: int
    sha256: str
    status: DocumentStatus = DocumentStatus.UPLOADED
    uploaded_at: datetime


class ClaimOut(BaseModel):
    id: str
    domain: InsuranceDomain
    claim_type: ClaimType
    status: ClaimStatus
    created_at: datetime
    documents: list[DocumentOut] = Field(default_factory=list)


class RejectedFile(BaseModel):
    filename: str
    reason: str


class UploadResponse(BaseModel):
    uploaded: list[DocumentOut]
    rejected: list[RejectedFile]
