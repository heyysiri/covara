"""M8 pipeline API: start/re-check analysis, poll results, review fields, tick actions."""

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from pydantic import BaseModel

from app.modules.extraction.extract import needs_review
from app.modules.pipeline import runner
from app.schemas.claim import ClaimOut, ClaimStatus
from app.schemas.results import Action, AnalysisResults, DocumentResult, ExtractedField, PolicyClause, PolicySummary, RunStatus
from app.services import claim_store

router = APIRouter(prefix="/claims", tags=["analysis"])


def _claim(claim_id: str) -> ClaimOut:
    claim = claim_store.get_claim(claim_id)
    if claim is None:
        raise HTTPException(status_code=404, detail="Claim not found")
    return claim


def _start(claim: ClaimOut, background: BackgroundTasks) -> AnalysisResults:
    if not claim.documents:
        raise HTTPException(status_code=422, detail="Upload at least one document before analysing.")
    current = runner.get_results(claim.id)
    if current.status == RunStatus.PROCESSING:
        return current
    res = runner.start(claim)
    claim.status = ClaimStatus.ANALYZING
    background.add_task(_run_and_mark, claim.id)
    return res


def _run_and_mark(claim_id: str) -> None:
    runner.run(claim_id)
    claim = claim_store.get_claim(claim_id)
    if claim:
        ok = runner.get_results(claim_id).status == RunStatus.COMPLETE
        claim.status = ClaimStatus.ANALYZED if ok else ClaimStatus.FAILED


@router.post("/{claim_id}/analyze", response_model=AnalysisResults, status_code=status.HTTP_202_ACCEPTED)
def analyze_claim(claim_id: str, background: BackgroundTasks) -> AnalysisResults:
    """Start (or re-check) the analysis. Poll GET /results for status/stage/progress."""
    return _start(_claim(claim_id), background)


@router.get("/{claim_id}/results", response_model=AnalysisResults)
def get_results(claim_id: str) -> AnalysisResults:
    _claim(claim_id)
    return runner.get_results(claim_id)


class ExtractionOut(BaseModel):
    documents: list[DocumentResult]
    fields: list[ExtractedField]
    review_needed: list[str]  # field ids


@router.get("/{claim_id}/extraction", response_model=ExtractionOut)
def get_extraction(claim_id: str) -> ExtractionOut:
    _claim(claim_id)
    r = runner.get_results(claim_id)
    return ExtractionOut(documents=r.documents, fields=r.fields,
                         review_needed=[f.id for f in r.fields if needs_review(f)])


class PolicyOut(BaseModel):
    summary: PolicySummary | None
    clauses: list[PolicyClause]


@router.get("/{claim_id}/policy", response_model=PolicyOut)
def get_policy(claim_id: str) -> PolicyOut:
    _claim(claim_id)
    r = runner.get_results(claim_id)
    return PolicyOut(summary=r.policy_summary, clauses=r.clauses)


@router.get("/{claim_id}/review", response_model=list[ExtractedField])
def get_review(claim_id: str) -> list[ExtractedField]:
    """Critical fields below the confidence threshold that the user should confirm."""
    _claim(claim_id)
    return [f for f in runner.get_results(claim_id).fields if needs_review(f)]


class FieldEdit(BaseModel):
    field_id: str
    value: str | float | None = None  # None = confirm the current value as correct
    confirm: bool = True


class ReviewIn(BaseModel):
    edits: list[FieldEdit]
    rerun: bool = True


@router.post("/{claim_id}/review", response_model=AnalysisResults, status_code=status.HTTP_202_ACCEPTED)
def submit_review(claim_id: str, payload: ReviewIn, background: BackgroundTasks) -> AnalysisResults:
    """Confirm or correct extracted values, then re-check (W4/W8)."""
    claim = _claim(claim_id)
    known = {f.id for f in runner.get_results(claim_id).fields}
    unknown = [e.field_id for e in payload.edits if e.field_id not in known]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Unknown field ids: {', '.join(unknown)}")
    for e in payload.edits:
        runner.set_override(claim_id, e.field_id, e.value, e.confirm)
    return _start(claim, background) if payload.rerun else runner.get_results(claim_id)


@router.get("/{claim_id}/actions", response_model=list[Action])
def get_actions(claim_id: str) -> list[Action]:
    _claim(claim_id)
    return runner.get_results(claim_id).action_plan


class ActionPatch(BaseModel):
    done: bool


@router.patch("/{claim_id}/actions/{action_id}", response_model=Action)
def patch_action(claim_id: str, action_id: str, payload: ActionPatch) -> Action:
    _claim(claim_id)
    if not runner.set_action_done(claim_id, action_id, payload.done):
        raise HTTPException(status_code=404, detail="Action not found")
    return next(a for a in runner.get_results(claim_id).action_plan if a.id == action_id)
