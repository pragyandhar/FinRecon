# Agent 4 — QA, Integration, Demo & Production Hardening

## Mission
Be the final integration owner. Run the project, find failures, fix them, and make it demo-ready. Do not merely write a review.

## Read First
Read:
- `/MASTER_PROMPT.md`
- `/docs/architecture.md`
- `/docs/contracts.md`
- all integration notes
- README
- configuration
- entire repository

## Responsibilities

### 1. Build/startup verification
Test installation and startup of backend and frontend. Fix:
- dependency errors
- import errors
- environment problems
- startup crashes
- API mismatches

### 2. End-to-end test
Use:
- `orders.csv`
- `payments.csv`
- `settlements.csv`

Run the complete flow:
`upload → extraction → schema → canonicalization → planning → validation → execution → investigation → metrics → report → chat`.

Do not bypass intermediate architecture stages.

### 3. Reconciliation correctness
Verify:
- row order does not matter
- relationships come from the plan
- missing records are detected
- amount mismatches are detected
- tolerances work
- duplicates work
- date differences work
- metrics are exact
- evidence is preserved

### 4. Dynamic schema test
Make a copy of the sample data and rename columns, e.g.:
`order_id → order_reference`
`amount_paid → paid_amount`
`payment_date → txn_date`

The system should still reason about the fields. If it fails because of hardcoded names, fix the architecture.

### 5. Invalid AI output test
Force malformed planner output and verify:
`LLM → validator rejects → repair/retry → valid plan`.

Verify permanent failure is handled safely.

### 6. Security
Check:
- no secrets committed
- no arbitrary LLM-generated code execution
- invalid files rejected
- AI receives minimum necessary data
- logs avoid unnecessary sensitive data

### 7. Failure handling
Test:
- empty files
- malformed files
- unsupported files
- schema failures
- model timeout
- malformed model output
- unsupported operations
- backend failure
- chat failure

Users should see useful errors, not stack traces.

### 8. Performance
Look for:
- unnecessary model calls
- repeated parsing
- expensive loops
- whole-dataset LLM prompts
- blocking jobs

Keep bulk reconciliation deterministic.

### 9. Production hardening
Review:
- configuration
- typing
- modularity
- API validation
- database consistency
- provenance
- idempotency where appropriate
- model/prompt version tracking
- README
- error handling

Do not add infrastructure just to sound impressive.

## Demo Preparation

Create `/docs/demo-script.md`.

The 5-minute demo should be:

**0:00–0:30 — Problem**
Finance teams receive records from multiple systems that should agree, but often do not.

**0:30–1:00 — Product**
FinRecon understands uploaded datasets and dynamically creates a reconciliation plan.

**1:00–2:00 — Run**
Upload files and show processing.

**2:00–3:30 — Results**
Show match rate, mismatches, exceptions, and evidence.

**3:30–4:20 — AI investigation**
Open a difficult exception and ask why it was flagged.

**4:20–5:00 — Close**
Explain that the demo uses orders/payments/settlements but the underlying engine is schema-driven and can support other financial reconciliation workflows.

Do not claim capabilities that are not implemented.

## Final Acceptance Criteria
The project is ready only when:
- clean startup works
- end-to-end flow works
- sample datasets work
- frontend/backend contracts agree
- tests pass
- critical bugs are fixed
- README works
- demo script exists
- no obvious hardcoded reconciliation logic remains
- no fake metrics are displayed
- AI explanations are evidence-grounded

Create `/docs/final-qa-report.md` with tests, fixes, limitations, startup commands, and final demo path.

Fix problems rather than merely documenting them.
