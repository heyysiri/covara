"""LangGraph pipeline + background runner.

ingest -> classify -> extract -> normalize -> policy -> verify -> policy_match -> explain_plan -> finalize

Nodes are plain functions over a typed state, so each is testable on its own. Progress is written to
the claim's AnalysisResults as each node finishes; the UI polls GET /claims/{id}/results.
Failure rules: one bad document never fails the run; no policy => skip policy stages with a warning.
"""

from __future__ import annotations

import hashlib
import logging
import threading
import traceback
from concurrent.futures import ThreadPoolExecutor
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from app.core import llm
from app.modules.actions.plan import build_plan, readiness, summary_is_empty
from app.modules.extraction import normalize as nz
from app.modules.extraction.classify import classify
from app.modules.extraction.extract import extract
from app.modules.extraction.ingest import IngestedDoc, ingest
from app.modules.intake.checklist import build_checklist
from app.modules.pipeline.context import VerificationContext
from app.modules.policy.index import build_clauses
from app.modules.policy.match import link_finding
from app.modules.policy.summary import build_summary
from app.schemas.claim import ClaimOut
from app.schemas.results import (
    AnalysisResults,
    DocumentResult,
    ExtractedField,
    Finding,
    LlmCall,
    PolicyClause,
    PolicySummary,
    RunStatus,
)
from app.services import claim_store

log = logging.getLogger("covara.pipeline")

STAGES = [
    ("ingest", "Reading documents"),
    ("classify", "Identifying document types"),
    ("extract", "Extracting details"),
    ("normalize", "Normalising values"),
    ("policy", "Reading the policy"),
    ("verify", "Checking consistency"),
    ("policy_match", "Matching policy clauses"),
    ("explain_plan", "Building your action plan"),
    ("finalize", "Finishing up"),
]
STAGE_LABEL = dict(STAGES)

# ------------------------------------------------------------------ per-claim state

_results: dict[str, AnalysisResults] = {}
_overrides: dict[str, dict[str, dict]] = {}  # claim_id -> field_id -> {"value": ..., "confirm": bool}
_done_actions: dict[str, set[str]] = {}
_locks: dict[str, threading.Lock] = {}


def get_results(claim_id: str) -> AnalysisResults:
    return _results.get(claim_id) or AnalysisResults(claim_id=claim_id, stages=[s for _, s in STAGES])


def set_override(claim_id: str, field_id: str, value, confirm: bool) -> None:
    _overrides.setdefault(claim_id, {})[field_id] = {"value": value, "confirm": confirm}


def set_action_done(claim_id: str, action_id: str, done: bool) -> bool:
    res = _results.get(claim_id)
    action = next((a for a in (res.action_plan if res else []) if a.id == action_id), None)
    if action is None:
        return False
    s = _done_actions.setdefault(claim_id, set())
    (s.add if done else s.discard)(action_id)
    action.done = done
    return True


def forget(claim_id: str) -> None:
    for d in (_results, _overrides, _done_actions, _locks):
        d.pop(claim_id, None)


def reset() -> None:
    for d in (_results, _overrides, _done_actions, _locks):
        d.clear()


# ------------------------------------------------------------------ graph


class ClaimState(TypedDict, total=False):
    claim_id: str
    claim: ClaimOut
    docs: list[IngestedDoc]
    documents: list[DocumentResult]
    fields: list[ExtractedField]
    clauses: list[PolicyClause]
    policy_summary: PolicySummary | None
    findings: list[Finding]
    calls: list[LlmCall]
    warnings: list[str]


def _progress(state: ClaimState, stage: str) -> None:
    res = _results[state["claim_id"]]
    idx = [s for s, _ in STAGES].index(stage)
    res.stage = STAGE_LABEL[stage]
    res.progress = round((idx + 1) / len(STAGES), 2)


def node_ingest(state: ClaimState) -> dict:
    claim = state["claim"]
    docs, documents, warnings = [], [], list(state.get("warnings", []))
    for d in claim.documents:
        dr = DocumentResult(id=d.id, filename=d.original_filename, category=d.category.value,
                            doc_type=d.category.value)
        try:
            ing = ingest(d.id, d.original_filename, claim_store.document_path(claim.id, d), d.content_type, d.sha256)
            dr.pages, dr.has_text_layer = len(ing.pages), ing.has_text_layer
            docs.append(ing)
        except Exception as e:
            dr.status, dr.error = "failed", f"Could not read this file ({type(e).__name__})."
            warnings.append(f"{d.original_filename}: could not be read.")
        documents.append(dr)
    _progress(state, "ingest")
    return {"docs": docs, "documents": documents, "warnings": warnings}


def node_classify(state: ClaimState) -> dict:
    calls = state["calls"]
    by_id = {d.id: d for d in state["documents"]}
    for doc in state["docs"]:
        dr = by_id[doc.document_id]
        try:
            detected = classify(doc, calls)
        except Exception:
            detected = None
        dr.detected_type = detected
        if dr.category == "other" and detected:
            dr.doc_type = detected  # user choice wins unless they picked "other"
    _progress(state, "classify")
    return {"documents": state["documents"]}


def node_extract(state: ClaimState) -> dict:
    calls = state["calls"]
    by_id = {d.id: d for d in state["documents"]}
    warnings = list(state.get("warnings", []))

    def work(doc: IngestedDoc):
        dr = by_id[doc.document_id]
        local: list[LlmCall] = []
        try:
            fields, method = extract(doc, dr.doc_type, local)
            return doc, fields, method, local, None
        except Exception as e:
            log.warning("extract failed for %s: %s", doc.document_id, type(e).__name__)
            return doc, [], None, local, e

    fields: list[ExtractedField] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        for doc, fs, method, local, err in pool.map(work, state["docs"]):
            calls.extend(local)
            dr = by_id[doc.document_id]
            if err:
                dr.status, dr.error = "failed", "Extraction failed for this document."
                warnings.append(f"{dr.filename}: extraction failed.")
                continue
            # Stable ids so user edits survive re-runs: <doc>-<key>-<n>
            counts: dict[str, int] = {}
            for f in fs:
                n = counts.get(f.key, 0)
                counts[f.key] = n + 1
                f.id = f"{doc.document_id[:8]}-{f.key}-{n}"
            dr.status, dr.extraction_method = "processed", method
            if method == "none":
                warnings.append(f"{dr.filename}: no text layer and no vision model configured, so nothing "
                                "could be extracted. Add ANTHROPIC_API_KEY to read scans and photos.")
            fields.extend(fs)
    _progress(state, "extract")
    return {"fields": fields, "warnings": warnings}


def node_normalize(state: ClaimState) -> dict:
    overrides = _overrides.get(state["claim_id"], {})
    for f in state["fields"]:
        o = overrides.get(f.id)
        if not o:
            continue
        if o.get("value") is not None and str(o["value"]).strip():
            if f.key in ("line_item", "waiting_period"):
                f.value = nz.parse_amount(o["value"])  # raw_text keeps the description
            else:
                f.raw_text = str(o["value"])
                f.value = nz.normalize_value(f.key, o["value"])
            f.method = "user"
        f.user_confirmed = bool(o.get("confirm", True))
        f.confidence = 1.0 if f.user_confirmed else f.confidence
    _progress(state, "normalize")
    return {"fields": state["fields"]}


def node_policy(state: ClaimState) -> dict:
    by_id = {d.id: d for d in state["documents"]}
    policies = [d for d in state["docs"] if by_id[d.document_id].doc_type == "policy"]
    warnings = list(state.get("warnings", []))
    clauses: list[PolicyClause] = []
    summary: PolicySummary | None = None
    if not policies:
        warnings.append("No policy document uploaded, so policy clauses could not be checked.")
    for doc in policies:
        try:
            clauses.extend(build_clauses(doc))
            s = build_summary(doc, clauses, state["calls"])
            summary = s if summary is None or summary_is_empty(summary) else summary
        except Exception as e:
            log.warning("policy stage failed: %s", type(e).__name__)
            warnings.append(f"{doc.filename}: policy could not be fully analysed.")
    _progress(state, "policy")
    return {"clauses": clauses, "policy_summary": summary, "warnings": warnings}


def node_verify(state: ClaimState) -> dict:
    checklist = build_checklist(state["claim"].claim_type.value, state["documents"], state["fields"])
    ctx = VerificationContext(
        claim=state["claim"], documents=state["documents"], fields=state["fields"],
        policy_summary=state.get("policy_summary"), clauses=state.get("clauses", []), checklist=checklist,
        page_texts={d.document_id: [p.text for p in d.pages] for d in state["docs"]})
    findings: list[Finding] = []
    warnings = list(state.get("warnings", []))
    try:
        from app.modules.verification.service import run_verification  # Person 2 (M3)
    except ImportError:
        run_verification = None
    if run_verification is not None:
        try:
            for f in run_verification(ctx) or []:
                findings.append(f if isinstance(f, Finding) else Finding.model_validate(f))  # I1 enforced
        except Exception as e:
            log.warning("verification failed: %s\n%s", type(e).__name__, traceback.format_exc())
            warnings.append("Consistency checks could not run completely.")
    _results[state["claim_id"]].checklist = checklist
    _progress(state, "verify")
    return {"findings": findings, "warnings": warnings}


def node_policy_match(state: ClaimState) -> dict:
    clauses = state.get("clauses", [])
    for f in state["findings"]:
        if f.clause_links or not clauses:
            continue
        try:
            f.clause_links = link_finding(f, clauses, state["calls"])
        except Exception as e:
            log.warning("policy_match failed: %s", type(e).__name__)
    # Grounding gate (I2): drop links whose clause is unknown.
    known = {c.id for c in clauses}
    for f in state["findings"]:
        f.clause_links = [link for link in f.clause_links if link.clause_id in known]
    _progress(state, "policy_match")
    return {"findings": state["findings"]}


def node_explain_plan(state: ClaimState) -> dict:
    res = _results[state["claim_id"]]
    res.action_plan = build_plan(state["findings"], res.checklist, state["fields"], state.get("clauses", []),
                                 _done_actions.get(state["claim_id"]))
    _progress(state, "explain_plan")
    return {}


def node_finalize(state: ClaimState) -> dict:
    res = _results[state["claim_id"]]
    res.documents = state["documents"]
    res.fields = state["fields"]
    res.findings = state["findings"]
    res.clauses = state.get("clauses", [])
    res.policy_summary = state.get("policy_summary")
    res.llm_calls = state["calls"]
    res.providers_used = sorted({c.provider for c in state["calls"] if c.ok})
    res.warnings = state.get("warnings", [])
    res.readiness_status, res.readiness_explanation = readiness(res.checklist, res.findings)
    blocking = sum(1 for f in res.findings if f.blocking and f.status == "open") + sum(
        1 for a in res.action_plan if a.group == "upload" and a.blocking and not a.done)
    res.packet_status = f"INCOMPLETE - {blocking} blocking items" if blocking else "Prepared for submission"
    _progress(state, "finalize")
    res.status = RunStatus.COMPLETE
    return {}


def _build_graph():
    g = StateGraph(ClaimState)
    nodes = [("ingest", node_ingest), ("classify", node_classify), ("extract", node_extract),
             ("normalize", node_normalize), ("policy", node_policy), ("verify", node_verify),
             ("policy_match", node_policy_match), ("explain_plan", node_explain_plan),
             ("finalize", node_finalize)]
    for name, fn in nodes:
        g.add_node(name, fn)
    g.add_edge(START, nodes[0][0])
    for (a, _), (b, _) in zip(nodes, nodes[1:]):
        g.add_edge(a, b)
    g.add_edge(nodes[-1][0], END)
    return g.compile()


GRAPH = _build_graph()


# ------------------------------------------------------------------ entry points


def start(claim: ClaimOut) -> AnalysisResults:
    """Mark the claim as processing. Call run() afterwards (background task)."""
    res = AnalysisResults(claim_id=claim.id, status=RunStatus.PROCESSING, stage="Queued", progress=0.0,
                          stages=[s for _, s in STAGES])
    prev = _results.get(claim.id)
    if prev:  # keep showing previous results while the re-check runs
        res = prev.model_copy(update={"status": RunStatus.PROCESSING, "stage": "Queued", "progress": 0.0,
                                      "error": None})
    _results[claim.id] = res
    return res


def run(claim_id: str) -> None:
    lock = _locks.setdefault(claim_id, threading.Lock())
    if not lock.acquire(blocking=False):
        return  # a run is already in progress
    try:
        claim = claim_store.get_claim(claim_id)
        if claim is None:
            return
        GRAPH.invoke({"claim_id": claim_id, "claim": claim, "calls": [], "warnings": []})
    except Exception as e:
        log.error("pipeline failed: %s\n%s", type(e).__name__, traceback.format_exc())
        res = _results.get(claim_id)
        if res:
            res.status, res.error = RunStatus.FAILED, f"Analysis failed ({type(e).__name__}). Please try again."
    finally:
        lock.release()


def input_hashes(claim: ClaimOut) -> list[str]:
    return [d.sha256 for d in claim.documents]


def run_fingerprint(claim: ClaimOut) -> str:
    return hashlib.sha1("|".join(sorted(input_hashes(claim))).encode()).hexdigest()[:12]


__all__ = ["start", "run", "get_results", "set_override", "set_action_done", "forget", "reset", "llm"]
