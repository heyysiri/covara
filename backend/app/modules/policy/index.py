"""policy_index: split the uploaded policy into clause-level chunks with page references.

Chunk by numbered headings (clause id, title, page, full text). Chunks never cross a page, so every
clause's text exists verbatim on its page (I2). Falls back to paragraph chunks when there are no
numbered headings.
"""

from __future__ import annotations

import re
import uuid

from app.modules.extraction.ingest import IngestedDoc
from app.schemas.results import ClauseType, PolicyClause

_HEADING = re.compile(r"^\s*(?:(?:section|clause|article)\s+)?(\d{1,2}(?:\.\d{1,2}){0,3})[.):]?\s+(.{2,})$", re.I)
_UNIT_START = re.compile(r"^(days?|months?|years?|%|lakh|lac|crore|rs|inr|₹|x|times|hours?)\b", re.I)


def _is_heading(line: str) -> tuple[str, str] | None:
    m = _HEADING.match(line)
    if not m:
        return None
    ref, rest = m.group(1), m.group(2).strip()
    if int(ref.split(".")[0]) > 40 or _UNIT_START.match(rest) or not rest[0].isalpha() or not rest[0].isupper():
        return None
    title = re.split(r"[:–—]|\s-\s", rest, maxsplit=1)[0].strip()
    if len(title) > 70:
        title = " ".join(title.split()[:8])
    return ref, title.rstrip(".")


def classify_clause(title: str, text: str) -> ClauseType:
    t, x = title.lower(), text.lower()
    if "exclu" in t or "not covered" in t:
        return "exclusion"
    if "waiting" in t:
        return "waiting_period"
    if "definition" in t or re.search(r"\bmeans\b", x[:200]) and len(t.split()) <= 4 and "defin" in x[:300]:
        return "definition"
    if re.search(r"room\s*rent|sub-?\s?limit|limit|capping|ceiling", t):
        return "sublimit"
    if re.search(r"co-?\s?pay|condition|claim|procedure|document|notif|intimation|deductible", t):
        return "condition"
    if "exclu" in x[:300] or "not covered" in x[:300] or "not payable" in x[:300]:
        return "exclusion"
    if "waiting period" in x[:300]:
        return "waiting_period"
    if re.search(r"room\s*rent", x[:300]):
        return "sublimit"
    return "coverage"


def build_clauses(doc: IngestedDoc) -> list[PolicyClause]:
    clauses: list[PolicyClause] = []
    current: dict | None = None

    def flush():
        nonlocal current
        if current and "\n".join(current["lines"]).strip():
            text = "\n".join(current["lines"]).strip()
            clauses.append(PolicyClause(
                id=uuid.uuid4().hex[:10], clause_ref=current["ref"],
                type=classify_clause(current["title"], text), title=current["title"], text=text,
                document_id=doc.document_id, filename=doc.filename, page_number=current["page"]))
        current = None

    for page in doc.pages:
        if current:  # continue the open clause on the new page as its own chunk
            ref, title = current["ref"], current["title"]
            flush()
            current = {"ref": ref, "title": f"{title} (cont.)", "page": page.number, "lines": [],
                       "cont": True}
        for line in page.text.splitlines():
            h = _is_heading(line)
            if h:
                flush()
                current = {"ref": h[0], "title": h[1], "page": page.number, "lines": [line.strip()]}
            elif current is not None:
                current["lines"].append(line.rstrip())
    flush()
    # Drop empty continuation chunks and tiny heading-only chunks.
    clauses = [c for c in clauses if len(c.text) > len(c.title) + 5 or not c.title.endswith("(cont.)")]

    if len(clauses) < 2:  # no numbered structure: paragraph chunks
        clauses = []
        for page in doc.pages:
            for n, para in enumerate(re.split(r"\n\s*\n", page.text), 1):
                para = para.strip()
                if len(para) < 40:
                    continue
                title = " ".join(para.split()[:8])
                clauses.append(PolicyClause(
                    id=uuid.uuid4().hex[:10], clause_ref=f"p{page.number}.{n}",
                    type=classify_clause(title, para), title=title, text=para,
                    document_id=doc.document_id, filename=doc.filename, page_number=page.number))
    return clauses
