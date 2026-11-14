# Covara - Progress Log

Shared status board for **Person 1** and **Person 2**. Read this before you start work; update it with every change.
Plan lives in [docs/DIVISION_OF_WORK.md](docs/DIVISION_OF_WORK.md) (modules, phases, handoffs H1-H9, contract). Original plan: [PLAN.md](PLAN.md).

**Last updated:** 2026-11-14 by Person 2 (verification engine + draft contract, folder/zip upload)

## How to use this file

- **Every change gets an entry** in the Change log (newest first): date, who, what, commit hash if there is one.
- Update the **Task board** and **Handoffs** tables in the same edit.
- Anything that affects the other person (shared files, schema changes, new endpoints, decisions) goes under **Open items / heads-up** until they acknowledge it.
- Commit `PROGRESS.md` together with the change it describes, so `git pull` always gives the full picture.
- Status values: `todo` · `in progress` · `done` · `blocked (reason)`.

## Current phase

**Phase 2 - Foundation (G0).** Exit check: schemas committed on both sides, existing backend tests pass after the folder migration, demo files + fixture exist, a Gemini and a Groq call each respond.

## Task board

### Phase 0-1 (environment + skeleton)
| Item | Status | Notes |
|---|---|---|
| Environment checked, monorepo created | done | Python 3.12 via uv, Node 25, Next.js 16 |
| FastAPI skeleton: `/health`, claims, document upload, 501 stubs for analyze/results/report | done | 10 backend tests pass |
| Next.js landing + upload UI skeleton, API-online badge | done | lint + build pass |
| README with setup/run commands | done | |

### Phase 2 - Foundation
| Task | Owner | Status | Notes |
|---|---|---|---|
| Contract freeze (shared schemas, TS mirror, decisions D1-D10) | both | **in progress** | P2 drafted `backend/app/schemas/contract.py` (`8dfba15`, new file, nothing existing modified). Needs P1 review/adoption. TS mirror not started. Decisions D1-D10 still unconfirmed. |
| Move Phase 1 code into feature folders | P1 (proposed) | todo | Nobody has started; do not move files until agreed |
| Add `claimed_amount` to claim form/API | P1 | todo | |
| Add `langgraph` to `requirements.txt` | P1 | todo | |
| Verify Gemini + Groq keys (one real call each) | P1 | todo | Needs keys + `GEMINI_MODEL` / `GROQ_MODEL` in `backend/.env` |
| Demo claim B documents (6 uploads + 1 held-back prescription) | P2 | **done** | commit `20b2aa8` |
| `expected_results/claim_b.json` (ground truth, quotes verified) | P2 | **done** | commit `20b2aa8` |
| Fixture `claim_b.results.fixture.json` (AnalysisResults-shaped mock) | P2 | **done** | commit `20b2aa8` |

### Phase 3 - Walking skeleton (not started)
| Task | Owner | Status |
|---|---|---|
| Pipeline stubs (LangGraph), `POST /analyze` 202, `GET /results` with progress | P1 | todo |
| LLM/OCR adapters, response cache by file hash, `llm_calls` log (W1) | P1 | todo |
| Checklist endpoint + UI, file endpoint, duplicate warning, consent + delete (W7) | P1 | todo |
| Workspace shell + all tabs rendering the fixture | P2 | todo |
| Verification rules V1-V5, V7, V14 with unit tests on fixtures | P2 | **done** (`8dfba15`) |
| Verification rules V10 (room-rent exposure), V11 (waiting period) | P2 | todo (Phase 5, needs `PolicySummary` from P1's M4) |
| Upload accepts a folder or a .zip (not only single files) | P2 (requested by user) | **done** | Client-side unzip; backend unchanged. Touches P1's M1 area, see open item 10. |

## Handoffs

| # | Handoff | From -> To | Status |
|---|---|---|---|
| H1 | Contract + decisions D1-D10 | both | **pending** - not yet agreed |
| H2 | Minimum demo documents (claim B) | P2 -> P1 | **done** (`20b2aa8`, run `git pull`) |
| H3 | Fixture results JSON | P2 -> P1 | **done** (`20b2aa8`) |
| H4 | Results API + polling hook | P1 -> P2 | waiting (Phase 3) |
| H5 | `GET /documents/{id}/file` | P1 -> P2 | waiting (Phase 3) |
| H6-H9 | Extracted fields, clauses/summary, action plan, findings | see plan | not due yet |

## Open items / heads-up

**For Person 1** (raised 2026-11-14 by Person 2):
1. `git pull` to get claim B documents and the fixture (`sample_documents/`). The fixture is the shape the stubs should return.
2. Decide who does the contract freeze + folder migration. Proposal: Person 1 does it (owns backend core), Person 2 reviews. **Nobody has touched `backend/app/schemas/` yet.**
3. Contract gap: the claimed amount comes from the claim form, not a document, so `EvidenceRef` needs a `source` field (`document` | `claim_form`). The fixture already uses it.
4. Contract gap: passed checks are a separate `checks_passed: list[str]` (a consistent item has no finding behind it). The fixture already uses it.
5. Missing from M1 in the plan, needed by the demo's re-check step: `PATCH /claims/{id}` (edit claimed amount) and `DELETE /claims/{id}/documents/{doc_id}` (remove the duplicate bill).

**For Person 1, from the verification work** (raised 2026-11-14 by Person 2):
6. **Review `backend/app/schemas/contract.py`.** It is the plan's section 4 as Pydantic models, with I1 (a `Finding` needs evidence) and I3 (an `Action` needs `finding_ids`) enforced as validation. Changes vs the plan: `EvidenceRef.source` is `document | claim_form | checklist`; `checks_passed` is a separate list; `ExtractedField.confidence` is a float 0-1. If you already wrote different models, reconcile against this one - the fixture and 48 tests validate against it. The old `schemas/results.py` is untouched.
7. **Engine signature differs slightly from the plan:** `run_verification(fields, documents, claim)` returns `VerificationResult(findings, checks_passed, rules_run)`, not just `list[Finding]`, because the "appears consistent" list needs the passed checks. Module: `backend/app/modules/verification/`. The pipeline's `verify` node should call it.
8. **What the engine expects from `normalize` (M2):** `patient_name`, `policy_number`, `member_id`, `bill_number`, `hospital_name` as strings; dates as ISO strings (`2026-08-12`, other common formats also parse); amounts numeric (`"Rs. 85,000"` also parses); each `line_item` value a dict with an `amount`; `referenced_document` as free text such as "prescription no. RX-7781". Each field needs `evidence.document_id` matching a `DocumentInfo.id` with the right `doc_type`.
9. **Fixture regenerated:** the copy bill, bill and discharge summary now also carry policy/member IDs and invoice numbers (32 -> 42 fields) so cross-document rules have data. Run `git pull` again when committed. Fixture shape is unchanged.

10. **Heads-up, frontend upload changed (M1 is yours, so pull before editing it):** `frontend/src/components/DocumentUpload.tsx` now takes files, a folder (button or drag-and-drop) or a `.zip`. New file `frontend/src/lib/ingest.ts` does the work in the browser (`fflate` added to `package.json`); hidden/system files (`.DS_Store`, `__MACOSX`), non-PDF/PNG/JPG files and nested zips are skipped with a notice, zips are capped (200 entries, 200 MB total, 20 MB per file). The backend API is **unchanged**: each document is still uploaded through `POST /claims/{id}/documents`. Category guessing now falls back to the folder path. New demo file `sample_documents/claim_b_upload.zip` (the 6 upload files, without the held-back prescription).

**Decisions still proposed, not confirmed** (see section 4 of the plan): D1 async analyze + polling, D2 `claimed_amount` on the claim form, D3 readiness rule, D4 required-documents checklist, D5 packet wording/watermark, D6 model names/keys, D7 feature-folder layout, D8 confidence threshold 0.75, D9 cache key, D10 Core/Wow/Stretch tiers.

## Change log (newest first)

| Date | Who | Change | Commit |
|---|---|---|---|
| 2026-11-14 | P2 | **Upload takes a folder or a .zip:** `frontend/src/lib/ingest.ts` (in-browser unzip with `fflate`, folder picker + folder drag-and-drop, junk/unsupported/nested-zip skipping, size and entry caps, corrupt-zip handling), `DocumentUpload.tsx` updated (Choose folder / Choose .zip buttons, path shown per file, notice banner), `sample_documents/claim_b_upload.zip` + generator support. Logic tested in Node against a messy zip (6 real docs kept, 6 junk entries skipped, corrupt zip reported); lint + tsc clean. Not yet clicked through in a browser. Backend unchanged. | `e28637e` |
| 2026-11-14 | P2 | **Verification engine** `backend/app/modules/verification/` (rules V1, V2, V3, V4, V5, V7, V14; deterministic, evidence on every finding, stored inputs); draft contract `backend/app/schemas/contract.py`; `backend/tests/test_verification.py` (48 tests incl. claim B end-to-end vs ground truth, quote-on-PDF-page check, and the demo fix sequence clearing all 3 blocking items). Fixed 2 bugs found by tests (amount parsing of "Rs. 85,000", name-variant threshold). Regenerated claim B fixture with more cross-document fields. **58 backend tests pass.** | `8dfba15` |
| 2026-11-14 | P2 | Created this progress log | `e6b419c` |
| 2026-11-14 | P2 | Added synthetic claim B (7 PDFs), ground truth with verified quotes, AnalysisResults fixture, deterministic generator `sample_documents/tools/generate_claim_b.py`, `sample_documents/README.md` | `20b2aa8` |
| 2026-11-14 | P2 | Rewrote `docs/DIVISION_OF_WORK.md`: feature-module split, architecture diagrams, USP guard rails, Build Guide integration (Wow set, V1-V14 rules, model routing), phases + handoffs | `290c25a` |
| 2026-11-13 | both | Phase 0-1: environment checked, monorepo, FastAPI + Next.js skeleton, health check, upload API/UI, 10 backend tests, README, `.env.example` files | `9bb20d0`, `88e3c0b`, `483f375` |
