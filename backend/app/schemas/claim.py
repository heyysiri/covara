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
    claimed_amount: float | None = Field(default=None, ge=0)  # INR, as entered on the claim form
    patient_name: str | None = Field(default=None, max_length=120)
    consent_given: bool = False  # explicit consent to process the uploaded documents (W7)


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
    duplicate_of: str | None = None  # id of an earlier document with the same sha256


class ClaimOut(BaseModel):
    id: str
    domain: InsuranceDomain
    claim_type: ClaimType
    status: ClaimStatus
    created_at: datetime
    claimed_amount: float | None = None
    patient_name: str | None = None
    consent_at: datetime | None = None
    documents: list[DocumentOut] = Field(default_factory=list)


class RejectedFile(BaseModel):
    filename: str
    reason: str


class UploadResponse(BaseModel):
    uploaded: list[DocumentOut]
    rejected: list[RejectedFile]
    duplicates: list[DocumentOut] = Field(default_factory=list)  # uploaded, but same file seen before


class ClaimUpdate(BaseModel):
    claimed_amount: float | None = Field(default=None, ge=0)
    patient_name: str | None = Field(default=None, max_length=120)
