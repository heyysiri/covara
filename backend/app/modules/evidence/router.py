"""M5 Evidence: the highlighted page image behind "Why was this flagged?"."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path, Query, Response

from app.services import claim_store

from .render import PageOutOfRange, render_page

router = APIRouter(prefix="/claims", tags=["evidence"])


def _bbox(raw: str) -> list[float]:
    try:
        x0, y0, x1, y1 = (float(v) for v in raw.split(","))
    except ValueError:
        raise HTTPException(status_code=422, detail="bbox must be 'x0,y0,x1,y1' with values between 0 and 1")
    if not all(0 <= v <= 1 for v in (x0, y0, x1, y1)) or x1 <= x0 or y1 <= y0:
        raise HTTPException(status_code=422, detail="bbox must be 'x0,y0,x1,y1' with values between 0 and 1")
    return [x0, y0, x1, y1]


@router.get("/{claim_id}/documents/{document_id}/pages/{page}/image")
def page_image(
    claim_id: str,
    document_id: str,
    page: int = Path(ge=1),
    highlight: list[str] = Query(default=[], max_length=10, description="Quote(s) to highlight (repeatable)"),
    bbox: list[str] = Query(default=[], max_length=10, description="Fallback boxes 'x0,y0,x1,y1', normalised 0-1"),
    dpi: int = Query(default=110, ge=50, le=200),
) -> Response:
    claim = claim_store.get_claim(claim_id)
    doc = next((d for d in claim.documents if d.id == document_id), None) if claim else None
    if claim is None or doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = claim_store.document_path(claim.id, doc)
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    quotes = [q[:600] for q in highlight if q.strip()]
    try:
        out = render_page(path, page, quotes, [_bbox(b) for b in bbox], dpi)
    except PageOutOfRange as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        raise HTTPException(status_code=422, detail="This document page could not be rendered.")
    return Response(
        out.png,
        media_type="image/png",
        headers={
            "X-Highlights-Found": str(out.highlights_found),
            "X-Highlights-Requested": str(len(quotes)),
            "X-Bbox-Highlights": str(out.bbox_highlights),
            "X-Page-Count": str(out.page_count),
            "Access-Control-Expose-Headers": "X-Highlights-Found, X-Highlights-Requested, X-Bbox-Highlights, X-Page-Count",
            "Cache-Control": "private, max-age=300",
        },
    )
