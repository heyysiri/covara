"""python -m claimgen a|b|c [--out DIR]   (run from sample_documents/tools; needs the backend venv)"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import documents as d
from .scenarios import SCENARIOS
from .truth import Paths, build_expected, verify, write_zip


def build(key: str, root: Path, write_json: bool = True) -> tuple[dict, list[str]]:
    s = SCENARIOS[key]()
    s.check()
    p = Paths.for_(s)
    d.make_policy(s, root / p.policy)
    d.make_final_bill(s, root / p.final)
    if s.duplicate_bill:
        d.make_final_bill(s, root / p.copy, copy=True)
    d.make_itemised_bill(s, root / p.itemised)
    d.make_discharge_summary(s, root / p.discharge)
    d.make_receipt(s, root / p.receipt)
    if s.rx_referenced:
        d.make_prescription(s, root / p.rx)
    exp = build_expected(s, p)
    errors = verify(root, exp)
    if write_json:
        out = root / "expected_results" / f"claim_{key}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(exp, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        write_zip(root, exp, root / f"claim_{key}_upload.zip")
    return exp, errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("claim", choices=sorted(SCENARIOS))
    ap.add_argument("--out", type=Path, default=Path(__file__).resolve().parents[2], help="sample_documents folder")
    args = ap.parse_args()
    exp, errors = build(args.claim, args.out)
    print(f"claim {args.claim.upper()}: {len(exp['upload_set'])} upload files, {len(exp['held_back_for_live_fix'])} held back, "
          f"{len(exp['expected_fields'])} fields, {len(exp['expected_findings'])} planted findings, packet '{exp['expected_packet_status']}'")
    if errors:
        print("VERIFICATION FAILED:")
        for e in errors:
            print(" -", e)
        return 1
    print("every quote verified against the generated PDFs: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
