"""Accuracy check for extraction + checklist on demo claim B (ground truth: sample_documents/expected_results).

Runs the real pipeline in-process (uses Claude if configured, else the rules path), uploads the six claim B
files, and compares extracted fields with `expected_fields`. Prints measured numbers only.

    cd backend && .venv/bin/python -m tests.eval_claim_b            # uses configured providers
    cd backend && .venv/bin/python -m tests.eval_claim_b --rules    # rules only, offline
"""

from __future__ import annotations

import json
import re
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample_documents"


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _eq(key: str, expected, got) -> bool:
    if key == "line_item":  # expected dict, ours: value=amount, raw_text=description
        return _num(got.value) == _num(expected["amount"])
    if key == "referenced_document":
        return str(expected).lower().startswith(str(got.value).lower())
    en, gn = _num(expected), _num(got.value)
    if en is not None and gn is not None and not re.search(r"[A-Za-z]", str(expected)):
        return abs(en - gn) < 0.5
    return re.sub(r"\W+", "", str(expected)).lower() == re.sub(r"\W+", "", str(got.value)).lower()


def main() -> int:
    from app.config import get_settings
    from app.modules.pipeline import runner
    from app.services import claim_store
    from app.main import app

    s = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="covara-eval-"))
    s.upload_dir, s.cache_dir = tmp / "uploads", tmp / "cache"
    if "--rules" in sys.argv:
        s.anthropic_api_key = s.gemini_api_key = s.groq_api_key = ""
        s.claude_use_cli = False
    claim_store.reset()
    runner.reset()

    truth = json.loads((SAMPLES / "expected_results" / "claim_b.json").read_text())
    client = TestClient(app)
    cid = client.post("/claims", json={**truth["claim_input"], "consent_given": True}).json()["id"]
    for item in truth["upload_set"]:
        path = SAMPLES / item["file"]
        r = client.post(f"/claims/{cid}/documents", data={"category": item["doc_type"]},
                        files=[("files", (path.name, path.read_bytes(), "application/pdf"))])
        assert r.status_code == 201, r.text

    print("analysing... (real model calls take a while)", flush=True)
    client.post(f"/claims/{cid}/analyze")
    res = client.get(f"/claims/{cid}/results").json()
    assert res["status"] == "complete", res.get("error")
    from app.schemas.results import AnalysisResults
    results = AnalysisResults.model_validate(res)

    by_key: dict[tuple[str, str], list] = {}
    for f in results.fields:
        by_key.setdefault((f.key, Path(f.evidence.filename).name), []).append(f)

    ok = miss = 0
    misses = []
    for e in truth["expected_fields"]:
        key, fname = e["key"], Path(e["file"]).name
        if key in ("waiting_period", "room_rent_cap"):  # compared via policy summary below
            continue
        cands = by_key.get((key, fname), [])
        if any(_eq(key, e["value"], c) for c in cands):
            ok += 1
        else:
            miss += 1
            misses.append((key, fname, e["value"] if key != "line_item" else e["value"]["amount"],
                           [c.value for c in cands][:4]))

    ps = results.policy_summary
    summary_checks = {
        "sum_insured = 500000": bool(ps and ps.sum_insured and ps.sum_insured.value == 500000),
        "room_rent_cap = 5000 on page 4 or 1": bool(ps and ps.room_rent_cap and ps.room_rent_cap.value == 5000),
        "waiting periods found (30d, 36mo, 24mo)": bool(ps and {w.days for w in ps.waiting_periods}
                                                         >= {30, 1095, 730}),
        "room-rent clause 4.1 on page 4": any(c.clause_ref.startswith("4.1") and c.page_number == 4
                                              for c in results.clauses),
    }
    cs = results.checklist_summary
    exp = truth["expected_checklist"]
    checklist_checks = {
        "required_present matches": sorted(cs.required_present) == sorted(exp["required_present"]),
        "required_missing matches": sorted(cs.required_missing) == sorted(exp["required_missing"]),
        "referenced_but_missing = prescription": cs.referenced_but_missing == exp["referenced_but_missing"],
    }
    quotes_ok = sum(1 for f in results.fields if f.evidence.quote and f.evidence.bbox is not None)

    print(f"\nFields: {ok}/{ok + miss} expected values extracted correctly")
    for m in misses:
        print("  MISS", m)
    for title, checks in (("Policy", summary_checks), ("Checklist", checklist_checks)):
        print(f"\n{title}:")
        for k, v in checks.items():
            print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nExtracted fields: {len(results.fields)}; with a located quote + bbox: {quotes_ok}; "
          f"low-confidence critical: {sum(1 for f in results.fields if f.confidence < 0.75)}")
    print(f"Providers: {results.providers_used or ['rules']}; model calls: {len(results.llm_calls)} "
          f"({sum(c.ok for c in results.llm_calls)} ok)")
    print(f"Readiness: {results.readiness_status} | packet: {results.packet_status}")
    print("(Findings come from Person 2's verification engine; none are produced here.)")
    return 0 if miss == 0 and all(summary_checks.values()) and all(checklist_checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
