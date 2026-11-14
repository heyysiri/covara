# Covara - Progress Log

Shared status board for **Person 1** and **Person 2**. Read this before you start work; update it with every change.
Plan lives in [docs/DIVISION_OF_WORK.md](docs/DIVISION_OF_WORK.md) (modules, phases, handoffs H1-H9, contract). Original plan: [PLAN.md](PLAN.md).

**Last updated:** 2026-11-14 by Person 1 (verification engine now wired into the pipeline; all merged to `main`)

## How to use this file

- **Every change gets an entry** in the Change log (newest first): date, who, what, commit hash if there is one.
- Update the **Task board** and **Handoffs** tables in the same edit.
- Anything that affects the other person (shared files, schema changes, new endpoints, decisions) goes under **Open items / heads-up** until they acknowledge it.
- Commit `PROGRESS.md` together with the change it describes, so `git pull` always gives the full picture.
- Status values: `todo` · `in progress` · `done` · `blocked (reason)`.

## Current phase

**Person 1 modules are built and Person 2's verification engine is wired in.** The full claim B demo path works end to end with Claude: upload -> analyse -> 3 blocking findings + 1 to review -> fix sequence -> Re-check -> "Prepared for submission" (measured below). Still missing for the demo: V10 (room-rent exposure) and V11 (waiting period) rules, the Findings/Evidence/Packet tabs, and the report PDF (all Person 2). Next joint milestone: G3 (evidence viewer + policy clause on a finding).

## Task board

### Phase 0-1 (environment + skeleton)
| Item | Status | Notes |
|---|---|---|
| Environment checked, monorepo created | done | Python 3.12, Node 20+, Next.js 16 |
| FastAPI skeleton, Next.js landing + upload skeleton, README | done | |

### Phase 2 - Foundation
| Task | Owner | Status | Notes |
|---|---|---|---|
| Contract freeze (shared schemas, TS mirror) | both | **reconciled by adapter** | Two model sets remain (P1 `schemas/results.py` = API/UI; P2 `schemas/contract.py` = engine input/output). They are field-compatible; `backend/app/modules/pipeline/verify_adapter.py` converts between them and shapes values for the engine. `EvidenceRef.source` now has `document`, `claim_form` and `checklist` on both sides. Merging into one file is optional cleanup. D1-D10 still need an explicit OK. |
| Feature-folder layout | P1 | **partly done** | All new code is in `backend/app/modules/*`, `backend/app/core`, `frontend/src/features/*`. Phase 1 files (`api/routes/claims.py`, `schemas/claim.py`, `services/claim_store.py`, `DocumentUpload.tsx`) were **not moved**, only extended. |
| `claimed_amount` (+ `patient_name`, consent) on claim form/API | P1 | **done** | `POST/PATCH /claims` |
| `langgraph` in `requirements.txt` | P1 | **done** | also `anthropic` |
| Verify AI provider with a real call | P1 | **done for Claude** | Via the user's Claude Code session (no API key). Gemini and Groq paths exist but are **untested against the real APIs** (no keys). |
| Demo claim B documents + ground truth + fixture | P2 | done | `20b2aa8` |

### Person 1 modules
| Module | Status | Notes |
|---|---|---|
| M1 Intake & vault | **done** | claim form values, consent gate, checklist (D4) incl. referenced-but-missing, duplicate-file warning (same sha256), original-file endpoint, **delete one document**, **delete my data**. UI: documents list with Remove, live checklist. |
| M2 Extraction | **done** | ingest (page text, bbox), classify, extract, normalise. Every field has page + quote located in the page text + confidence. Review: low-confidence critical fields (<0.75) show a badge; user can confirm/correct inline and **Re-check**. |
| M4 Policy intelligence | **done** | clause chunking by numbered heading with page; `PolicySummary` (sum insured, room-rent cap as INR/day, co-pay, pre/post days, waiting periods, exclusions); `policy_match` links findings to clauses and **rejects any quote not found verbatim in the clause**. |
| M6 Action plan | **done** | owned (you/hospital/doctor/insurer), blocking-first, `finding_ids` required (I3), ready-to-send messages with real values, tick-done survives Re-check. Shows `checks_passed` as "Appears consistent". |
| M8 Pipeline & platform | **done** | LangGraph graph (ingest -> classify -> extract -> normalize -> policy -> verify -> policy_match -> explain_plan -> finalize), background run, polling, cache by file hash (W1), `llm_calls` log, demo mode, one bad document never fails the run. |
| W7 consent + delete | done | |
| W1 safety net (cache, demo mode) | done | `DEMO_MODE=true` replays cache only |
| W4 re-check loop | **done** | Edit claimed amount, remove the duplicate, upload the prescription, Re-check: findings clear and the packet status flips. Measured on claim B (below). Backend only; the packet PDF/watermark is P2's. |
| W8 review gate as a LangGraph `interrupt()` | **not done** | Implemented as badge + confirm/edit + Re-check instead (no pause/resume). |
| W5 Sarvam Vision (Indic/handwritten) | **not done** | Key present in env but no integration yet. |

### Phase 3+ - Person 2 (from the board, unchanged by P1)
| Task | Owner | Status |
|---|---|---|
| Verification rules V1-V5, V7, V14 with unit tests | P2 | **done and wired into the pipeline** (`8dfba15`; adapter by P1) | Runs in the `verify` node on every analysis. |
| Verification rules V10 (room-rent exposure), V11 (waiting period) | P2 | todo | `PolicySummary` is now available from P1 (`ctx.policy_summary`). |
| Upload accepts a folder or a .zip | P2 (requested by user) | **done** (`e28637e`) | Client-side unzip; merged with P1's claim form/consent/documents list. |
| Workspace shell + tabs (Findings, Evidence viewer, Packet) | P2 | todo (`AnalysisView` accepts `extraTabs`) |
| Report + claim packet + `claim.json` | P2 | todo (`GET /claims/{id}/report` still returns 501) |

## Measured results (claim B, ground truth by P2)

Run: `cd backend && .venv/bin/python -m tests.eval_claim_b` (add `--rules` for offline, no AI). It uploads the 6 claim B files, analyses, applies the demo fix sequence (correct amount, remove duplicate, upload the held-back prescription) and re-checks.

| Check | Claude (via Claude Code session) | Rules only (no AI) |
|---|---|---|
| Expected fields extracted correctly | **40 / 40** | 22 / 40 |
| Policy summary + clause checks | 4 / 4 | 3 / 4 (waiting periods missed) |
| Checklist checks | 3 / 3 | 3 / 3 |
| Findings the engine can produce (B-F1 V4, B-F2 V1, B-F3 V7, B-F5 V2) found with correct blocking flag | **4 / 4** | 3 / 4 (name variant missed) |
| Unexpected extra findings | none | 1 false alarm (V4 line items) |
| First analysis packet status | INCOMPLETE - 3 blocking items | INCOMPLETE - 4 blocking items |
| After fix sequence + Re-check | **Prepared for submission** (only the name variant left open) | still INCOMPLETE (false V4 alarm) |
| Time | ~1 min first analysis, ~1 min for the re-check including one new document | ~1 s |

Not covered: B-F4 (V10 room-rent exposure, rule not written yet), V11, claims A and C (not made yet), handwritten/Indic documents, scanned images. The no-AI path is a fallback only and is not demo quality. Model: Claude through the Claude Code session; speed will differ on the real API.

## Handoffs

| # | Handoff | From -> To | Status |
|---|---|---|---|
| H1 | Contract + decisions D1-D10 | both | **P1 draft done, P2 review pending** |
| H2 | Minimum demo documents (claim B) | P2 -> P1 | done, used by the eval |
| H3 | Fixture results JSON | P2 -> P1 | done; real API shape now matches it except `checklist` (see below) |
| H4 | Results API + polling hook | P1 -> P2 | **done** (`GET /claims/{id}/results`, `useAnalysis`) |
| H5 | `GET /documents/{id}/file` | P1 -> P2 | **done** (`GET /claims/{id}/documents/{doc_id}/file`, `#page=N` opens the page) |
| H6 | First correct `ExtractedField`s | P1 -> P2 | **done** (30/30 on claim B with Claude) |
| H7 | Real `PolicyClause`s + `PolicySummary` | P1 -> P2 | **done** |
| H8 | `Action[]` | P1 -> P2 | **done**, but only checklist actions until P2's findings arrive |
| H9 | Findings with evidence | P2 -> P1 | **done** (`8dfba15`, wired by P1): V1-V5, V7, V14 reach the plan and results |

## Open items / heads-up

**For Person 2 (raised 2026-11-14 by Person 1) - please read:**
1. **Your engine is already plugged in** through `pipeline/verify_adapter.py` (no action needed). Optional override: a `verification/service.py` with `run_verification(ctx: VerificationContext)` takes precedence over the adapter. Return a `VerificationResult(findings=[...], checks_passed=[...])` (from `app/modules/pipeline/context.py`); a plain `list[Finding]` or a `(findings, checks_passed)` tuple also works. `Finding` rejects empty `evidence` (I1).
2. **`ctx` gives you:** `claim` (claim form: `claimed_amount`, `patient_name`, `claim_type`), `documents`, `fields` (normalised), `policy_summary`, `clauses`, `checklist`, `page_texts`. Use `ctx.fields_for("bill_total")` and `ctx.claim_form_ref("claimed_amount")` to build the claim-form `EvidenceRef`.
3. **Normalisation you can rely on:** dates are ISO `YYYY-MM-DD` strings; amounts are floats in INR; names are title-cased without Mr/Mrs/Dr; `line_item` has `value` = amount and `raw_text` = description (**qty and rate are not extracted yet**, so V4 line-item arithmetic can check amounts vs the total only); `referenced_document.value` is a doc type (`prescription`, `diagnostic_report`); `waiting_period.value` is days (months = 30.4 days, rounded). Unknown stays `None`.
4. **Two patient-name sources:** `patient_name` appears in the bill, discharge summary and receipt (one field per document). For V2, compare across `ctx.fields_for("patient_name")` and `policyholder_name`.
5. **Policy values for V10/V11:** `ctx.policy_summary.room_rent_cap.value` is INR per day; `room_rent_cap_percent` is set when stated as a % of sum insured; `waiting_periods[].days`. `policy_start`/`policy_end` are extracted as normal fields from the policy.
6. **Clause linking is done for you** after your findings return: each finding is linked to clauses by `rule_id` (V10 -> room-rent clause) with a verified quote, unless you fill `clause_links` yourself. Actions are generated from your findings (`RULE_ROUTING` in `app/modules/actions/plan.py`); tell me if you want different owners or wording per rule.
7. **Shape differences from your fixture (your call which side moves):** the API `checklist` is a list of items with reasons; the fixture's `{required_present, required_missing, referenced_but_missing}` is available as `checklist_summary`. Fixture `documents[]` entries have no `pages`/`category`/`has_text_layer`/`extraction_method`; the API adds them. `policy_summary` values carry a human `text` field.
8. **Endpoints you asked for exist:** `PATCH /claims/{id}` (edit claimed amount) and `DELETE /claims/{id}/documents/{doc_id}`. The UI has a Remove button per document and a Re-check button.
9. **Packet status:** today `packet_status` counts blocking findings plus missing blocking uploads; replace it with your own once the packet generator exists.
10. **Frontend:** the panels are in `frontend/src/features/*`; `AnalysisView` takes `extraTabs` for Findings / Evidence / Packet. The `EvidenceLink` component opens the original PDF at the cited page.

**How the AI provider works (no API key needed):** the backend uses Claude through the logged-in Claude Code session (`claude -p`), auto-detected; set `ANTHROPIC_API_KEY` to use the Claude API instead. Calls take 10-50 s per document, so analyses take ~1 min; run once to warm the cache (`backend/.cache/`, keyed by file hash) before a demo, and use `DEMO_MODE=true` to replay without calling any model. This path is for local development and demos.

**For Person 1, from Person 2** (raised 2026-11-14; numbered P2-n; status in item 11):
P2-6. **Review `backend/app/schemas/contract.py`.** It is the plan's section 4 as Pydantic models, with I1 (a `Finding` needs evidence) and I3 (an `Action` needs `finding_ids`) enforced as validation. Changes vs the plan: `EvidenceRef.source` is `document | claim_form | checklist`; `checks_passed` is a separate list; `ExtractedField.confidence` is a float 0-1. If you already wrote different models, reconcile against this one - the fixture and 48 tests validate against it. The old `schemas/results.py` is untouched.
P2-7. **Engine signature differs slightly from the plan:** `run_verification(fields, documents, claim)` returns `VerificationResult(findings, checks_passed, rules_run)`, not just `list[Finding]`, because the "appears consistent" list needs the passed checks. Module: `backend/app/modules/verification/`. The pipeline's `verify` node should call it.
P2-8. **What the engine expects from `normalize` (M2):** `patient_name`, `policy_number`, `member_id`, `bill_number`, `hospital_name` as strings; dates as ISO strings (`2026-08-12`, other common formats also parse); amounts numeric (`"Rs. 85,000"` also parses); each `line_item` value a dict with an `amount`; `referenced_document` as free text such as "prescription no. RX-7781". Each field needs `evidence.document_id` matching a `DocumentInfo.id` with the right `doc_type`.
P2-9. **Fixture regenerated:** the copy bill, bill and discharge summary now also carry policy/member IDs and invoice numbers (32 -> 42 fields) so cross-document rules have data. Run `git pull` again when committed. Fixture shape is unchanged.

P2-10. **Heads-up, frontend upload changed (M1 is yours, so pull before editing it):** `frontend/src/components/DocumentUpload.tsx` now takes files, a folder (button or drag-and-drop) or a `.zip`. New file `frontend/src/lib/ingest.ts` does the work in the browser (`fflate` added to `package.json`); hidden/system files (`.DS_Store`, `__MACOSX`), non-PDF/PNG/JPG files and nested zips are skipped with a notice, zips are capped (200 entries, 200 MB total, 20 MB per file). The backend API is **unchanged**: each document is still uploaded through `POST /claims/{id}/documents`. Category guessing now falls back to the folder path. New demo file `sample_documents/claim_b_upload.zip` (the 6 upload files, without the held-back prescription).

11. **Status (Person 1):** P2-6 (reconcile contracts), P2-7 and P2-8 (engine signature and expected inputs) are **done via the adapter** (`app/modules/pipeline/verify_adapter.py`): it converts models, passes `line_item` values from the itemised bill only (the engine sums every line item it sees, so passing both bills would double count), and passes `referenced_document` as written ("prescription no. RX-7781"). `EvidenceRef` accepts `source=checklist`. P2-9 and P2-10 acknowledged: fixture pulled, upload merged. **Still yours (P2):** V10, V11, the Findings/Evidence/Packet tabs, the report/packet PDF. To add a rule, append it to `RULES` in `verification/rules.py`; the pipeline needs no change.

**Decisions still proposed, not confirmed** (see section 4 of the plan): D1 async analyze + polling (implemented), D2 `claimed_amount` on the claim form (implemented), D3 readiness rule (implemented in `plan.readiness`), D4 required-documents checklist (implemented), D5 packet wording/watermark (status string only, no PDF yet), D6 model names/keys (changed: Claude via session or `ANTHROPIC_API_KEY`), D7 feature-folder layout (new code only), D8 confidence threshold 0.75 (implemented as a badge, not a pause), D9 cache key (implemented), D10 tiers.

## Change log (newest first)

| Date | Who | Change | Commit |
|---|---|---|---|
| 2026-11-14 | P1 | **Wired the verification engine into the pipeline** (`verify_adapter.py`): V1-V5, V7, V14 findings now reach clause linking, the action plan and the packet status; `EvidenceRef.source=checklist`; packet blocking count no longer double-counts a V7 finding and its upload action; `referenced_document` keeps the wording as written; `member_id` extracted from discharge summaries. Claim B eval extended with findings and the demo fix sequence: Claude 40/40 fields, 4/4 findings, packet goes INCOMPLETE (3 blocking) -> Prepared for submission; rules-only 22/40. 76 backend tests pass | this commit |
| 2026-11-14 | P1 | Merged `origin/main` (verification engine, folder/zip upload) into `person1-pipeline`; resolved conflicts in `DocumentUpload.tsx` (kept both sides) and this file | merge commit |
| 2026-11-14 | P1 | Contract reconciliation with P2's asks: `EvidenceRef.source` (document / claim_form), `checks_passed`, `checklist_summary`, `documents_failed`, `VerificationResult`, `ctx.claim_form_ref`; `DELETE /claims/{id}/documents/{doc_id}` + Remove button; Claim B accuracy eval (`tests/eval_claim_b.py`): Claude 30/30, rules 13/30; fixed table-layout policy parsing; 27 backend tests pass | this branch |
| 2026-11-14 | P1 | Claude provider: API key path and no-key path through the logged-in Claude Code session (`claude -p`), refusal handling, cache, schema validation | this branch |
| 2026-11-14 | P1 | Built M1, M2, M4, M6, M8 (backend + frontend), consent/delete, cache + demo mode, README endpoints; 23 tests | `16e51e5` |
| 2026-11-14 | P2 | **Upload takes a folder or a .zip:** `frontend/src/lib/ingest.ts` (in-browser unzip with `fflate`, folder picker + folder drag-and-drop, junk/unsupported/nested-zip skipping, size and entry caps, corrupt-zip handling), `DocumentUpload.tsx` updated (Choose folder / Choose .zip buttons, path shown per file, notice banner), `sample_documents/claim_b_upload.zip` + generator support. Logic tested in Node against a messy zip (6 real docs kept, 6 junk entries skipped, corrupt zip reported); lint + tsc clean. Not yet clicked through in a browser. Backend unchanged. | `e28637e` |
| 2026-11-14 | P2 | **Verification engine** `backend/app/modules/verification/` (rules V1, V2, V3, V4, V5, V7, V14; deterministic, evidence on every finding, stored inputs); draft contract `backend/app/schemas/contract.py`; `backend/tests/test_verification.py` (48 tests incl. claim B end-to-end vs ground truth, quote-on-PDF-page check, and the demo fix sequence clearing all 3 blocking items). Fixed 2 bugs found by tests (amount parsing of "Rs. 85,000", name-variant threshold). Regenerated claim B fixture with more cross-document fields. **58 backend tests pass.** | `8dfba15` |
| 2026-11-14 | P2 | Created this progress log | `e6b419c` |
| 2026-11-14 | P2 | Added synthetic claim B (7 PDFs), ground truth with verified quotes, AnalysisResults fixture, deterministic generator `sample_documents/tools/generate_claim_b.py`, `sample_documents/README.md` | `20b2aa8` |
| 2026-11-14 | P2 | Rewrote `docs/DIVISION_OF_WORK.md`: feature-module split, architecture diagrams, USP guard rails, Build Guide integration (Wow set, V1-V14 rules, model routing), phases + handoffs | `290c25a` |
| 2026-11-13 | both | Phase 0-1: environment checked, monorepo, FastAPI + Next.js skeleton, health check, upload API/UI, 10 backend tests, README, `.env.example` files | `9bb20d0`, `88e3c0b`, `483f375` |
