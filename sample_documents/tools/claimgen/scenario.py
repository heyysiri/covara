"""A synthetic claim as pure data. Documents and ground truth are both derived from it.

Nothing in the generator code is specific to one claim: change the data and the PDFs, the expected fields
and the expected findings all follow. Everything is fictional.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


def fmt_date(d: date) -> str:
    return f"{d.day:02d}-{d.strftime('%b')}-{d.year}"  # 12-Aug-2026


def inr(n: float) -> str:
    """Indian digit grouping: 500000 -> 5,00,000."""
    s = str(int(round(n)))
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def rs(n: float) -> str:
    return f"Rs. {inr(n)}.00"


_ONES = ["", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven", "Twelve", "Thirteen",
         "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"]
_TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def words(n: int) -> str:
    """Indian-system number to words: 85000 -> 'Eighty Five Thousand'."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return (_TENS[n // 10] + " " + _ONES[n % 10]).strip()
    if n < 1000:
        return (_ONES[n // 100] + " Hundred " + words(n % 100)).strip()
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if n >= size:
            return (words(n // size) + f" {name} " + words(n % size)).strip()
    return ""


def human_list(items: list[str]) -> str:
    """['a', 'b', 'c'] -> 'A, b and c'."""
    items = [i.strip() for i in items if i.strip()]
    text = items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]
    return text[:1].upper() + text[1:]


@dataclass
class Line:
    description: str
    qty: int
    rate: int
    associated: bool = False  # does this synthetic policy's definition treat it as an associated expense?

    @property
    def amount(self) -> int:
        return self.qty * self.rate


@dataclass
class Scenario:
    key: str  # "a", "b", "c": file prefix claim_<key>_*
    title: str
    # ---- insured person and policy
    insurer: str
    product: str
    policy_no: str
    member_id: str
    patient: str
    salutation: str
    age: int
    sex: str
    inception: date  # first enrolment
    period_start: date
    period_end: date
    sum_insured: int
    room_cap_pct: float = 1.0  # room rent limit as % of sum insured per day
    initial_wait_days: int = 30
    preexisting_months: int = 36
    specified_months: int = 24
    specified_conditions: list[str] = field(default_factory=list)
    pre_hosp_days: int = 30
    post_hosp_days: int = 60
    icu_pct: float = 2.0
    claim_days_limit: int = 30
    exclusions: list[tuple[str, str]] = field(default_factory=list)  # (title, sentence), shown under Section 6
    # The policy's own wording of clause 1.4 (what counts as an associated expense). Synthetic policy text; the
    # `associated` flag on each bill line must agree with it, which is what the expected exposure is computed from.
    definition_included: str = ""  # "nursing charges, surgeon and anaesthetist fees, ..."
    definition_excluded: str = ""  # "Medicines, diagnostics and registration charges"
    # ---- hospital stay
    hospital: str = ""
    hospital_address: str = ""
    uhid: str = ""
    invoice_no: str = ""
    bill_date: date | None = None
    admission: date | None = None
    discharge: date | None = None
    surgery: date | None = None
    diagnosis: str = ""
    procedure: str = ""
    course_text: str = ""
    condition_text: str = "Stable, tolerating oral diet, wound clean."
    follow_up: str = ""
    doctor: str = ""
    doctor_role: str = "Consultant"
    doctor_reg: str = ""
    rx_no: str = ""
    rx_items: list[str] = field(default_factory=list)
    receipt_no: str = ""
    receipt_mode: str = "UPI"
    lines: list[Line] = field(default_factory=list)  # the first line is the room when `room_line` is set
    room_line: bool = True
    summary: list[tuple[str, list[int]]] = field(default_factory=list)  # final-bill buckets: (label, line indexes)
    # ---- what the user types on the claim form
    claimed_amount: int = 0
    # ---- defects deliberately planted (everything else is consistent)
    receipt_name: str | None = None  # a different spelling on the receipt
    duplicate_bill: bool = False  # a reprinted copy of the final bill is also uploaded
    rx_referenced: bool = False  # the discharge summary refers to a prescription
    rx_uploaded: bool = False  # ...and it is part of the upload (False = held back for the live fix)
    diagnosis_date: date | None = None

    # ---- derived
    @property
    def total(self) -> int:
        return sum(l.amount for l in self.lines)

    @property
    def room(self) -> Line | None:
        return self.lines[0] if self.room_line and self.lines else None

    @property
    def room_cap(self) -> int:
        return round(self.sum_insured * self.room_cap_pct / 100)

    @property
    def stay_days(self) -> int:
        return (self.discharge - self.admission).days  # type: ignore[operator]

    @property
    def receipt_display_name(self) -> str:
        return self.receipt_name or self.patient

    def check(self) -> None:
        assert self.lines and self.summary, "a scenario needs bill lines and a summary"
        assert sum(sum(self.lines[i].amount for i in idx) for _, idx in self.summary) == self.total, "summary must add up to the total"
        assert sorted(i for _, idx in self.summary for i in idx) == list(range(len(self.lines))), "every line is in exactly one bucket"
        assert self.period_start <= self.admission <= self.discharge <= self.period_end  # type: ignore[operator]
