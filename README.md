# Covara

**Know your coverage. Prepare with confidence.**

AI-powered insurance claim readiness and intelligence. Hackathon scope: **health insurance** (property, travel and other domains are future scope). See [PLAN.md](PLAN.md) for the full plan.

> Covara is an AI-assisted preparation tool. It does not decide whether an insurer will approve a claim. Use synthetic documents only.

## Status

**Phase 1 (skeleton) is done:** health check, claim creation, document upload, landing page and upload UI.
Extraction, verification, policy retrieval and report generation are **not** implemented yet. `analyze`, `results` and `report` return `501`.

## Structure

```
frontend/          Next.js 16 (App Router, TypeScript, Tailwind, shadcn/ui, Lucide)
backend/           FastAPI (Python 3.12)
  app/main.py        app + CORS
  app/config.py      settings from backend/.env
  app/api/routes/    health.py, claims.py
  app/schemas/       claim.py, results.py (API contract)
  app/services/      claim_store.py, providers.py (Gemini / Groq / Sarvam)
  app/utils/         upload validation helpers
  tests/             pytest
sample_documents/  synthetic demo data (policy/, medical/, expected_results/)
docs/
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
cp .env.example .env        # then add API keys when you have them (all optional for now)
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

## API (Phase 1)

| Method | Endpoint | Status |
|---|---|---|
| GET | `/health` | Working. Also reports which AI providers have keys configured (booleans only). |
| POST | `/claims` | Working. Creates a claim session. |
| GET | `/claims/{id}` | Working. |
| POST | `/claims/{id}/documents` | Working. Multipart: `category` (form field) + `files` (one or more). |
| GET | `/claims/{id}/documents` | Working. |
| POST | `/claims/{id}/analyze` | `501`, later phase. |
| GET | `/claims/{id}/results` | `501`, later phase. |
| GET | `/claims/{id}/report` | `501`, later phase. |

Upload rules: PDF / PNG / JPG only, max `MAX_UPLOAD_MB` (default 20) per file. The file's leading bytes must match its extension. Files are stored on disk at `backend/uploads/<claim_id>/<document_id>.<ext>` under server-generated names. The original filename is kept as sanitized metadata only. Claims are held **in memory**, so restarting the backend clears them.

## Environment variables

`backend/.env` (see `backend/.env.example`): `APP_ENV`, `FRONTEND_ORIGIN` (comma-separated CORS origins), `MAX_UPLOAD_MB`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `GROQ_API_KEY`, `GROQ_MODEL`, `SARVAM_API_KEY`.

`frontend/.env.local` (see `frontend/.env.example`): `NEXT_PUBLIC_API_URL`. **Never put secrets in `NEXT_PUBLIC_` variables.**

AI providers are optional. The app boots without keys, and `backend/app/services/providers.py` lazily creates Gemini, Groq and Sarvam clients once a key is set.

## Troubleshooting

- **Badge says "API offline":** the backend is not running, or `NEXT_PUBLIC_API_URL` is wrong. Restart `npm run dev` after editing `.env.local`.
- **CORS error in the browser console:** add the page's exact origin (scheme, host and port) to `FRONTEND_ORIGIN` in `backend/.env`, then restart the backend.
- **Port in use:** `lsof -i :8000` (or `:3000`), then stop that process.
