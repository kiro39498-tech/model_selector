# AI Application Architect

Design a complete software application and determine the best AI model for each
task within it.

The application guides you through **requirements discovery**, decomposes your
application into **components and workflows**, and produces **evidence-backed
model recommendations** (up to three ranked candidates per AI task) — without
fabricating model names, parameter counts, benchmark results, prices, or
citations.

> **Status:** Working end-to-end vertical slice. See
> [Known limitations](#known-limitations-and-unverified-integrations).

---

## Prerequisites

- **Python 3.11+**
- **Node.js 20+** and npm
- A **Neon PostgreSQL** connection string
- An **OpenAI-compatible AI endpoint** key (the configured reasoning endpoint)

## Environment configuration

### Backend

Copy `backend/.env.example` to `backend/.env` and fill in real values:

```
AI_BASE_URL=http://indiaai.maqsoftware.net/v1
AI_MODEL=qwen3.8-27b
AI_API_KEY=<your-secret>
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DBNAME?sslmode=require
CORS_ORIGINS=http://localhost:5173
CLASSIFICATION_THRESHOLD_BILLIONS=150
```

> **Never commit `.env`.** It is excluded by `.gitignore`. The AI endpoint is a
> *reasoning* endpoint — it is not assumed to browse the web, enumerate models,
> or invoke other models.

### Frontend

The frontend talks to the backend at `http://localhost:8000` (proxied via Vite
in development). No secrets are placed in the frontend bundle.

## Backend startup

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Health checks:

- `GET /health` — application + configuration status (no secrets)
- `GET /health/db` — database reachability
- `GET /health/ai` — AI endpoint reachability

## Frontend startup

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

## Database migrations

Migrations are **not** run automatically at startup. Apply them explicitly:

```bash
cd backend
alembic upgrade head
```

To seed the curated model registry (illustrative, honestly-labeled):

```bash
python -m app.seed_registry
```

## Tests

### Backend

```bash
cd backend
python -m pytest -v
```

### Frontend

```bash
cd frontend
npm run test        # unit tests (Vitest + React Testing Library)
npm run build       # type-check + production build
```

## Endpoint configuration

| Variable | Purpose |
|---|---|
| `AI_BASE_URL` | OpenAI-compatible base URL |
| `AI_MODEL` | Configured model identifier |
| `AI_API_KEY` | Secret key (never logged or returned) |
| `DATABASE_URL` | Neon PostgreSQL connection string |
| `CORS_ORIGINS` | Comma-separated allowed origins |
| `CLASSIFICATION_THRESHOLD_BILLIONS` | SLM/LLM threshold (default 150) |

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `ai_service_unavailable` (503) | `AI_API_KEY` missing or endpoint unreachable. Check `GET /health/ai`. |
| `database_unreachable` | `DATABASE_URL` missing or wrong. Check `GET /health/db`. |
| Analysis returns 409 | Requirements must be **approved** before analysis. |
| Approve returns 409 | Critical (high-criticality) requirements are unresolved. |
| Frontend can't reach API | Ensure the backend is running on port 8000 (Vite proxies `/api`). |

## Security considerations

- Secrets are read from the environment only; `.env` is git-ignored.
- API keys and DB credentials are never logged, returned in responses, or placed
  in the frontend bundle.
- All AI responses are validated server-side with Pydantic; malformed responses
  are handled with a bounded repair and never silently substituted with
  fabricated data.
- User-provided text, documents, and model metadata are treated as untrusted and
  cannot override system instructions or security policies.
- The classification threshold and other policy values are configurable, not
  hardcoded.

## Architecture documentation

- **Backend:** `backend/app/` — FastAPI app, routers, services, models, schemas.
- **Frontend:** `frontend/src/` — React screens, API client, components.
- **Database:** `backend/app/models.py` (ORM) + `backend/alembic/` (migrations).
- **AI integration:** `backend/app/services/ai_service.py` (dedicated service).
- **Classification policy:** `backend/app/services/classification.py`.
- **Model registry seed:** `backend/app/seed_registry.py`.

## Known limitations and unverified integrations

- **The AI endpoint cannot browse the web or enumerate models.** Model
  recommendations are reasoned over a **curated, source-backed registry**
  (official documentation URLs, parameter counts, conservative availability
  labels). Verified facts are always distinguished from AI-inferred content.
- **Live model evaluation is not executed automatically.** Evaluation *planning*
  is implemented; *execution* against external endpoints requires explicit
  configuration and approval. No benchmark results are fabricated.
- **Analysis runs synchronously** in this slice. A production deployment should
  use an explicit asynchronous execution design.
- **No authentication** (single-user / local tool, per the approved decision).
- The seed registry is **illustrative**; availability and pricing are labeled
  conservatively and must be verified before production use.

## Deployment guide

1. Provision a Neon PostgreSQL database and set `DATABASE_URL`.
2. Set `AI_API_KEY`, `AI_BASE_URL`, `AI_MODEL`.
3. `alembic upgrade head` to create the schema.
4. `python -m app.seed_registry` to load the curated registry.
5. Run the backend with `uvicorn app.main:app --port 8000`.
6. Build the frontend (`npm run build`) and serve `dist/`, or run `npm run dev`.
7. Verify `GET /health`, `GET /health/db`, and `GET /health/ai`.
