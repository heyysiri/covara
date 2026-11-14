"""M1 Intake & Document Vault: claim form values, checklist, original files, delete-my-data."""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import FileResponse

from app.core import llm
from app.modules.intake.checklist import build_checklist
from app.modules.pipeline import runner
from app.schemas.claim import ClaimOut, ClaimUpdate
from app.schemas.results import ChecklistItem, DocumentResult
from app.services import claim_store

router = APIRouter(prefix="/claims", tags=["intake"])


def _claim(claim_id: str) -> ClaimOut:
    claim = claim_store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


@router.patch("/{claim_id}", response_model=ClaimOut)
def update_claim(claim_id: str, payload: ClaimUpdate) -> ClaimOut:
    claim = _claim(claim_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(claim, k, v.strip() if isinstance(v, str) else v)
    return claim


@router.get("/{claim_id}/checklist", response_model=list[ChecklistItem])
def get_checklist(claim_id: str) -> list[ChecklistItem]:
    """Live checklist. Uses analysed doc types/references when available, else upload categories."""
    claim = _claim(claim_id)
    res = runner.get_results(claim_id)
    known = {d.id for d in res.documents}
    if res.checklist and known == {d.id for d in claim.documents}:
        return res.checklist
    docs = [DocumentResult(id=d.id, filename=d.original_filename, category=d.category.value,
                           doc_type=d.category.value) for d in claim.documents]
    return build_checklist(claim.claim_type.value, docs, res.fields if known else [])


@router.get("/{claim_id}/documents/{document_id}/file")
def get_document_file(claim_id: str, document_id: str) -> FileResponse:
    claim = _claim(claim_id)
    doc = next((d for d in claim.documents if d.id == document_id), None)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = claim_store.document_path(claim.id, doc)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path, media_type=doc.content_type, filename=doc.original_filename,
                        content_disposition_type="inline")


@router.delete("/{claim_id}/documents/{document_id}", status_code=204)
def delete_document(claim_id: str, document_id: str) -> Response:
    """Remove one uploaded document (e.g. a duplicate bill). Press Re-check afterwards."""
    claim = _claim(claim_id)
    removed = claim_store.remove_document(claim, document_id)
    if removed is None:
        raise HTTPException(status_code=404, detail="Document not found")
    still_used = {d.sha256 for c in claim_store.all_claims() for d in c.documents}
    if removed.sha256 not in still_used:
        llm.purge_cache_for([removed.sha256])
    return Response(status_code=204)


@router.delete("/{claim_id}", status_code=204)
def delete_claim(claim_id: str) -> Response:
    """Delete my data: files, extracted fields, results, cached model outputs for these files."""
    claim = _claim(claim_id)
    hashes = [d.sha256 for d in claim.documents]
    other_claims_use = set()  # cache is shared by file hash; keep entries another claim still needs
    for c in claim_store.all_claims():
        if c.id != claim_id:
            other_claims_use.update(d.sha256 for d in c.documents)
    llm.purge_cache_for([h for h in hashes if h not in other_claims_use])
    runner.forget(claim_id)
    claim_store.delete_claim(claim_id)
    return Response(status_code=204)
