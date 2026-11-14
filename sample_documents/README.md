# Sample documents (SYNTHETIC)

Everything here is **fictional**: no real person, hospital, insurer or policy. Each PDF carries a "SYNTHETIC DEMO DOCUMENT" header.

## Claim B - the hero demo claim

Claim form input: reimbursement, **claimed amount 95,000**, patient Ravi Kumar Sharma.

**Upload these 6 files**

| File | Doc type |
|---|---|
| `policy/claim_b_policy.pdf` (6 pages; room-rent clause 4.1 on page 4) | policy |
| `medical/claim_b_final_bill.pdf` | final bill |
| `medical/claim_b_final_bill_copy.pdf` (same invoice number, different file) | final bill (duplicate) |
| `medical/claim_b_itemised_bill.pdf` | itemised bill |
| `medical/claim_b_discharge_summary.pdf` (refers to prescription RX-7781) | discharge summary |
| `medical/claim_b_payment_receipt.pdf` (name written "Ravi K Sharma") | payment receipt |

**Held back for the live fix:** `medical/_held_back/claim_b_prescription_RX-7781.pdf` - upload it during the demo.

**Planted findings** (ground truth in `expected_results/claim_b.json`)

| ID | Rule | What | Blocking |
|---|---|---|---|
| B-F1 | V4 | Bill total 85,000 vs claimed 95,000 | yes |
| B-F2 | V1 | Same invoice number in two files | yes |
| B-F3 | V7 | Discharge summary refers to prescription RX-7781, not uploaded | yes |
| B-F4 | V10 | Room rent 7,500/day vs cap 5,000/day (clause 4.1); estimated exposure ~23,867 | no |
| B-F5 | V2 | Receipt says "Ravi K Sharma" | no |

Expected readiness: `needs_attention`; packet: "INCOMPLETE - 3 blocking items". After the demo fix sequence (correct the amount, remove the duplicate, upload the prescription, re-check) the packet should read "Prepared for submission" with B-F4 and B-F5 still open for review.

## Files

- `expected_results/claim_b.json` - ground truth: fields, findings, checks passed, checklist, fix sequence. Every quote was verified to appear on the stated page.
- `expected_results/claim_b.results.fixture.json` - an `AnalysisResults`-shaped mock (see section 4 of `docs/DIVISION_OF_WORK.md`) for the frontend and pipeline stubs.
- `tools/generate_claim_b.py` - regenerates everything and re-verifies it. Output is deterministic (identical file hashes on every run).

```bash
backend/.venv/bin/python sample_documents/tools/generate_claim_b.py
```

## Still to make

- Claim A (clean claim, must produce no false alarms).
- Claim C (waiting-period conflict, plus one Hindi/Telugu document and one handwritten prescription for Sarvam).
