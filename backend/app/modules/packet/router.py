"""M7: Readiness Report PDF, Claim Packet PDF and claim.json."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response

from app.modules.pipeline import runner
from app.schemas.claim import ClaimOut
from app.schemas.results import AnalysisResults, RunStatus
from app.services import claim_store

from .claim_json import build_claim_json
from .packet import build_packet
from .report import build_report
from .report_i18n import TranslationUnavailable, build_report_translated

SUPPORTED_REPORT_LANGS = {"hi-IN"}

router = APIRouter(prefix="/claims", tags=["packet"])


def _ready(claim_id: str) -> tuple[ClaimOut, AnalysisResults]:
    claim = claim_store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    results = runner.get_results(claim_id)
    if results.status != RunStatus.COMPLETE:
        raise HTTPException(status_code=409, detail="Run the analysis first: the report needs a completed analysis.")
    return claim, results


def _pdf(data: bytes, filename: str) -> Response:
    return Response(data, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"})


@router.get("/{claim_id}/report")
def get_report(claim_id: str, lang: str = "en-IN") -> Response:
    """Built fresh from the current results every time it is requested (nothing is stored)."""
    claim, results = _ready(claim_id)
    if lang != "en-IN":
        if lang not in SUPPORTED_REPORT_LANGS:
            raise HTTPException(status_code=422, detail="Unsupported language for the report.")
        try:
            return _pdf(build_report_translated(claim, results, lang), f"covara-report-{claim.id[:8]}-{lang[:2]}.pdf")
        except TranslationUnavailable:
            raise HTTPException(status_code=503, detail="The translated report is unavailable right now. Try again, or download it in English.")
    return _pdf(build_report(claim, results), f"covara-report-{claim.id[:8]}.pdf")


@router.get("/{claim_id}/packet")
def get_packet(claim_id: str) -> Response:
    claim, results = _ready(claim_id)
    return _pdf(build_packet(claim, results), f"covara-packet-{claim.id[:8]}.pdf")


@router.get("/{claim_id}/packet.json")
def get_claim_json(claim_id: str) -> Response:
    import json

    claim, results = _ready(claim_id)
    return Response(json.dumps(build_claim_json(claim, results), indent=2, ensure_ascii=False), media_type="application/json",
                    headers={"Content-Disposition": f'attachment; filename="covara-claim-{claim.id[:8]}.json"', "Cache-Control": "no-store"})
