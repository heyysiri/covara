"""Document-type helpers shared by extraction and verification."""

from __future__ import annotations

import re


def reference_type(text: str) -> str:
    """Canonical document type for a free-text reference ("prescription no. RX-7781" -> "prescription")."""
    t = text.lower()
    for kind, words in (("prescription", ("prescription", "medicine", "medication")),
                        ("diagnostic_report", ("report", "lab", "investigation", "scan", "x-ray", "xray", "mri",
                                               "ultrasound", "usg", "ecg", "test")),
                        ("discharge_summary", ("discharge",)),
                        ("final_bill", ("bill", "invoice")), ("payment_receipt", ("receipt",))):
        if any(w in t for w in words):
            return kind
    return re.sub(r"\W+", "_", t).strip("_")
