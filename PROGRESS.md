# Covara - Progress Log

Shared status board for **Person 1** and **Person 2**. Read this before you start work; update it with every change.
Plan lives in [docs/DIVISION_OF_WORK.md](docs/DIVISION_OF_WORK.md) (modules, phases, handoffs H1-H9, contract). Original plan: [PLAN.md](PLAN.md).

**Last updated:** 2026-11-14 by Person 1 (merged Person 2's `20b2aa8`/`e6b419c`; Person 1 work is on branch `person1-pipeline`)

## How to use this file

- **Every change gets an entry** in the Change log (newest first): date, who, what, commit hash if there is one.
- Update the **Task board** and **Handoffs** tables in the same edit.
- Anything that affects the other person (shared files, schema changes, new endpoints, decisions) goes under **Open items / heads-up** until they acknowledge it.
- Commit `PROGRESS.md` together with the change it describes, so `git pull` always gives the full picture.
- Status values: `todo` · `in progress` · `done` · `blocked (reason)`.

## Current phase

**Person 1 modules are built (Phases 2-6 for P1's scope).** Waiting on Person 2's verification engine (M3) to produce findings; until then the pipeline returns extraction, policy, checklist and checklist-based actions, and **no findings**. Next joint milestone: G3 (document evidence -> policy clause -> issue -> action on claim B).

## Task board

### Phase 0-1 (environment + skeleton)
| Item | Status | Notes |
|---|---|---|
| Environment checked, monorepo created | done | Python 3.12, Node 20+, Next.js 16 |
| FastAPI skeleton, Next.js landing + upload skeleton, README | done | |

### Phase 2 - Foundation
| Task | Owner | Status | Notes |
|---|---|---|---|
| Contract freeze (shared schemas, TS mirror) | P1 draft | **done (draft) - P2 please review** | `backend/app/schemas/results.py` + `frontend/src/types/results.ts`. Includes P2's asks: `EvidenceRef.source`, `checks_passed`. D1-D10 still need an explicit OK from P2 (see Decisions). |
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
| W4 re-check loop | **partly done** | Re-check, field edits, document delete all work. The finding disappearing needs P2's engine. |
| W8 review gate as a LangGraph `interrupt()` | **not done** | Implemented as badge + confirm/edit + Re-check instead (no pause/resume). |
| W5 Sarvam Vision (Indic/handwritten) | **not done** | Key present in env but no integration yet. |

### Phase 3+ - Person 2 (from the board, unchanged by P1)
| Task | Owner | Status |
|---|---|---|
| Verification rules V1-V5, V7, V14 (+ V10, V11) with unit tests | P2 | todo (see how to plug in below) |
| Workspace shell + tabs (Findings, Evidence viewer, Packet) | P2 | todo (`AnalysisView` accepts `extraTabs`) |
| Report + claim packet + `claim.json` | P2 | todo (`GET /claims/{id}/report` still returns 501) |

## Measured results (claim B, ground truth by P2)

Run: `cd backend && .venv/bin/python -m tests.eval_claim_b` (add `--rules` for offline).

| Path | Fields correct | Policy checks | Checklist checks | Time |
|---|---|---|---|---|
| Claude (via Claude Code session) | **30 / 30** | 4 / 4 | 3 / 3 | ~50 s for 6 documents |
| Rules only (no AI) | 13 / 30 | 3 / 4 | 3 / 3 | ~1 s |

Not measured: claims A and C (not made yet), handwritten/Indic documents, scanned images, latency under the real Claude API. The first Claude run missed 2 of 4 policy checks because the policy schedule is a table (label and value on separate lines); that is fixed and covered by a regression test.

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
| H9 | Findings with evidence | P2 -> P1 | **waiting on P2** |

## Open items / heads-up

**For Person 2 (raised 2026-11-14 by Person 1) - please read:**
1. **Plug in your engine at one place:** create `backend/app/modules/verification/service.py` with `def run_verification(ctx: VerificationContext)`. The pipeline imports it automatically. Return a `VerificationResult(findings=[...], checks_passed=[...])` (from `app/modules/pipeline/context.py`); a plain `list[Finding]` or a `(findings, checks_passed)` tuple also works. `Finding` rejects empty `evidence` (I1).
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

**Decisions still proposed, not confirmed** (see section 4 of the plan): D1 async analyze + polling (implemented), D2 `claimed_amount` on the claim form (implemented), D3 readiness rule (implemented in `plan.readiness`), D4 required-documents checklist (implemented), D5 packet wording/watermark (status string only, no PDF yet), D6 model names/keys (changed: Claude via session or `ANTHROPIC_API_KEY`), D7 feature-folder layout (new code only), D8 confidence threshold 0.75 (implemented as a badge, not a pause), D9 cache key (implemented), D10 tiers.

## Change log (newest first)

| Date | Who | Change | Commit |
|---|---|---|---|
| 2026-11-14 | P1 | Contract reconciliation with P2's asks: `EvidenceRef.source` (document / claim_form), `checks_passed`, `checklist_summary`, `documents_failed`, `VerificationResult`, `ctx.claim_form_ref`; `DELETE /claims/{id}/documents/{doc_id}` + Remove button; Claim B accuracy eval (`tests/eval_claim_b.py`): Claude 30/30, rules 13/30; fixed table-layout policy parsing; 27 backend tests pass | this branch |
| 2026-11-14 | P1 | Claude provider: API key path and no-key path through the logged-in Claude Code session (`claude -p`), refusal handling, cache, schema validation | this branch |
| 2026-11-14 | P1 | Built M1, M2, M4, M6, M8 (backend + frontend), consent/delete, cache + demo mode, README endpoints; 23 tests | `16e51e5` |
| 2026-11-14 | P2 | Created this progress log | `e6b419c` |
| 2026-11-14 | P2 | Added synthetic claim B (7 PDFs), ground truth with verified quotes, AnalysisResults fixture, generator `sample_documents/tools/generate_claim_b.py` | `20b2aa8` |
| 2026-11-14 | P2 | Rewrote `docs/DIVISION_OF_WORK.md` | `290c25a` |
| 2026-11-13 | both | Phase 0-1: environment, monorepo, FastAPI + Next.js skeleton, upload API/UI, 10 backend tests | `9bb20d0`, `88e3c0b`, `483f375` |
