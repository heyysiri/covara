"""In-memory claim store (hackathon scope). Files live on disk under upload_dir/<claim_id>/."""

import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.config import get_settings
from app.schemas.claim import (
    ClaimCreate,
    ClaimOut,
    ClaimStatus,
    DocumentOut,
)

_claims: dict[str, ClaimOut] = {}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_claim(payload: ClaimCreate) -> ClaimOut:
    claim = ClaimOut(
        id=uuid.uuid4().hex,
        domain=payload.domain,
        claim_type=payload.claim_type,
        status=ClaimStatus.CREATED,
        created_at=_now(),
        claimed_amount=payload.claimed_amount,
        patient_name=(payload.patient_name or "").strip() or None,
        consent_at=_now() if payload.consent_given else None,
    )
    _claims[claim.id] = claim
    return claim


def get_claim(claim_id: str) -> ClaimOut | None:
    return _claims.get(claim_id)


def all_claims() -> list[ClaimOut]:
    return list(_claims.values())


def add_document(claim: ClaimOut, document: DocumentOut) -> None:
    claim.documents.append(document)
    claim.status = ClaimStatus.DOCUMENTS_UPLOADED


def find_by_sha(claim: ClaimOut, sha256: str) -> DocumentOut | None:
    return next((d for d in claim.documents if d.sha256 == sha256), None)


def remove_document(claim: ClaimOut, document_id: str) -> DocumentOut | None:
    """Remove one document (and its stored file) from the claim."""
    doc = next((d for d in claim.documents if d.id == document_id), None)
    if doc is None:
        return None
    document_path(claim.id, doc).unlink(missing_ok=True)
    claim.documents = [d for d in claim.documents if d.id != document_id]
    return doc


def delete_claim(claim_id: str) -> bool:
    """Remove the claim and its stored files. Derived data is removed by the caller's hooks."""
    claim = _claims.pop(claim_id, None)
    if claim is None:
        return False
    path = get_settings().upload_dir / claim_id
    if path.is_dir():
        shutil.rmtree(path, ignore_errors=True)
    return True


def document_path(claim_id: str, document: DocumentOut) -> Path:
    ext = {"application/pdf": ".pdf", "image/png": ".png", "image/jpeg": ".jpg"}[document.content_type]
    return get_settings().upload_dir / claim_id / f"{document.id}{ext}"


def claim_dir(claim_id: str) -> Path:
    """Per-claim storage directory. claim_id must come from a store lookup, never raw user input."""
    path = get_settings().upload_dir / claim_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def reset() -> None:
    """Clear in-memory state (used by tests)."""
    _claims.clear()
