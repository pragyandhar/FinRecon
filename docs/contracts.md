# FinRecon — Contracts

Single source of truth for every structured object that crosses a stage
boundary. Each contract below is implemented 1:1 as a Pydantic model in
`backend/app/models/`. If a contract changes: update this file, add a
line to `docs/decisions.md`, update the model, update dependent code, run
tests.

Build note: this pass implements the **core reconciliation loop**
(ingestion → schema understanding → canonical mapping → planning →
validation → execution → results → metrics → exception investigation →
report → chat). Auth/authz, encrypted-at-rest storage, PDF extraction,
LangSmith tracing and the full adversarial test matrix from
`context/architecture.md` are out of scope for this pass — see
`docs/decisions.md`.

---

## 1. Dataset (`app/models/dataset.py`)

Output of ingestion. One per uploaded sheet/file.

```json
{
  "dataset_id": "payments",
  "job_id": "job_abc123",
  "source_file": "payments.csv",
  "columns": [{"name": "Txn ID", "raw_type": "string"}],
  "row_count": 128,
  "column_stats": [
    {
      "name": "Txn ID",
      "inferred_type": "string",
      "null_rate": 0.0,
      "unique_rate": 1.0,
      "sample_values": ["TX1001", "TX1002", "TX1003"]
    }
  ]
}
```

`DatasetRow` (stored separately, one row per record):

```json
{
  "row_id": "payments_0001",
  "dataset_id": "payments",
  "values": {"Txn ID": "TX1001", "Amount Paid": 1000},
  "source_file": "payments.csv",
  "sheet": null,
  "row_index": 1
}
```

`column_stats` — not raw rows — is what gets sent to the schema model.

---

## 2. Schema JSON (`app/models/schema.py` — `SchemaJSON`)

Output of schema understanding.

```json
{
  "job_id": "job_abc123",
  "datasets": [
    {
      "dataset_id": "payments",
      "purpose": "payment_records",
      "fields": [
        {
          "name": "Txn ID",
          "semantic_type": "identifier",
          "role": "primary_key",
          "nullable": false,
          "confidence": 0.95
        }
      ]
    }
  ]
}
```

`semantic_type` ∈ `identifier | currency_amount | date | status |
customer_reference | text | other`. `role` ∈ `primary_key | foreign_key
| measure | attribute`.

## 3. Canonical Mapping (`app/models/schema.py` — `CanonicalMapping`)

```json
{
  "job_id": "job_abc123",
  "mapping": {
    "payments": {"payment_id": "Txn ID", "payment_amount": "Amount Paid"},
    "settlements": {"payment_id": "Transaction Ref", "settlement_amount": "Net Amount"}
  }
}
```

Never rewrites raw data — a lookup layer only. Schema JSON and Canonical
Mapping are produced by a **single combined LLM call** (see
`docs/decisions.md` #1) to cut cost/latency; they remain two separate
contracts because downstream code addresses them independently.

---

## 4. Reconciliation Plan (`app/models/plan.py`)

```json
{
  "job_id": "job_abc123",
  "plan_version": 1,
  "steps": [
    {
      "step_id": "s1_join",
      "operation": "JOIN",
      "left": "payments",
      "right": "settlements",
      "left_field": "payment_id",
      "right_field": "payment_id",
      "join_type": "full_outer"
    },
    {
      "step_id": "s2_compare_amount",
      "operation": "COMPARE",
      "input": "s1_join",
      "comparison": "TOLERANCE",
      "field_a": "payment_amount",
      "field_b": "settlement_amount",
      "tolerance": 10
    },
    {
      "step_id": "s3_missing",
      "operation": "MISSING",
      "input": "s1_join",
      "side": "right"
    }
  ]
}
```

Operation vocabulary (fixed, engine hardcodes semantics not field
names): `JOIN, COMPARE, MISSING, DUPLICATE, FILTER, GROUP, AGGREGATE`.
`COMPARE.comparison` ∈ `EQUALS, NOT_EQUALS, TOLERANCE, DATE_DIFF,
DATE_WITHIN`. `AGGREGATE.agg_function` ∈ `SUM, COUNT, AVG`.

Per-operation required-field contracts live in
`backend/app/validation/contracts.py` and are the authority the
validator checks against — this doc shows the shape, that file shows
what's mandatory.

`left`/`right`/`input` may reference either a raw `dataset_id` or an
earlier step's `step_id`, so steps chain (`orders → payments →
settlements`).

---

## 5. Validation Result (`app/models/validation.py`)

```json
{
  "job_id": "job_abc123",
  "plan_version": 1,
  "is_valid": false,
  "issues": [
    {"step_id": "s2_compare_amount", "field": "tolerance", "message": "tolerance must be >= 0"}
  ]
}
```

An invalid plan is sent back to the planner with these issues (bounded
retries, `MAX_PLAN_RETRIES`), never executed.

---

## 6. Reconciliation Result (`app/models/result.py`)

One per evaluated record.

```json
{
  "record_id": "payment_id:TX1023",
  "job_id": "job_abc123",
  "step_id": "s2_compare_amount",
  "status": "MISMATCHED",
  "rule_applied": "TOLERANCE(10)",
  "checks": [
    {"field": "payment_amount vs settlement_amount", "expected": 1000, "actual": 950, "result": "OUT_OF_TOLERANCE"}
  ],
  "evidence": [
    {"dataset_id": "payments", "row_id": "payments_0022", "values": {"payment_id": "TX1023", "payment_amount": 1000}},
    {"dataset_id": "settlements", "row_id": "settlements_0019", "values": {"payment_id": "TX1023", "settlement_amount": 950}}
  ],
  "reason": null
}
```

`status` ∈ `MATCHED | MISMATCHED | EXCEPTION | UNRESOLVED`. Records are
never silently dropped — every row touched by a check step produces one
of these.

---

## 7. Exception Explanation (`app/models/investigation.py`)

Investigator output, one per `EXCEPTION` record, produced by a single
**batched** LLM call per job (not one call per record).

```json
{
  "record_id": "payment_id:TX1023",
  "reason": "Settlement amount is 50 below payment amount.",
  "evidence_used": ["payments_0022.payment_amount=1000", "settlements_0019.settlement_amount=950"],
  "likely_cause": "Processing fee deduction",
  "recommended_action": "Verify settlement fee configuration.",
  "confidence": 0.7,
  "resolved": true
}
```

If the model cannot ground an explanation in the evidence it was given,
`resolved: false` and the record stays `UNRESOLVED` in the report rather
than getting a fabricated explanation.

---

## 8. Report (`app/models/report.py`)

```json
{
  "job_id": "job_abc123",
  "generated_at": "2026-09-04T12:00:00Z",
  "metrics": {
    "total_records": 200, "matched": 173, "mismatched": 27, "exceptions": 0,
    "unresolved": 0, "match_rate": 0.865, "mismatch_rate": 0.135,
    "exception_rate": 0.0, "unresolved_rate": 0.0, "total_variance_amount": 640.0
  },
  "by_step": [
    {
      "step_id": "s2_compare_order_payment", "rule_applied": "TOLERANCE(1.0)",
      "total_records": 100, "matched": 91, "mismatched": 9, "exceptions": 0,
      "unresolved": 0, "match_rate": 0.91, "mismatch_rate": 0.09,
      "exception_rate": 0.0, "unresolved_rate": 0.0, "total_variance_amount": 210.0
    },
    {
      "step_id": "s4_compare_payment_settlement", "rule_applied": "TOLERANCE(1.0)",
      "total_records": 100, "matched": 82, "mismatched": 18, "exceptions": 0,
      "unresolved": 0, "match_rate": 0.82, "mismatch_rate": 0.18,
      "exception_rate": 0.0, "unresolved_rate": 0.0, "total_variance_amount": 430.0
    }
  ],
  "results": ["... ReconciliationResult[] ..."],
  "exception_explanations": ["... ExceptionExplanation[] ..."],
  "ai_calls_made": 3
}
```

`metrics` and `by_step` are computed entirely in code from `results` —
never asserted by a model. `metrics` is the combined total across every
check step the plan ran; if a plan runs two distinct comparisons over
overlapping records (as above — order vs payment, then payment vs
settlement), `metrics.total_records` is the sum of both, which can
legitimately exceed the row count of any single input file. This is
not double-counting the same check twice; it's two different checks.
`by_step` gives each check its own honest, un-blended match rate, so a
combined figure never hides which specific relationship is broken —
the dashboard leads with `by_step` for this reason.

---

## 9. Chat (`app/models/chat.py`)

Request:
```json
{"session_id": "chat_xyz", "message": "Why was TX1023 flagged?", "record_id": "payment_id:TX1023"}
```

Response:
```json
{"session_id": "chat_xyz", "reply": "...", "context_used": ["payment_id:TX1023 result + evidence"]}
```

The chat handler resolves `record_id` (or infers it from the message) to
its `ReconciliationResult` + `ExceptionExplanation` and sends only that
slice to the model — never the full dataset.

---

## 10. Job (`app/models/job.py`)

```json
{"job_id": "job_abc123", "status": "RECONCILING", "created_at": "...", "updated_at": "...", "error_code": null, "error_message": null}
```

`status` state machine: `UPLOADED → EXTRACTING →
UNDERSTANDING_SCHEMA → PLANNING → VALIDATING_PLAN → RECONCILING →
INVESTIGATING → GENERATING_REPORT → COMPLETED`, with `FAILED` reachable
from any state, carrying `error_code` from `app/core/errors.py`.
