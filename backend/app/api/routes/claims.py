import hashlib
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.config import get_settings
from app.schemas.claim import (
    ClaimCreate,
    ClaimOut,
    DocumentCategory,
    DocumentOut,
    RejectedFile,
    UploadResponse,
)
from app.schemas.results import AnalysisResults
from app.services import claim_store
from app.utils.files import (
    ALLOWED_TYPES,
    display_filename,
    extension_of,
    validate_signature,
)

router = APIRouter(prefix="/claims", tags=["claims"])

CHUNK = 1024 * 1024
NOT_IMPLEMENTED = "Not implemented yet - arrives in a later phase."


def _get_claim_or_404(claim_id: str) -> ClaimOut:
    claim = claim_store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.post("", response_model=ClaimOut, status_code=status.HTTP_201_CREATED)
def create_claim(payload: ClaimCreate | None = None) -> ClaimOut:
    return claim_store.create_claim(payload or ClaimCreate())


@router.get("/{claim_id}", response_model=ClaimOut)
def get_claim(claim_id: str) -> ClaimOut:
    return _get_claim_or_404(claim_id)


@router.post(
    "/{claim_id}/documents",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_documents(
    claim_id: str,
    category: DocumentCategory = Form(...),
    files: list[UploadFile] = File(...),
) -> UploadResponse:
    claim = _get_claim_or_404(claim_id)
    settings = get_settings()
    uploaded: list[DocumentOut] = []
    rejected: list[RejectedFile] = []

    for upload in files:
        name = display_filename(upload.filename)
        ext = extension_of(name)

        if ext not in ALLOWED_TYPES:
            rejected.append(
                RejectedFile(filename=name, reason="Unsupported file type. Use PDF, PNG or JPG.")
            )
            continue

        # Stream to disk under a server-generated name; enforce the size cap while reading.
        doc_id = uuid.uuid4().hex
        dest = claim_store.claim_dir(claim.id) / f"{doc_id}{'.jpg' if ext == '.jpeg' else ext}"
        sha = hashlib.sha256()
        size = 0
        reason: str | None = None
        with dest.open("wb") as out:
            while chunk := await upload.read(CHUNK):
                if size == 0 and not validate_signature(ext, chunk[:16]):
                    reason = "File content does not match its extension."
                    break
                size += len(chunk)
                if size > settings.max_upload_bytes:
                    reason = f"File exceeds the {settings.max_upload_mb} MB limit."
                    break
                sha.update(chunk)
                out.write(chunk)
        if reason is None and size == 0:
            reason = "File is empty."
        if reason:
            dest.unlink(missing_ok=True)
            rejected.append(RejectedFile(filename=name, reason=reason))
            continue

        document = DocumentOut(
            id=doc_id,
            claim_id=claim.id,
            original_filename=name,
            category=category,
            content_type=ALLOWED_TYPES[ext][0],
            size_bytes=size,
            sha256=sha.hexdigest(),
            uploaded_at=datetime.now(timezone.utc),
        )
        claim_store.add_document(claim, document)
        uploaded.append(document)

    if not uploaded:
        raise HTTPException(
            status_code=422,
            detail=[r.model_dump() for r in rejected] or "No files received",
        )
    return UploadResponse(uploaded=uploaded, rejected=rejected)


@router.get("/{claim_id}/documents", response_model=list[DocumentOut])
def list_documents(claim_id: str) -> list[DocumentOut]:
    return _get_claim_or_404(claim_id).documents


# --- Placeholders for later phases (analysis pipeline is NOT part of Phase 1) ---


@router.post("/{claim_id}/analyze", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def analyze_claim(claim_id: str) -> None:
    _get_claim_or_404(claim_id)
    raise HTTPException(status_code=501, detail=NOT_IMPLEMENTED)


@router.get("/{claim_id}/results", response_model=AnalysisResults)
def get_results(claim_id: str) -> AnalysisResults:
    _get_claim_or_404(claim_id)
    raise HTTPException(status_code=501, detail=NOT_IMPLEMENTED)


@router.get("/{claim_id}/report")
def get_report(claim_id: str) -> None:
    _get_claim_or_404(claim_id)
    raise HTTPException(status_code=501, detail=NOT_IMPLEMENTED)
