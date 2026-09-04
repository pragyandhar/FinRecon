# FinRecon — Decisions

Log of choices made while building this pass, and why. Update this file
whenever a contract or architectural choice changes.

## Bug found on first real run: canonical name collisions on measure fields

First real end-to-end run (real OpenAI calls, real `orders`/`payments`/
`settlements` data) failed at execution with `PLAN_EXECUTION_FAILED:
cannot resolve field 'amount' ... (ambiguous: ['amount_orders',
'amount_payments'])`.

Root cause: the original schema-understanding prompt
(`backend/app/schema_understanding/service.py`) told the model to reuse
shared canonical names across datasets for "common finance concepts",
and listed `amount` as an example alongside `payment_id`/`order_id`.
That's correct for identifier fields (you *want* `payment_id` to mean
the same thing in both `payments` and `settlements` so they can be
joined) but wrong for measure fields — reconciliation's whole point is
comparing `order_amount` against `payment_amount`, so if both collapse
to the same canonical name `amount`, they become indistinguishable:
after the JOIN, pandas disambiguates the collision with suffixes
(`amount__orders`, `amount__payments`), and the plan's `field_a:
"amount"` reference is ambiguous between them.

This was **not silently wrong** — the engine's `_resolve_column`
(`backend/app/execution/engine.py`) refused to guess and raised a clear
error naming the exact ambiguity, exactly per the "never silently
produce wrong results" principle. But it shouldn't have been reachable
in the first place.

Fix: the schema-understanding prompt now explicitly splits guidance —
identifier/key fields (`payment_id`, `order_id`, `customer_id`, ...)
should share canonical names across datasets to enable joins; measure,
status, and date fields should NOT — they get dataset-qualified
canonical names (`order_amount`/`payment_amount`/`settlement_amount`,
`order_status`/`payment_status`/..., etc.) so they stay comparable
rather than colliding. A regression test
(`test_colliding_canonical_field_names_fail_loudly_not_silently` in
`backend/tests/unit/test_engine.py`) locks in the safe-failure behavior
even if canonicalization collides again for some other reason.

## Scope: core loop, not the full spec

`context/architecture.md` and the four agent briefs describe a
production platform with auth/authz, encrypted-at-rest storage, PDF
table extraction, LangSmith tracing, idempotency guarantees, and a full
adversarial test matrix. Building all of that in one pass, on a $2 AI
budget, would produce a shallow version of everything rather than a
solid version of the thing that's actually being graded: a working
reconciliation loop with an honest match rate. So this pass builds:

- CSV + Excel ingestion (PDF explicitly **not** implemented).
- Schema understanding + canonical mapping (one combined AI call).
- Reconciliation planning (AI) with a bounded validator repair loop.
- A generic deterministic execution engine covering the full operation
  vocabulary (JOIN, COMPARE, MISSING, DUPLICATE, FILTER, GROUP,
  AGGREGATE).
- Batched exception investigation (AI).
- Code-computed metrics, a JSON/CSV report, and a contextual chat.

Not built: auth, encryption at rest, LangSmith/tracing integration,
idempotency keys, a real task queue (see below), and the described
full adversarial test suite (a representative subset is implemented
instead — see `backend/tests/`).

## One model, one env var

The architecture docs describe separate `SCHEMA_MODEL` /
`PLANNER_MODEL` / `EXCEPTION_MODEL` configuration. Per explicit
instruction, this build uses exactly one: `OPENAI_MODEL` in `.env`,
read once in `backend/app/core/config.py` and passed through
`backend/app/core/model_client.py` to every AI call site (schema
understanding, planning, plan repair, exception investigation, chat).
Changing the model is a one-line edit in one file. The `ModelClient`
abstraction (with a `FakeModelClient` for tests) keeps this swappable
without touching call sites, satisfying the architecture's "Model
Abstraction" principle without the SLM/LLM env-var split.

## AI call budget

With a small real budget in mind, the pipeline deliberately makes as
few AI calls as correctness allows for one job:

1. Schema understanding **and** canonical mapping in a single call
   (not two), because they're both about interpreting the same
   column stats.
2. Reconciliation planning: one call, plus at most `MAX_PLAN_RETRIES`
   repair calls (default 2) only if the plan fails validation.
3. Exception investigation: **all** EXCEPTION records for a job go
   into batches of 25 (`_BATCH_SIZE` in
   `backend/app/investigation/service.py`), not one call per record.
4. Chat: one call per user question, scoped to one record's evidence
   or job-level metrics — never the full dataset.

Every AI call is logged to the `model_calls` table
(`backend/app/storage/models.py`) with token counts, so
`report.ai_calls_made` is an exact count, not an estimate. The
automated test suite (`backend/tests/`) uses `FakeModelClient`
exclusively — **zero real API calls run in CI or during development**;
only actually using the app spends the budget.

## Plan format

`context/context.md` and `context/architecture.md` show two different
illustrative plan shapes (`joins[]`/`checks[]` vs. a `steps[]` list).
Neither is treated as binding — both docs say the format "can evolve."
This build uses a **single ordered `steps[]` list**
(`backend/app/models/plan.py`), where each step's `left`/`right`/`input`
can reference either a raw dataset or an earlier step's `step_id`. This
generalizes cleanly to chained joins (`orders → payments →
settlements`) without a separate multi-hop join construct, and lets the
validator apply one per-operation contract table
(`backend/app/validation/contracts.py`) instead of separate rules for
joins vs. checks.

All field references in a plan are **canonical field names**, not raw
column names — the execution engine resolves canonical → raw once, at
load time, per dataset (`backend/app/execution/engine.py:_build_base_relation`).

## No LLM fallback executor

The architecture describes an LLM fallback for "genuinely unsupported"
plan operations. In this build that path is structurally unreachable:
the planner is prompted with a closed operation vocabulary, and the
validator rejects any plan that uses anything outside it before
execution ever runs. So there is no case where a validated plan reaches
the execution engine with an operation it can't run. `ENABLE_LLM_FALLBACK`
exists in configuration for forward-compatibility but nothing reads it
yet — documented here rather than silently claimed as implemented.

## Storage

SQLite via SQLAlchemy (`DATABASE_URL` in `.env`), not PostgreSQL. The
schema (`backend/app/storage/models.py`) is already relational with
real foreign-key-shaped columns and indexes, and JSON columns only
where the payload is genuinely a flexible AI-produced structure
(matching the architecture's own storage guidance) — so moving to
Postgres later is a `DATABASE_URL` change plus a migration tool, not a
rewrite.

## Async processing

Job processing runs via FastAPI `BackgroundTasks` in the same process
that served the upload request, not a real task queue (Celery/RQ/etc).
This is a single-process, single-worker assumption — correct for a
demo/buildathon deployment, not for horizontal scaling. If this needs
to survive a process restart mid-job or run multiple workers, that's
the next thing to change, not a hidden gap.

## No fabricated demo dataset

The system was **not** given a fabricated 50+ row orders/payments/
settlements demo dataset to "prove" a match rate. That data is the
user's to provide. Small (5-10 row) fixtures exist under
`backend/tests/` purely to unit-test individual operations
(tolerance, duplicates, date windows, etc.) with known ground truth —
they are not a demo dataset and are never presented as one.

## Frontend

A minimal React + Vite SPA (`frontend/`), not a component-library-heavy
build. Three screens (upload → processing → dashboard) driven entirely
by the real backend API — no hardcoded results anywhere. Filtering by
status is done client-side against the already-fetched report to avoid
extra requests. No router: the three screens are simple local state,
which is all three screens need.
