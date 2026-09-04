# FinRecon

**AI-powered financial reconciliation system that automatically analyzes, matches, and investigates records across multiple financial datasets.**

Understand → Standardize → Plan → Validate → Execute → Investigate →
Report. Schema understanding and reconciliation planning are AI calls;
the actual reconciliation is deterministic code interpreting a
validated plan. See `docs/contracts.md` for the exact data contracts
and `docs/decisions.md` for what's implemented in this pass vs. the
full `context/architecture.md` spec (auth, PDF ingestion, encryption at
rest, and a task queue are explicitly **not** built yet).

## Requirements

- Python 3.11+
- Node 18+
- An OpenAI API key

## Setup

```bash
cp .env.example .env
# edit .env: set OPENAI_API_KEY. OPENAI_MODEL controls every AI call
# in the system from this one place (default: gpt-4o-mini).
```

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API is now at `http://localhost:8000` (`/health` to check it's up).
SQLite storage and raw file storage are created automatically under
`backend/storage/` on first run.

Run the test suite (uses `FakeModelClient` everywhere — **zero real API
calls**, safe to run as often as you like):

```bash
cd backend && source .venv/bin/activate && python -m pytest -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The dev server proxies `/reconciliation`
and `/health` to the backend on port 8000 (see `frontend/vite.config.ts`).

## Using it

1. Upload two or more CSV/Excel files that should reconcile against
   each other (e.g. payments vs. settlements). No specific column
   names are required — the system infers meaning from the data itself.
2. Watch the job move through its stages (extraction → schema
   understanding → planning → validation → reconciliation →
   investigation → report).
3. On completion: match rate and record counts, a filterable results
   table (All / Matched / Mismatched / Exception / Unresolved), and a
   detail panel per record with evidence and — for exceptions — an
   AI-grounded explanation.
4. Ask the contextual assistant a question about a specific record or
   the report as a whole; it's given only the relevant evidence, never
   the full dataset.
5. Export results as CSV from the dashboard, or fetch the full JSON
   report at `GET /reconciliation/jobs/{id}/report`.

## Every AI call is logged and bounded

`report.ai_calls_made` and the `model_calls` table are an exact count
of every AI call a job made, with token usage — not an estimate. Per
job that's typically: 1 call for schema understanding + canonical
mapping (combined), 1 call for planning (plus up to `MAX_PLAN_RETRIES`
repair calls only if the plan fails validation), and one **batched**
call per 25 exceptions (not one call per exception). Chat is one call
per question, scoped to the relevant record or job metrics only.

## Project layout

```text
backend/app/
  api/                 FastAPI routers
  core/                config, errors, logging, model client, pipeline orchestration
  models/              Pydantic domain models (the contracts in docs/contracts.md)
  ingestion/           CSV/Excel extraction, validation
  schema_understanding/ AI: schema + canonical mapping
  planning/            AI: reconciliation plan generation + repair loop
  validation/          plan contract table + validator (pure code)
  execution/           the generic deterministic engine (pure code)
  investigation/       AI: batched exception investigation
  reporting/           metrics (pure code), report assembly, CSV export
  chat/                contextual chat
  storage/             SQLAlchemy models + repository

frontend/src/          React + Vite SPA: upload -> processing -> dashboard
docs/                  contracts.md, decisions.md
```
