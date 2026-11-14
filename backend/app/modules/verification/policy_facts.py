"""Policy values the policy-aware rules (V10, V11) need. Built from the pipeline's PolicySummary and clauses.

Kept separate from the schemas so the engine stays pure: no LLM, no I/O. Every value carries the
EvidenceRef of the policy page it was read from, so a finding can cite the policy as well as the bill.

Nothing here is tuned to a particular policy: which bill lines count as "associated expenses" is read from
the uploaded policy's own definition, in whatever words that policy uses.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field

from app.schemas.contract import EvidenceRef

# words that carry no meaning when matching a bill line to a term in the policy's definition
_FILLER = {
    "fee", "fees", "charge", "charges", "expense", "expenses", "cost", "costs", "incurred", "the", "a", "an", "of",
    "for", "and", "or", "other", "related", "all", "any", "such", "during", "hospitalisation", "hospitalization",
    "in", "to", "by", "with", "on", "at", "as",
}


def _stem(word: str) -> str:
    w = word.lower().replace("ae", "e")  # anaesthetist / anesthetist
    if w.endswith("ing") and len(w) > 5:
        return w[:-3]
    if w.endswith("s") and len(w) > 3:
        return w[:-1]
    return w


def significant_words(text: str) -> frozenset[str]:
    """The meaningful, stemmed words of a phrase: 'Operation theatre charges' -> {operation, theatre}."""
    return frozenset(_stem(w) for w in re.findall(r"[a-z]+", text.lower()) if w not in _FILLER)


@dataclass
class AssociatedExpenses:
    """Which bill lines the policy's room-rent clause treats as 'associated expenses'."""

    included: list[frozenset[str]]  # each term is a set of words that must all appear in the bill line
    excluded: list[frozenset[str]]
    quote: str  # the defining sentence, verbatim from the policy
    evidence: EvidenceRef

    def classify(self, description: str) -> str | None:
        """'associated', 'excluded' (named as not associated), or None (the policy says nothing about it)."""
        words = significant_words(description)
        if any(t and t <= words for t in self.excluded):
            return "excluded"
        if any(t and t <= words for t in self.included):
            return "associated"
        return None


@dataclass
class WaitingFact:
    name: str  # e.g. "Initial waiting period"
    days: int
    evidence: EvidenceRef  # policy page + the sentence it came from


@dataclass
class PolicyFacts:
    room_rent_cap_per_day: float | None = None  # INR per day
    room_rent_cap_evidence: EvidenceRef | None = None
    waiting_periods: list[WaitingFact] = field(default_factory=list)
    associated_expenses: AssociatedExpenses | None = None


# "Associated Medical Expenses means / include / are  A, B and C incurred during ..."
_INCLUDE = re.compile(
    r"associated\s+(?:medical\s+)?expenses?\s+(?:means|mean|include|includes|are|shall\s+include|shall\s+mean)\s+(?P<body>[^.]+)",
    re.I,
)
# "X, Y and Z are not Associated Medical Expenses"  /  "X, Y are excluded from associated expenses"
_EXCLUDE = re.compile(
    r"(?P<body>[^.]*?)\s+(?:are|is|shall\s+be)\s+(?:not\s+(?:considered\s+|treated\s+as\s+)?(?:an?\s+)?associated"
    r"|excluded\s+from\s+(?:the\s+)?(?:definition\s+of\s+)?associated)\s*(?:medical\s+)?expenses?",
    re.I,
)
_TAIL = re.compile(r"\s+(?:incurred|during|which|that|provided|where|when|while)\b.*$", re.I | re.S)
_SPLIT = re.compile(r",|;|\band\b|\bor\b", re.I)


def _terms(body: str) -> list[frozenset[str]]:
    out = []
    for part in _SPLIT.split(_TAIL.sub("", body)):
        words = significant_words(part)
        if words:
            out.append(words)
    return out


def parse_associated_expenses(clause_text: str, document_id: str, filename: str, page_number: int) -> AssociatedExpenses | None:
    """Read the policy's definition of associated expenses. None when the clause does not define them."""
    text = re.sub(r"\s+", " ", clause_text)
    m = _INCLUDE.search(text)
    if not m:
        return None
    included = _terms(m.group("body"))
    if not included:
        return None
    excluded = [t for e in _EXCLUDE.finditer(text) for t in _terms(e.group("body"))]
    quote = m.group(0).strip()
    evidence = EvidenceRef(document_id=document_id, filename=filename, page_number=page_number, quote=quote)
    return AssociatedExpenses(included=included, excluded=excluded, quote=quote, evidence=evidence)


def find_associated_expenses(clauses: Iterable) -> AssociatedExpenses | None:
    """First clause (anything with text, document_id, filename, page_number) that defines associated expenses."""
    for c in clauses:
        found = parse_associated_expenses(c.text, c.document_id, c.filename, c.page_number)
        if found:
            return found
    return None
