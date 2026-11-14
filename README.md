# Covara

**Know your coverage. Prepare with confidence.**

AI-powered insurance claim readiness and intelligence. Hackathon scope: **health insurance** (property, travel and other domains are future scope). See [PLAN.md](PLAN.md) for the full plan.

> Covara is an AI-assisted preparation tool. It does not decide whether an insurer will approve a claim. Use synthetic documents only.

## What it does

A user uploads a health policy and hospital documents (typed PDFs, scans, phone photos, a handwritten prescription, or a whole folder / zip). Covara reads them, cross-checks them against each other and against the policy, and returns:

1. **Evidence-linked findings.** Every finding shows the source document and page, the extracted field, the exact quote, the policy clause (quoted verbatim from the uploaded policy) and the reason it was flagged. Click *Why was this flagged?*.
2. **An action plan** that says what to obtain, verify or clarify before submitting, who owns each step, with a ready-to-send message. Explanations can be shown in English or Hindi (Sarvam), read aloud, and dictated.
3. **A claim packet**: one PDF (cover, summary, index, evidence references, your originals with bookmarks), a readiness report PDF, and `claim.json`. The packet is stamped INCOMPLETE on every page while blocking items are open.

Deterministic Python code decides whether something is an issue; the AI only reads documents and phrases explanations. Covara never predicts approval or rejection, and every screen and PDF carries a disclaimer. Use **synthetic documents only**.

## Status

All of the above works end to end on the synthetic demo claims (see `sample_documents/README.md`). Not built: login, a database (claims are kept on local disk and expire), deployment, insurer/TPA integrations, structured FHIR input, and the Paytm integration.
Verification rules in place: duplicate bill (V1), patient identity (V2), policy number / member ID (V3), amounts (V4), dates (V5), required and referenced documents (V7), room-rent limit with an estimated exposure (V10), waiting period (V11), low-confidence fields (V14).

**Measured** (full pipeline against the synthetic ground truth, low-cost model): claim A (clean) 33/33 fields and **no false alarms**; claim B 41/41 fields and all 5 planted findings with the exact exposure estimate; claim C 36/36 and the waiting-period finding; claim D (phone-photo scans + handwritten prescription) 33/33 with Sarvam OCR. Model output varies a little between runs, so treat these as measurements of a few runs, not guarantees. Reproduce with the commands under **Evaluations** below.

## AI providers and cost

| Provider | Used for | Setting |
|---|---|---|
| Claude | Reading documents, classification, phrasing (low-cost model by default: Haiku) | `ANTHROPIC_API_KEY` + `ANTHROPIC_MODEL`, **or** no key: uses your logged-in Claude Code session (`claude -p`) with `CLAUDE_CLI_MODEL` (default `haiku`) |
| Sarvam | OCR of scans / photos / Indic text (Sarvam Vision), translation, speech to text, text to speech | `SARVAM_API_KEY` |
| Gemini, Groq | Optional fallbacks | `GEMINI_API_KEY`, `GROQ_API_KEY` |

Every model result is cached in `backend/.cache` by file hash, so re-running the same documents costs nothing. `DEMO_MODE=true` replays the cache only and never calls a provider. The Claude Code session path is for local development and demos, not production. With no provider at all, a weaker rule-based reader still runs.

## Settings (`backend/.env`, see `.env.example`)

| Setting | Default | Meaning |
|---|---|---|
| `FRONTEND_ORIGIN` | localhost:3000 | CORS origins (comma-separated) |
| `MAX_UPLOAD_MB` | 20 | Per file |
| `PERSIST_CLAIMS` | true | Save claims to `backend/.data/` (git-ignored) so they survive a restart |
| `RETENTION_HOURS` | 72 | Claims older than this are deleted with their files and cached AI output (0 = keep) |
| `DEMO_MODE` | false | Replay cached AI results only |
| `ANTHROPIC_*`, `CLAUDE_*`, `SARVAM_API_KEY`, `GEMINI_*`, `GROQ_*` | | See the table above |

## Privacy

Consent is recorded before upload; **Delete my data** removes the files, extracted data, results, the saved snapshot and cached AI output; claims expire automatically; error logs record only the error type and location, never document content; uploaded originals are never modified and are stored under random names. This is designed around data-protection principles but has **not** been through a compliance review.

## Structure

```
frontend/          Next.js 16 (App Router, TypeScript, Tailwind, shadcn/ui), English + Hindi
  src/features/      one folder per feature: intake, extraction, verification, policy, evidence, actions, packet, pipeline
backend/           FastAPI (Python 3.12), LangGraph pipeline
  app/modules/       intake, extraction, policy, verification, evidence, actions, packet, pipeline, language
  app/core/          llm (providers, cache), sarvam, persistence, safe_log
  app/schemas/       claim.py, results.py (API contract)
  tests/             pytest + evals (eval_claim_b, eval_claims)
sample_documents/  synthetic claims A-D, ground truth, and tools/claimgen (generates them from data)
docs/              architecture, modules, phases (DIVISION_OF_WORK.md)
PROGRESS.md        shared status board
```

## Prerequisites

| Tool | Version used | Install |
|---|---|---|
| Node.js + npm | 25.x / 11.x (Node 20.9+ should work) | https://nodejs.org |
| uv | 0.9+ | `brew install uv` |
| Python | 3.12 (uv fetches it automatically) | `uv python install 3.12` |

## 1. Backend setup (once)

```bash
cd backend
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -r requirements.txt
cp .env.example .env        # add SARVAM_API_KEY (and ANTHROPIC_API_KEY if you have one); see Settings below
```

## 2. Frontend setup (once)

```bash
cd frontend
npm install
cp .env.example .env.local
```

## 3. Run (two terminals)

**Terminal 1 - backend (http://localhost:8000):**

```bash
cd backend
.venv/bin/uvicorn app.main:app --reload --port 8000
```

**Terminal 2 - frontend (http://localhost:3000):**

```bash
cd frontend
npm run dev
```

Open http://localhost:3000. The header badge shows **API online** when the frontend can reach the backend. Interactive API docs: http://localhost:8000/docs.

## Evaluations (full pipeline vs ground truth)

```bash
cd backend
.venv/bin/python -m tests.eval_claims a       # a = clean claim, c = waiting period, d = photographed paper
.venv/bin/python -m tests.eval_claim_b        # claim B, including the demo fix sequence
# add --fresh to bypass the cache (a true re-measure), --rules for the offline no-AI fallback
```

Regenerate a synthetic claim: `cd sample_documents/tools && ../../backend/.venv/bin/python -m claimgen a`.

## 4. Verify

```bash
# Health check
curl http://localhost:8000/health

# CORS preflight from the frontend origin (expect access-control-allow-origin: http://localhost:3000)
curl -i -X OPTIONS http://localhost:8000/claims \
  -H "Origin: http://localhost:3000" -H "Access-Control-Request-Method: POST"

# Create a claim, then upload a document to it
CID=$(curl -s -X POST http://localhost:8000/claims -H 'Content-Type: application/json' -d '{}' \
  | python3 -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s -X POST http://localhost:8000/claims/$CID/documents -F category=policy -F "files=@/path/to/file.pdf"
curl -s http://localhost:8000/claims/$CID/documents

# Backend tests
cd backend && .venv/bin/python -m pytest -q

# Frontend checks
cd frontend && npm run lint && npm run build
```

## API

| Method | Endpoint | Status |
|---|---|---|
| GET | `/health` | Working. Also reports which AI providers have keys configured (booleans only). |
| POST | `/claims` | Working. Creates a claim session. |
| GET | `/claims/{id}` | Working. |
| POST | `/claims/{id}/documents` | Working. Multipart: `category` (form field) + `files` (one or more). |
| GET | `/claims/{id}/documents` | Working. |
| PATCH | `/claims/{id}` | Update `claimed_amount` / `patient_name`. |
| DELETE | `/claims/{id}` | Delete my data: files, results, cached model outputs. |
| GET | `/claims/{id}/checklist` | Required vs received documents (D4), incl. referenced-but-missing. |
| GET | `/claims/{id}/documents/{doc_id}/file` | Original file (for the evidence viewer; append `#page=N`). |
| DELETE | `/claims/{id}/documents/{doc_id}` | Remove one document (e.g. a duplicate bill); press Re-check afterwards. |
| POST | `/claims/{id}/analyze` | `202`; starts or re-checks the pipeline. Poll `/results`. |
| GET | `/claims/{id}/results` | Full `AnalysisResults` (status, stage, progress, fields, clauses, policy summary, findings, action plan, checklist, readiness). |
| GET | `/claims/{id}/extraction` | Documents + extracted fields + ids needing review. |
| GET | `/claims/{id}/policy` | Policy summary + clause chunks with pages. |
| GET/POST | `/claims/{id}/review` | Low-confidence critical fields / confirm or correct values and re-check. |
| GET | `/claims/{id}/actions` · PATCH `/claims/{id}/actions/{action_id}` | Action plan / tick an action done. |
| GET | `/claims/{id}/summary?lang=` | Plain-language summary of the analysis in the chosen language (also what Listen reads aloud). |
| POST | `/speech/tts` | `{text, lang}` -> spoken reply (mp3). Needs `SARVAM_API_KEY`. |
| POST | `/translate` | `{texts, lang}` -> translations of backend text; numbers/dates/IDs preserved. |
| GET | `/speech/languages` | Supported languages and whether Sarvam is configured. |
| GET | `/claims/{id}/report` | Readiness report PDF (9 sections). `409` until an analysis has completed. |
| GET | `/claims/{id}/packet` | Claim packet PDF: cover + summary, document index, evidence references, then the originals with bookmarks. Stamped INCOMPLETE on every page while blocking items are open. |
| GET | `/claims/{id}/packet.json` | `claim.json`: the same facts as structured data (shaped to map to a health-claims exchange later; not FHIR). |
| GET | `/claims/{id}/documents/{doc_id}/pages/{n}/image` | Page as PNG with the cited text highlighted. Query: `highlight` (repeatable quote), `bbox` (`x0,y0,x1,y1`, 0-1), `dpi`. Headers say how many highlights were found. |

Upload rules: PDF / PNG / JPG only, max `MAX_UPLOAD_MB` (default 20) per file. The file's leading bytes must match its extension. Files are stored on disk at `backend/uploads/<claim_id>/<document_id>.<ext>` under server-generated names. The original filename is kept as sanitized metadata only. Claims are held **in memory**, so restarting the backend clears them.

## Languages, voice and Hindi scans (Sarvam)

- **Scans and photos** (Hindi or any Indian language) are read by Sarvam Vision first, then Claude structures the text; quotes are checked against the OCR text and shown with an approximate highlight box. Documents are classified automatically when uploaded with category "other".
- **Languages**: English and Hindi, via the language selector on every page. Static UI text comes from `frontend/src/i18n/translations.json` (generated once with Sarvam by `backend/scripts/gen_i18n.py`; machine translation, have a native speaker review it; the script is resumable and only translates missing sentences). Text from the backend (findings, actions, explanations) is translated on demand; **amounts, dates, IDs and file names are protected and never altered**: if a protected value would be lost, that sentence stays English. To add a language: add it to `LANGUAGES` in `app/core/sarvam.py` and `frontend/src/i18n/index.tsx`, then run the script (it makes many Sarvam calls).
- **Listen**: the results banner has a Listen button that reads the claim summary aloud in the selected language (Sarvam Bulbul). It appears only when `SARVAM_API_KEY` is set.
- Rate limits: Sarvam throttles translation; bulk generation is paced. For demos use `npm run build && npm start` (the dev server hot-reloads when the dictionary file changes).

**Hindi demo claim** (synthetic): `sample_documents/hindi_demo_upload.zip` holds a Hindi scanned bill, a Hindi scanned prescription and four English documents. Enter 95000 as the claimed amount; expect one blocking issue (bill 85,000 vs claimed 95,000) and one name variant to review; correcting the amount to 85000 and pressing Re-check clears the blocker. Regenerate with `backend/.venv/bin/python sample_documents/tools/generate_hindi_demo.py`; check with `cd backend && .venv/bin/python -m tests.eval_hindi_demo`. The scans are printed-style, **not real handwriting**.

## Environment variables

`backend/.env` (see `backend/.env.example`): `APP_ENV`, `FRONTEND_ORIGIN` (comma-separated CORS origins), `MAX_UPLOAD_MB`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `SARVAM_API_KEY` (scan OCR, translation, voice).

`frontend/.env.local` (see `frontend/.env.example`): `NEXT_PUBLIC_API_URL`. **Never put secrets in `NEXT_PUBLIC_` variables.**

`ANTHROPIC_MODEL` defaults to `claude-sonnet-5-5` (API key path only; the Claude Code path uses your session's model, or `CLAUDE_CLI_MODEL`). `GEMINI_MODEL` defaults to `gemini-2.5-flash` and `GROQ_MODEL` to `llama-3.1-8b-instant` if left empty (check current model IDs). `DEMO_MODE=true` replays cached model outputs only (no live calls). Model outputs are cached in `backend/.cache/` by file hash.

AI providers are optional. The app boots without keys, and `backend/app/services/providers.py` lazily creates Gemini, Groq and Sarvam clients once a key is set.

## Troubleshooting

- **Badge says "API offline":** the backend is not running, or `NEXT_PUBLIC_API_URL` is wrong. Restart `npm run dev` after editing `.env.local`.
- **CORS error in the browser console:** add the page's exact origin (scheme, host and port) to `FRONTEND_ORIGIN` in `backend/.env`, then restart the backend.
- **Port in use:** `lsof -i :8000` (or `:3000`), then stop that process.
