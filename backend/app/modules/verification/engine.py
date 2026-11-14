"""Verification engine entry point: run every rule over normalised claim data.

    result = run_verification(fields, documents, claim)
    result.findings       -> list[Finding]  (each with evidence, rule id, stored inputs)
    result.checks_passed  -> list[str]      ("items that appear consistent")

Pure Python, no network, no LLM. Input values are expected to be normalised by the
`normalize` pipeline node (ISO dates, numeric amounts); the helpers also tolerate common
raw formats such as "12-Aug-2026" or "Rs. 85,000".
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.contract import ClaimInput, DocumentInfo, ExtractedField, Finding, Severity

from .rules import RULES, Ctx

_SEVERITY_ORDER = {Severity.HIGH: 0, Severity.MEDIUM: 1, Severity.LOW: 2}


@dataclass
class VerificationResult:
    findings: list[Finding]
    checks_passed: list[str]
    rules_run: list[str]


def run_verification(
    fields: list[ExtractedField], documents: list[DocumentInfo], claim: ClaimInput | None = None
) -> VerificationResult:
    ctx = Ctx(fields=fields, documents=documents, claim=claim or ClaimInput())
    for rule in RULES:
        rule(ctx)
    findings = sorted(ctx.findings, key=lambda f: (not f.blocking, _SEVERITY_ORDER[f.severity], f.rule_id))
    return VerificationResult(
        findings=findings,
        checks_passed=[p.text for p in ctx.passed],
        rules_run=[r.__name__ for r in RULES],
    )
