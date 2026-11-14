"""Verification thresholds in one place (nothing tuned to a particular claim).

Defaults reuse the pipeline's shared values (critical fields, review threshold) so the two cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.results import CRITICAL_KEYS, REVIEW_THRESHOLD


@dataclass(frozen=True)
class VerificationConfig:
    amount_tolerance_inr: float = 0.5  # two amounts closer than this are the same amount
    line_item_tolerance_inr: float = 1.0  # rounding allowed when line items are summed against a total
    name_variant_ratio: float = 0.9  # fuzzy similarity above which two names count as a likely variation
    low_confidence: float = REVIEW_THRESHOLD  # critical fields below this go to the user for confirmation
    critical_keys: frozenset[str] = frozenset(CRITICAL_KEYS)
    # words too generic to prove that a diagnosis is the waiting-period condition the policy names
    condition_stopwords: frozenset[str] = frozenset({
        "acute", "chronic", "severe", "mild", "surgery", "surgical", "treatment", "procedure",
        "disease", "diseases", "condition", "conditions", "syndrome", "disorder"})
    min_condition_word_len: int = 5


DEFAULT_CONFIG = VerificationConfig()
