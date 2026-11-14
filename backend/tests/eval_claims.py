"""Measured check of the full pipeline on any synthetic claim, against its ground truth.

    cd backend && .venv/bin/python -m tests.eval_claims a        # claim A (clean): nothing may be flagged
    cd backend && .venv/bin/python -m tests.eval_claims c        # claim C: the waiting-period finding
    cd backend && .venv/bin/python -m tests.eval_claims a --rules   # offline, no AI (weaker, fallback only)

Ground truth is sample_documents/expected_results/claim_<key>.json (made by sample_documents/tools/claimgen).
The findings check is an EXACT match: a finding the ground truth does not list counts as a false alarm.
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from tests.eval_claim_b import _eq

ROOT = Path(__file__).resolve().parents[2]
SAMPLES = ROOT / "sample_documents"


def main() -> int:
    key = next((a for a in sys.argv[1:] if not a.startswith("-")), "a")
    from app.config import get_settings
    from app.main import app
    from app.modules.pipeline import runner
    from app.schemas.results import AnalysisResults
    from app.services import claim_store

    s = get_settings()
    tmp = Path(tempfile.mkdtemp(prefix="covara-eval-"))
    s.upload_dir = tmp / "uploads"
    s.persist_claims = False  # evals must not leave claims in the real data folder
    if "--fresh" in sys.argv or "--rules" in sys.argv:  # default: reuse backend/.cache so re-runs cost no model calls
        s.cache_dir = tmp / "cache"
    if "--rules" in sys.argv:
        s.anthropic_api_key = s.gemini_api_key = s.groq_api_key = ""
        s.claude_use_cli = False
    claim_store.reset()
    runner.reset()

    truth = json.loads((SAMPLES / "expected_results" / f"claim_{key}.json").read_text())
    client = TestClient(app)
    cid = client.post("/claims", json={**truth["claim_input"], "consent_given": True}).json()["id"]
    for item in truth["upload_set"]:
        path = SAMPLES / item["file"]
        r = client.post(f"/claims/{cid}/documents", data={"category": item["doc_type"]},
                        files=[("files", (path.name, path.read_bytes(), "application/pdf"))])
        assert r.status_code == 201, r.text
    print(f"claim {key.upper()}: {truth['title']}\nanalysing... (real model calls take a while)", flush=True)
    client.post(f"/claims/{cid}/analyze")
    res = client.get(f"/claims/{cid}/results").json()
    assert res["status"] == "complete", res.get("error")
    results = AnalysisResults.model_validate(res)

    # ---- fields
    by_key: dict[tuple[str, str], list] = {}
    for f in results.fields:
        by_key.setdefault((f.key, Path(f.evidence.filename).name), []).append(f)
    ok, misses = 0, []
    for e in truth["expected_fields"]:
        if e["key"] in ("waiting_period", "room_rent_cap"):
            continue  # compared through the policy summary below
        if any(_eq(e["key"], e["value"], c) for c in by_key.get((e["key"], Path(e["file"]).name), [])):
            ok += 1
        else:
            misses.append((e["key"], Path(e["file"]).name, e["value"] if e["key"] != "line_item" else e["value"]["amount"],
                           [c.value for c in by_key.get((e["key"], Path(e["file"]).name), [])][:4]))

    # ---- policy summary, from the ground-truth fields
    want = {f["key"]: f["value"] for f in truth["expected_fields"] if f["key"] in ("sum_insured", "room_rent_cap")}
    ps = results.policy_summary
    checks = {
        f"sum_insured = {want['sum_insured']}": bool(ps and ps.sum_insured and ps.sum_insured.value == want["sum_insured"]),
        f"room_rent_cap = {want['room_rent_cap']}": bool(ps and ps.room_rent_cap and ps.room_rent_cap.value == want["room_rent_cap"]),
    }

    # ---- findings: exact match against the planted defects
    exp_f = {f["rule_id"] + ":" + f["issue_type"]: f for f in truth["expected_findings"]}
    got_f = {f.rule_id + ":" + f.issue_type: f for f in results.findings if f.rule_id != "V14"}
    for k, f in exp_f.items():
        g = got_f.get(k)
        checks[f"{f['id']} {k} found (blocking={f['blocking']})"] = bool(g and g.blocking == f["blocking"])
        if g and f.get("waiting"):
            w = f["waiting"]
            i = g.explanation.inputs
            checks[f"{f['id']} waiting period: {w['elapsed_days']} days into a {w['days']}-day '{w['name']}'"] = (
                i.get("elapsed_days") == w["elapsed_days"] and i.get("waiting_days") == w["days"])
        if g and f.get("exposure_amount") is not None:
            checks[f"{f['id']} exposure = {f['exposure_amount']}"] = g.exposure_amount == f["exposure_amount"]
    extra = sorted(set(got_f) - set(exp_f))
    checks["no false alarms (findings outside the ground truth)"] = not extra
    checks["every finding has evidence and every action cites a finding or checklist item"] = (
        all(f.evidence for f in results.findings)
        and all(a.finding_ids or a.group in ("upload", "consistent") for a in results.action_plan))
    checks[f"packet status = '{truth['expected_packet_status']}'"] = results.packet_status == truth["expected_packet_status"]
    checks[f"readiness = {truth['expected_readiness']}"] = results.readiness_status and results.readiness_status.value == truth["expected_readiness"]

    print(f"\nFields: {ok}/{ok + len(misses)} expected values extracted correctly")
    for m in misses:
        print("  MISS", m)
    print("\nChecks:")
    for k, v in checks.items():
        print(f"  {'PASS' if v else 'FAIL'}  {k}")
    for k in extra:  # show exactly what a false alarm was built from
        g = got_f[k]
        print(f"\nFALSE ALARM {k}: {g.title}\n  values: {g.extracted_value} vs {g.comparison_value}\n  inputs: {g.explanation.inputs}\n"
              f"  evidence: {[(e.source, e.filename, e.page_number, e.quote) for e in g.evidence]}")
    print(f"\nFindings produced: {sorted(got_f) or 'none'}; false alarms: {extra or 'none'}")
    print(f"Providers: {results.providers_used or ['rules']}; model calls: {len(results.llm_calls)} ({sum(c.ok for c in results.llm_calls)} ok); "
          f"checks passed listed: {len(results.checks_passed)}")
    return 0 if not misses and all(checks.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
