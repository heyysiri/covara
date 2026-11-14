"""In-memory claim store (hackathon scope). Files live on disk under upload_dir/<claim_id>/."""

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
    )
    _claims[claim.id] = claim
    return claim


def get_claim(claim_id: str) -> ClaimOut | None:
    return _claims.get(claim_id)


def add_document(claim: ClaimOut, document: DocumentOut) -> None:
    claim.documents.append(document)
    claim.status = ClaimStatus.DOCUMENTS_UPLOADED


def claim_dir(claim_id: str) -> Path:
    """Per-claim storage directory. claim_id must come from a store lookup, never raw user input."""
    path = get_settings().upload_dir / claim_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def reset() -> None:
    """Clear in-memory state (used by tests)."""
    _claims.clear()
