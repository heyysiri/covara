"""Pure helpers for the verification rules: parsing and name comparison. No network, no LLM."""

from __future__ import annotations

import re
from datetime import date, datetime
from difflib import SequenceMatcher
from typing import Any

_TITLES = {"mr", "mrs", "ms", "miss", "mx", "dr", "shri", "smt", "sri"}
_DATE_FORMATS = ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y")


def parse_amount(value: Any) -> float | None:
    """25000, '25,000.00', 'Rs. 25,000' -> number. Unknown -> None."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, dict):  # line items: {"amount": ...}
        return parse_amount(value.get("amount"))
    match = re.search(r"-?\d[\d,]*(?:\.\d+)?", str(value))
    if not match:
        return None
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return None


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def money(n: float | None) -> str:
    return "unknown" if n is None else (f"{n:,.0f}" if float(n).is_integer() else f"{n:,.2f}")


def norm_id(value: Any) -> str:
    """Policy numbers / member IDs: ignore case and spacing, keep hyphens as characters."""
    return re.sub(r"\s+", "", str(value or "")).upper()


def name_tokens(name: Any) -> list[str]:
    text = re.sub(r"[^a-z\s]", " ", str(name or "").lower().replace(".", " "))
    return [t for t in text.split() if t and t not in _TITLES]


def compare_names(a: Any, b: Any, variant_ratio: float = 0.9) -> str:
    """Return 'same', 'variant' (likely spelling/initial/middle-name variation) or 'different'."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return "different"
    if ta == tb:
        return "same"
    if sorted(ta) == sorted(tb):
        return "variant"  # same words, different order
    # initials, e.g. "ravi k sharma" vs "ravi kumar sharma"
    if len(ta) == len(tb) and all(x == y or (len(x) == 1 and y.startswith(x)) or (len(y) == 1 and x.startswith(y)) for x, y in zip(ta, tb)):
        return "variant"
    # dropped middle name, e.g. "ravi sharma" vs "ravi kumar sharma"
    if len(ta) != len(tb) and len(ta) >= 2 and len(tb) >= 2 and ta[0] == tb[0] and ta[-1] == tb[-1]:
        return "variant"
    if SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio() >= variant_ratio:
        return "variant"
    return "different"
