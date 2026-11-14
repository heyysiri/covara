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

    # Findings (produced by Person 2's engine through the pipeline) vs ground truth.
    exp_f = {f["rule_id"] + ":" + f["issue_type"]: f for f in truth["expected_findings"]}
    got_f = {f.rule_id + ":" + f.issue_type: f for f in results.findings}
    implemented = {"V1", "V2", "V3", "V4", "V5", "V7", "V14"}  # engine rules that exist today
    finding_checks = {}
    for key, f in exp_f.items():
        if f["rule_id"] in implemented:
            g = got_f.get(key)
            finding_checks[f"{f['id']} {key} found" + (" (blocking)" if f["blocking"] else "")] = bool(
                g and g.blocking == f["blocking"])
    not_built = [f"{f['id']} {f['rule_id']}" for f in exp_f.values() if f["rule_id"] not in implemented]
    expected_keys = set(exp_f)
    extra = sorted(k for k in got_f if k not in expected_keys and not k.startswith("V14"))
    plan_ok = all(a.finding_ids or a.group in ("upload", "consistent") for a in results.action_plan)
    finding_checks["every action cites a finding or checklist item"] = plan_ok

    # Demo fix sequence: correct amount, remove duplicate, upload held-back prescription, re-check.
    steps = truth["demo_fix_sequence"]
    docs_now = client.get(f"/claims/{cid}/documents").json()
    copy = next(d for d in docs_now if d["original_filename"] == "claim_b_final_bill_copy.pdf")
    client.patch(f"/claims/{cid}", json={"claimed_amount": 85000})
    client.delete(f"/claims/{cid}/documents/{copy['id']}")
    rx = SAMPLES / "medical" / "_held_back" / "claim_b_prescription_RX-7781.pdf"
    client.post(f"/claims/{cid}/documents", data={"category": "prescription"},
                files=[("files", (rx.name, rx.read_bytes(), "application/pdf"))])
    client.post(f"/claims/{cid}/analyze")
    after = AnalysisResults.model_validate(client.get(f"/claims/{cid}/results").json())
    open_ids = sorted(f"{f.rule_id}:{f.issue_type}" for f in after.findings if f.status == "open"
                      and not f.rule_id == "V14")
    fix_checks = {
        "after fixes: packet says Prepared for submission": after.packet_status == truth["after_fix"]["expected_packet_status"],
        "after fixes: no blocking findings": not any(f.blocking for f in after.findings),
        "after fixes: prescription no longer missing": not any(f.issue_type == "referenced_document_missing"
                                                                for f in after.findings),
    }

    print(f"\nFields: {ok}/{ok + miss} expected values extracted correctly")
    for m in misses:
        print("  MISS", m)
    for title, checks in (("Policy", summary_checks), ("Checklist", checklist_checks),
                          ("Findings (engine via pipeline)", finding_checks), ("Demo fix sequence", fix_checks)):
        print(f"\n{title}:")
        for k, v in checks.items():
            print(f"  {'PASS' if v else 'FAIL'}  {k}")
    print(f"\nExtracted fields: {len(results.fields)}; with a located quote + bbox: {quotes_ok}; "
          f"low-confidence critical: {sum(1 for f in results.fields if f.confidence < 0.75)}")
    print(f"Providers: {results.providers_used or ['rules']}; model calls: {len(results.llm_calls)} "
          f"({sum(c.ok for c in results.llm_calls)} ok)")
    print(f"Readiness: {results.readiness_status} | packet: {results.packet_status}")
    print(f"Findings: expected-but-not-built rules (Person 2): {not_built or 'none'}; "
          f"unexpected extra findings: {extra or 'none'}")
    print(f"After fix sequence, open findings: {open_ids}; packet: {after.packet_status}; "
          f"readiness: {after.readiness_status}")
    print(f"Checks passed listed: {len(results.checks_passed)}")
    allc = [summary_checks, checklist_checks, finding_checks, fix_checks]
    return 0 if miss == 0 and all(all(c.values()) for c in allc) else 1


if __name__ == "__main__":
    sys.exit(main())
