"""Normalise raw values: dates -> ISO, amounts -> float INR, names -> cleaned title case."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}

DATE_KEYS = {"policy_start", "policy_end", "policy_inception", "admission_date", "discharge_date", "diagnosis_date",
             "bill_date", "receipt_date"}
AMOUNT_KEYS = {"sum_insured", "room_rent_charged_per_day", "bill_total", "receipt_amount"}
NAME_KEYS = {"patient_name", "policyholder_name"}

_TITLES = re.compile(r"^(mr|mrs|ms|miss|dr|shri|smt|kumari|master|baby)\.?\s+", re.I)


HINDI_MONTHS = {"जनवरी": "jan", "फ़रवरी": "feb", "फरवरी": "feb", "मार्च": "mar", "अप्रैल": "apr", "मई": "may",
                "जून": "jun", "जुलाई": "jul", "अगस्त": "aug", "सितंबर": "sep", "सितम्बर": "sep", "अक्तूबर": "oct",
                "अक्टूबर": "oct", "नवंबर": "nov", "नवम्बर": "nov", "दिसंबर": "dec", "दिसम्बर": "dec"}


def ascii_digits(s: str) -> str:
    """Devanagari / Bengali / Tamil / ... digits -> 0-9."""
    return "".join(str(unicodedata.decimal(ch)) if unicodedata.decimal(ch, None) is not None else ch for ch in s)


def parse_date(raw: str | None) -> str | None:
    if not raw:
        return None
    s = ascii_digits(raw).strip().lower().replace(",", " ")
    for hi, en in HINDI_MONTHS.items():
        s = s.replace(hi, en)
    m = re.search(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s)
    if m:
        y, mo, d = map(int, m.groups())
        return _iso(y, mo, d)
    m = re.search(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})", s)
    if m:  # Indian convention: day first
        d, mo, y = map(int, m.groups())
        return _iso(y + 2000 if y < 100 else y, mo, d)
    m = re.search(r"(\d{1,2})(?:st|nd|rd|th)?[\s\-/]+([a-z]{3})[a-z]*\.?[\s\-/]+(\d{2,4})", s)
    if m and m.group(2) in MONTHS:
        y = int(m.group(3))
        return _iso(y + 2000 if y < 100 else y, MONTHS[m.group(2)], int(m.group(1)))
    m = re.search(r"([a-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?\s+(\d{4})", s)
    if m and m.group(1) in MONTHS:
        return _iso(int(m.group(3)), MONTHS[m.group(1)], int(m.group(2)))
    return None


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def parse_amount(raw: str | float | int | None) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    s = ascii_digits(raw).lower().replace("₹", " ").replace("inr", " ").replace("rs.", " ").replace("rs", " ")
    s = s.replace("/-", " ")
    m = re.search(r"(\d[\d,]*(?:\.\d+)?)\s*(lakh|lac|crore|cr)?", s)
    if not m:
        return None
    n = float(m.group(1).replace(",", ""))
    mult = {"lakh": 1e5, "lac": 1e5, "crore": 1e7, "cr": 1e7}.get(m.group(2) or "", 1)
    return round(n * mult, 2)


def clean_name(raw: str | None) -> str | None:
    if not raw:
        return None
    s = re.sub(r"\s+", " ", raw).strip(" .,:;-")
    while _TITLES.match(s):
        s = _TITLES.sub("", s, count=1)
    return s.title() or None


def normalize_value(key: str, raw: str | float | None) -> str | float | None:
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return None
    if isinstance(raw, str) and key not in NAME_KEYS:
        raw = ascii_digits(raw)
    if key in DATE_KEYS:
        return parse_date(str(raw))
    if key in AMOUNT_KEYS:
        return parse_amount(raw)
    if key in NAME_KEYS:
        return clean_name(str(raw))
    if key == "age":
        m = re.search(r"\d{1,3}", str(raw))
        return float(m.group()) if m else None
    return re.sub(r"\s+", " ", str(raw)).strip()
