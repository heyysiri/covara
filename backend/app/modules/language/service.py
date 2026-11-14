"""Plain-language summary of an analysis, for reading aloud and for showing in the user's language.

Built only from structured results (findings, actions, passed checks): nothing here can invent a value.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Literal

from pydantic import BaseModel, Field

from app.core import sarvam
from app.schemas.results import AnalysisResults, Finding, ReadinessStatus

SOURCE_KINDS = Literal["finding", "clause", "action", "field"]


class Source(BaseModel):
    kind: SOURCE_KINDS
    id: str
    title: str
    document_id: str | None = None
    filename: str | None = None
    page: int | None = None
    quote: str | None = None


class SummaryItem(BaseModel):
    id: str
    title: str
    detail: str = ""
    blocking: bool = False
    owner: str | None = None
    source: Source | None = None
    draft_message: str | None = None


class Summary(BaseModel):
    readiness: ReadinessStatus | None
    headline: str
    issues: list[SummaryItem] = Field(default_factory=list)
    steps: list[SummaryItem] = Field(default_factory=list)
    consistent: list[str] = Field(default_factory=list)
    packet_status: str | None = None
    speech: str = ""  # what the voice reads
    lang: str = "en-IN"
    translated: bool = True


def _doc_source(f: Finding, kind: SOURCE_KINDS = "finding") -> Source:
    ev = next((e for e in f.evidence if e.source == "document"), None)
    return Source(kind=kind, id=f.id, title=f.title, document_id=ev.document_id if ev else None,
                  filename=ev.filename if ev else None, page=ev.page_number if ev else None,
                  quote=ev.quote if ev else None)


# ------------------------------------------------------------------ summary


def build_summary(res: AnalysisResults) -> Summary:
    open_f = [f for f in res.findings if f.status == "open"]
    open_f.sort(key=lambda f: (not f.blocking, {"high": 0, "medium": 1, "low": 2}[f.severity.value]))
    issues = [SummaryItem(id=f.id, title=f.title, detail=f.description[:220], blocking=f.blocking,
                          source=_doc_source(f)) for f in open_f[:5]]
    steps = [SummaryItem(id=a.id, title=a.title, detail=(a.how[0] if a.how else a.why)[:200], blocking=a.blocking,
                         owner=a.owner, draft_message=a.draft_message)
             for a in res.action_plan if not a.done][:4]
    ready = res.readiness_status
    blocking = sum(1 for f in open_f if f.blocking) + sum(
        1 for a in res.action_plan if a.group == "upload" and a.blocking and not a.done and not a.finding_ids)
    if ready == ReadinessStatus.READY:
        headline = "Your claim looks ready to submit. I found nothing that needs fixing."
    elif ready == ReadinessStatus.INCOMPLETE:
        headline = res.readiness_explanation or "Your claim is incomplete: key documents are missing."
    else:
        headline = (f"Your claim needs attention: {blocking} thing{'s' if blocking != 1 else ''} to fix before you "
                    f"submit." if blocking else "Your claim is nearly there. A few things are worth a look.")
    speech = headline
    if issues:
        speech += " Here is what I found. " + " ".join(f"{i + 1}. {it.title}." for i, it in enumerate(issues[:3]))
    if steps:
        speech += f" Next step: {steps[0].title}."
    return Summary(readiness=ready, headline=headline, issues=issues, steps=steps,
                       consistent=res.checks_passed[:4], packet_status=res.packet_status, speech=speech)


def localize_summary(s: Summary, lang: str) -> Summary:
    if lang == "en-IN" or not sarvam.available():
        return s
    strings: list[str] = [s.headline, s.speech]
    for it in s.issues + s.steps:
        strings += [it.title, it.detail]
    strings += s.consistent
    uniq = [x for x in dict.fromkeys(strings) if x.strip()]
    try:
        with ThreadPoolExecutor(max_workers=4) as pool:
            done = dict(zip(uniq, pool.map(lambda x: sarvam.translate(x, lang), uniq)))
    except sarvam.SarvamError:
        return s.model_copy(update={"lang": lang, "translated": False})
    tr = lambda x: done[x][0] if x in done else x
    out = s.model_copy(deep=True)
    out.headline, out.speech = tr(s.headline), tr(s.speech)
    for it in out.issues + out.steps:
        it.title, it.detail = tr(it.title), tr(it.detail)
    out.consistent = [tr(x) for x in s.consistent]
    out.lang = lang
    out.translated = all(ok for _, ok in done.values())
    return out
