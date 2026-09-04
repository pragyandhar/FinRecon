# FinRecon — Complete System Architecture

## 1. Overview

FinRecon is an AI-powered financial reconciliation system designed to automate one finance-operations loop across multiple heterogeneous datasets such as orders, payments, and settlements.

The system accepts unfamiliar CSV, Excel, or PDF data, understands the structure and meaning of the data, creates a stable internal representation, determines how the datasets should be reconciled, validates the resulting plan, executes the reconciliation using deterministic code where possible, and uses AI only where reasoning is genuinely required.

### Core principle

> Use AI where reasoning is required. Use deterministic code where computation is predictable.

The architecture is intentionally hybrid:

- SLM for schema understanding and lightweight contextual interactions.
- LLM for reconciliation-plan generation and difficult reasoning.
- Deterministic code for validation, bulk comparison, aggregation, metrics, and reporting.
- LLM fallback for plans or cases that the deterministic engine cannot safely handle.

---

# 2. High-Level Flow

```text
                    ┌──────────────────────┐
                    │      User Upload      │
                    │ CSV / Excel / PDF     │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   File Validation    │
                    │ Type / Size / Safety  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Data Extraction    │
                    │ Tables / Rows / Text  │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Schema Understanding │
                    │        SLM           │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │  Canonical Schema    │
                    │ Field Meaning Map    │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │ Reconciliation Plan  │
                    │        LLM           │
                    └──────────┬───────────┘
                               │
                               ▼
                    ┌──────────────────────┐
                    │   Plan Validator     │
                    │ Schema / Types / Ops │
                    └──────────┬───────────┘
                               │
                         Valid │ Invalid
                               │
                  ┌────────────┴────────────┐
                  │                         │
                  ▼                         ▼
        ┌───────────────────┐      ┌───────────────────┐
        │ Generic Execution │      │ Plan Regeneration │
        │      Engine       │      │ / Error Handling  │
        └─────────┬─────────┘      └───────────────────┘
                  │
                  ▼
        ┌──────────────────────┐
        │ Reconciliation       │
        │ Results + Evidence   │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Exception Investigator│
        │    SLM / LLM         │
        └──────────┬───────────┘
                   │
                   ▼
        ┌──────────────────────┐
        │ Metrics + Report     │
        │ Audit Trail          │
        └──────────┬───────────┘
                   │
          ┌────────┴─────────┐
          ▼                  ▼
   ┌──────────────┐   ┌────────────────┐
   │ Report / UI  │   │ Contextual AI  │
   │ CSV / JSON   │   │ Chat Assistant │
   └──────────────┘   └────────────────┘
```

---

# 3. Main Components

## 3.1 File Upload Layer

### Responsibility

Accept user-provided financial data.

### Supported inputs

- CSV
- XLSX / Excel
- PDF

The upload layer should not assume a fixed schema.

For example, different organizations may provide:

```text
Transaction ID
Txn ID
Payment Reference
Payment Ref
Gateway Transaction ID
```

These may all represent the same business concept.

### Responsibilities

- Validate file extension and MIME type.
- Enforce file-size limits.
- Assign a unique upload/job ID.
- Store the original file immutably.
- Record metadata.
- Pass the file to the appropriate extractor.

### Important design decision

The original file must never be modified.

Raw input is preserved for auditability.

---

# 4. Data Extraction Layer

The extraction layer converts different file formats into a structured intermediate representation.

```text
CSV   ──────┐
Excel ──────┼──► Extraction Layer ───► Structured Tables
PDF   ──────┘
```

## CSV

Read rows and headers directly.

## Excel

Identify:

- worksheets
- headers
- tables
- rows
- merged/header regions where relevant

## PDF

PDFs require more intelligence because information may appear as:

- tables
- text
- multiple pages
- repeated headers
- irregular layouts

The extractor should preserve:

- source file
- page number
- table number
- row/column location where available
- original value

This creates provenance between the extracted representation and the source document.

---

# 5. Intermediate Data Representation

After extraction, every dataset should be represented internally in a common format.

Conceptually:

```json
{
  "dataset_id": "payments",
  "source_file": "payments.csv",
  "columns": [
    {
      "name": "amount_paid",
      "raw_type": "number"
    }
  ],
  "rows": [
    {
      "row_id": "payments_001",
      "values": {
        "amount_paid": 1000
      }
    }
  ]
}
```

The exact implementation can use typed Python objects, database tables, or another structured representation.

The important point is that downstream components do not need to understand CSV, Excel, or PDF internals.

---

# 6. Schema Understanding Layer

## Purpose

The system must understand what the uploaded data represents before attempting reconciliation.

An SLM is used here because this task is primarily structured semantic classification rather than deep open-ended reasoning.

### Inputs

The schema-understanding model receives:

- dataset names
- column names
- sample values
- inferred data types
- null rates
- uniqueness statistics
- basic distributions
- relationships that can be inferred from data

### It identifies

- dataset purpose
- field meaning
- data type
- candidate identifiers
- candidate primary keys
- candidate foreign keys
- unique fields
- possible relationships
- possible date fields
- amount/currency fields
- status fields

### Example

Input:

```text
payment_ref
amt_paid
txn_dt
cust_ref
```

The model may infer:

```text
payment_ref → payment_id
amt_paid    → payment_amount
txn_dt      → payment_date
cust_ref    → customer_id
```

The model should produce structured JSON rather than free-form text.

---

# 7. Schema JSON

The schema-understanding output describes what the system believes exists in the data.

Example:

```json
{
  "datasets": [
    {
      "dataset_id": "orders",
      "purpose": "order_records",
      "fields": [
        {
          "name": "order_id",
          "semantic_type": "identifier",
          "role": "primary_key"
        },
        {
          "name": "order_amount",
          "semantic_type": "currency_amount",
          "role": "measure"
        }
      ]
    }
  ]
}
```

This JSON is a machine-readable contract between schema understanding and the next stage.

---

# 8. Canonical Schema

## Why it exists

Different systems use different names for the same business concept.

The canonical schema gives FinRecon a stable internal vocabulary.

Example:

```text
Txn ID
Transaction Reference
Payment Reference
Gateway Reference
```

may map to:

```text
payment_id
```

Likewise:

```text
Amount Paid
Paid Amount
Transaction Amount
```

may map to:

```text
payment_amount
```

### Important distinction

The canonical schema does NOT rewrite the original files.

It is a semantic mapping layer.

```text
Raw Field Name
      │
      ▼
Semantic Meaning
      │
      ▼
Canonical Field
```

Example:

```text
"amt_paid"
     ↓
payment amount
     ↓
"payment_amount"
```

The original `"amt_paid"` remains available for provenance.

---

# 9. Reconciliation Planning Agent

Once the system understands the datasets, it needs to determine what reconciliation should actually be performed.

This is where the LLM is useful.

## Inputs

The planning LLM receives:

- Schema JSON
- Canonical schema
- dataset relationships
- field statistics
- data types
- uniqueness information
- available operations
- system constraints

It should NOT receive unnecessary raw data when the schema and metadata are sufficient.

## Output

A structured Reconciliation Plan JSON.

The plan answers:

> What should the system do with this data?

---

# 10. Reconciliation Plan

Example:

```json
{
  "steps": [
    {
      "operation": "JOIN",
      "left_dataset": "orders",
      "right_dataset": "payments",
      "fields": ["order_id"]
    },
    {
      "operation": "COMPARE",
      "fields": ["order_amount", "amount_paid"],
      "comparison": "TOLERANCE",
      "tolerance": 0.01
    },
    {
      "operation": "CHECK",
      "condition": "MISSING"
    }
  ]
}
```

The exact plan format can evolve, but it should remain structured and constrained.

---

# 11. Generic Operation Vocabulary

The execution engine should understand generic capabilities rather than finance-specific column names.

Possible operations include:

```text
JOIN
COMPARE
EQUALS
NOT_EQUALS
TOLERANCE
MISSING
DUPLICATE
DATE_DIFF
DATE_WITHIN
SUM
COUNT
AGGREGATE
FILTER
GROUP
```

The engine hardcodes the meaning of these operations.

It does NOT hardcode:

```text
order_amount
amount_paid
payment_reference
settled_amount
```

Those values come dynamically from the reconciliation plan.

### Key architectural principle

> Hardcode capabilities, not financial schemas.

---

# 12. Plan Validator

The LLM is probabilistic, so its output must never be trusted blindly.

The Plan Validator sits between the LLM and the execution engine.

```text
LLM Plan
   │
   ▼
Plan Validator
   │
   ├── Valid ──────► Execution Engine
   │
   └── Invalid ───► Regenerate / Fail Safely
```

## Validation responsibilities

### Structural validation

Check:

- valid JSON
- required fields
- correct data types
- correct operation names

### Semantic validation

Check:

- dataset exists
- field exists
- operation is supported
- fields are compatible with operation
- numeric tolerance is valid
- join fields have compatible types
- required parameters are present

### Execution compatibility

The validator should ensure the plan contains everything the execution engine needs.

This prevents runtime failures caused by incomplete LLM output.

---

# 13. Plan Regeneration

If the plan is invalid:

```text
Invalid Plan
     │
     ▼
Validation Error
     │
     ▼
LLM receives structured error
     │
     ▼
Corrected Plan
     │
     ▼
Validator
```

A maximum retry count should be enforced.

The system must not enter an infinite regeneration loop.

If the plan remains invalid, the job should fail safely and explain the problem.

---

# 14. Generic Execution Engine

The execution engine is the deterministic core of FinRecon.

It interprets the validated plan and executes the requested operations.

## Responsibilities

- joins
- comparisons
- tolerance calculations
- missing-record detection
- duplicate detection
- date comparisons
- aggregations
- filtering
- grouping
- result generation

Example:

```text
Plan says:

JOIN payments ↔ settlements
using payment_id

Then:

COMPARE
amount_paid ↔ settled_amount
with tolerance = X
```

The engine dynamically resolves those fields.

It does not need to know beforehand that one dataset is called `payments` or that one field is called `amount_paid`.

---

# 15. Why the Execution Engine Is Not Hardcoded

There is an important distinction between hardcoding a schema and hardcoding an execution capability.

Bad design:

```text
if column == "amount_paid":
    compare_with("settled_amount")
```

This only works for one schema.

Better design:

```text
execute(plan)
```

where the plan contains:

```text
left_field = dynamically selected field
right_field = dynamically selected field
operation = COMPARE
```

The engine knows how `COMPARE` works, but not which financial fields will be compared.

Therefore:

```text
New Dataset
    ↓
Schema Understanding
    ↓
Canonical Mapping
    ↓
New Plan
    ↓
Same Generic Engine
```

---

# 16. Deterministic Fast Path

Most reconciliation work should be performed without an LLM.

For example:

```text
100,000 records
      ↓
JOIN
      ↓
COMPARE
      ↓
TOLERANCE
      ↓
MATCH / MISMATCH
```

This should happen in normal application code.

Advantages:

- low latency
- low cost
- deterministic behavior
- reproducibility
- easier testing
- easier auditing

---

# 17. LLM Fallback Executor

Not every possible reconciliation rule will necessarily be supported by the deterministic engine.

If a validated plan contains a genuinely complex operation that the engine cannot execute safely:

```text
Validated Plan
      │
      ▼
Can deterministic engine execute it?
      │
  ┌───┴────┐
 Yes       No
  │         │
  ▼         ▼
Execute   LLM Fallback
            │
            ▼
        Structured Result
```

The fallback should be constrained.

It should receive only the relevant data and instructions needed for the specific operation.

It should not be allowed to execute arbitrary generated code against the system.

---

# 18. Reconciliation Result Model

Each evaluated record should produce a structured result.

Example:

```json
{
  "record_id": "order_1023",
  "status": "MISMATCHED",
  "checks": [
    {
      "field": "amount",
      "expected": 1000,
      "actual": 980,
      "result": "NOT_EQUAL"
    }
  ],
  "evidence": {
    "orders_row": "orders_1023",
    "payments_row": "payments_8451"
  }
}
```

Possible statuses:

```text
MATCHED
MISMATCHED
EXCEPTION
UNRESOLVED
```

---

# 19. Exception Investigator

Bulk reconciliation identifies records.

It should not require an LLM to reason about every record.

Instead, AI is used selectively for exceptions.

```text
All Records
     │
     ▼
Deterministic Reconciliation
     │
     ├── MATCHED ───────────► Final Results
     │
     ├── MISMATCHED ────────► Final Results
     │
     └── EXCEPTION ─────────► Exception Investigator
```

## Inputs

The investigator receives:

- relevant records
- reconciliation rule
- observed values
- expected values
- related records
- dates
- statuses
- evidence
- confidence information

## Output

For example:

```json
{
  "reason": "Settlement amount differs from payment amount.",
  "evidence": [
    "Payment amount = 1000",
    "Settlement amount = 980",
    "Processing fee = 20"
  ],
  "likely_cause": "Processing fee deduction",
  "recommended_action": "Verify settlement fee configuration."
}
```

The model explains the result; it should not invent evidence.

---

# 20. Confidence and Unresolved Cases

The system should distinguish between:

- deterministic certainty
- high-confidence AI reasoning
- ambiguous reasoning
- unresolved cases

If evidence is insufficient, the correct output is:

```text
UNRESOLVED
```

rather than a fabricated explanation.

This is particularly important in financial workflows.

---

# 21. Metrics Engine

Core metrics must be calculated using deterministic code.

The LLM should never be responsible for counting records or calculating the match rate.

Example:

```text
Total records       = 100
Matched             = 82
Mismatched          = 11
Exceptions          = 5
Unresolved          = 2

Match Rate = 82 / 100 = 82%
```

Other useful metrics:

- mismatch rate
- exception rate
- unresolved rate
- duplicate count
- missing-record count
- amount variance
- processing latency
- AI invocation count
- estimated AI cost

---

# 22. Final Report

The reporting layer combines:

```text
Execution Results
       +
Exception Analysis
       +
Deterministic Metrics
       +
Audit Information
```

The report should include:

### Summary

- records processed
- match rate
- mismatches
- exceptions
- unresolved cases

### Breakdown

- mismatch categories
- missing records
- duplicates
- amount differences
- date differences
- status inconsistencies

### Evidence

For each exception:

- source records
- relevant fields
- rule applied
- observed values
- reason
- confidence
- recommended next action

---

# 23. Audit Trail and Provenance

Financial systems need traceability.

Every result should be traceable through the pipeline:

```text
Original File
    ↓
Extracted Row
    ↓
Schema Interpretation
    ↓
Canonical Mapping
    ↓
Reconciliation Plan
    ↓
Validated Plan
    ↓
Execution Result
    ↓
Exception Reasoning
    ↓
Final Report
```

The system should preserve identifiers linking each stage.

This allows a reviewer to answer:

> Why did FinRecon mark this record as an exception?

without relying on a black-box final answer.

---

# 24. Contextual AI Chatbot

The report UI can provide a small contextual AI assistant.

Example user questions:

```text
Why was TX1023 flagged?

Which settlements have the largest variance?

Why is this record unresolved?

What percentage of payments matched?
```

The chatbot should receive the relevant report context rather than the entire dataset.

Example:

```text
User asks:
"Why was TX1023 flagged?"

      ↓

Retrieve TX1023 result
      ↓
Retrieve its evidence
      ↓
Send only relevant context to SLM
      ↓
Generate explanation
```

This keeps the interaction:

- fast
- cheap
- focused
- privacy-conscious

The chat session should be temporary and contextual to the current report.

---

# 25. Chat Session Lifecycle

A practical behavior is:

```text
Open Report
    ↓
Open AI Assistant
    ↓
Temporary conversation context
    ↓
Ask questions
    ↓
Close assistant
    ↓
Session ends
```

Reopening can start a fresh session.

A reset action should explicitly clear the current conversational context.

---

# 26. Data Storage

A production-oriented implementation can separate storage into logical layers.

## Raw Storage

Stores original uploaded files.

```text
raw_files
```

Original data is immutable.

## Structured Data

Stores extracted tables/rows.

```text
datasets
dataset_rows
```

## Metadata

Stores:

```text
jobs
schemas
canonical_mappings
reconciliation_plans
validation_results
```

## Results

Stores:

```text
reconciliation_results
exceptions
reports
```

## Audit

Stores:

```text
execution_events
model_calls
plan_versions
result_provenance
```

The exact database technology can vary. PostgreSQL is a reasonable production choice for metadata, plans, results, and audit records, while object storage can hold original files.

---

# 27. Job-Based Processing

Reconciliation should be treated as a job.

Example:

```text
POST /reconciliation/jobs
        ↓
Create job
        ↓
Store upload
        ↓
Process asynchronously
        ↓
Update job status
        ↓
Generate report
```

Possible job states:

```text
UPLOADED
EXTRACTING
UNDERSTANDING_SCHEMA
PLANNING
VALIDATING_PLAN
RECONCILING
INVESTIGATING
GENERATING_REPORT
COMPLETED
FAILED
```

This makes long-running jobs manageable and observable.

---

# 28. API Layer

Possible API boundaries:

```text
POST   /uploads
POST   /reconciliation/jobs
GET    /reconciliation/jobs/{id}
GET    /reconciliation/jobs/{id}/results
GET    /reconciliation/jobs/{id}/exceptions
GET    /reconciliation/jobs/{id}/report
POST   /reconciliation/jobs/{id}/chat
```

The frontend should not directly control reconciliation logic.

The backend owns:

- validation
- schema processing
- planning
- execution
- results
- auditability

---

# 29. Frontend Flow

A simple UI can follow this sequence:

```text
Upload Files
     ↓
Processing
     ↓
Detected Datasets
     ↓
Reconciliation Summary
     ↓
Match Rate
     ↓
Exception List
     ↓
Exception Details
     ↓
AI Explanation
```

The main dashboard should make the most important result immediately visible:

```text
Match Rate: 82%

Matched:       82
Mismatched:    11
Exceptions:     5
Unresolved:     2
```

---

# 30. Error Handling

Every stage should fail explicitly.

Examples:

### Unsupported file

```text
UNSUPPORTED_FILE_TYPE
```

### Extraction failure

```text
EXTRACTION_FAILED
```

### Schema uncertainty

```text
SCHEMA_UNCERTAIN
```

### Invalid plan

```text
INVALID_RECONCILIATION_PLAN
```

### Unsupported operation

```text
UNSUPPORTED_OPERATION
```

### LLM failure

```text
MODEL_EXECUTION_FAILED
```

### Insufficient evidence

```text
UNRESOLVED_EXCEPTION
```

Errors should contain actionable diagnostic information without leaking sensitive data.

---

# 31. LLM Safety Boundary

LLMs should never be given unrestricted control of the application.

The architecture enforces:

```text
LLM
 ↓
Structured JSON
 ↓
Schema Validation
 ↓
Plan Validation
 ↓
Allowed Operations
 ↓
Deterministic Execution
```

The LLM should not be allowed to:

- execute arbitrary Python
- execute arbitrary SQL
- modify raw files
- modify financial records
- bypass validation
- access unrelated datasets

This makes the AI component controllable and auditable.

---

# 32. Cost and Latency Architecture

The system deliberately avoids an LLM call for every row.

Bad approach:

```text
100,000 rows
    ↓
100,000 LLM calls
```

This would be expensive and slow.

Preferred approach:

```text
1 SLM call
    → understand schema

1 LLM call
    → create reconciliation plan

Deterministic engine
    → process bulk records

Only exceptions/complex cases
    → AI reasoning
```

This gives a strong balance between intelligence and performance.

---

# 33. Model Routing

A simple model strategy:

| Task | Preferred Component |
|---|---|
| Schema understanding | SLM |
| Canonical mapping | SLM / deterministic validation |
| Reconciliation planning | LLM |
| Plan validation | Code |
| Bulk reconciliation | Code |
| Complex unsupported operation | LLM |
| Exception explanation | SLM/LLM |
| Metrics | Code |
| Report calculations | Code |
| Contextual chatbot | SLM |

The exact models can be changed through configuration.

The application should avoid tightly coupling business logic to one model provider.

---

# 34. Model Abstraction

Instead of scattering provider-specific calls throughout the codebase, use an abstraction such as:

```text
ModelClient
    ├── SLMClient
    └── LLMClient
```

The rest of the application should request capabilities rather than directly depend on a particular provider.

This makes:

- model replacement easier
- testing easier
- cost optimization easier
- provider migration easier

---

# 35. Configuration

Model names, limits, tolerances, retry counts, and feature flags should be configuration-driven.

Examples:

```text
SCHEMA_MODEL
PLANNER_MODEL
EXCEPTION_MODEL

MAX_FILE_SIZE
MAX_PLAN_RETRIES
DEFAULT_AMOUNT_TOLERANCE

ENABLE_LLM_FALLBACK
ENABLE_CHAT
```

Do not hardcode environment-specific configuration into business logic.

---

# 36. Observability

The system should expose enough information to understand what happened during every job.

Track:

- job ID
- stage
- duration
- model used
- token usage
- estimated cost
- retries
- validation failures
- execution failures
- exception count
- unresolved count

LLM traces can be integrated with a tracing/evaluation platform such as LangSmith.

A trace should make it possible to inspect:

```text
Job
 ├── Extraction
 ├── Schema call
 ├── Planning call
 ├── Plan validation
 ├── Execution
 ├── Exception investigation
 └── Report generation
```

---

# 37. Evaluation

The system should not be evaluated only by whether it produces a report.

Important evaluation metrics include:

## Reconciliation accuracy

- true matches
- false matches
- true mismatches
- false mismatches

## Exception quality

- correct exception classification
- explanation accuracy
- unsupported claims
- unresolved rate

## System performance

- end-to-end latency
- extraction latency
- planning latency
- execution throughput

## AI efficiency

- model calls per job
- tokens used
- estimated cost

A particularly important metric is the rate of incorrect matches because a false financial match can be more dangerous than an unresolved record.

---

# 38. Testing Strategy

Testing should exist at multiple levels.

## Unit tests

Test individual operations:

```text
JOIN
COMPARE
TOLERANCE
MISSING
DUPLICATE
DATE_DIFF
```

## Validator tests

Test:

- missing fields
- invalid operations
- invalid datasets
- incompatible types
- malformed JSON
- invalid tolerance

## Integration tests

Run:

```text
Upload
 → Extract
 → Understand
 → Plan
 → Validate
 → Execute
 → Report
```

## AI evaluation tests

Use representative datasets to test:

- schema interpretation
- canonical mapping
- plan quality
- exception reasoning

## Adversarial tests

Test:

- different column names
- different column ordering
- missing columns
- null values
- duplicate records
- date format differences
- amount precision differences
- currency differences
- unfamiliar schemas
- malformed model output
- unsupported operations

---

# 39. Security

Financial data can be sensitive.

The system should implement:

- authentication
- authorization
- encrypted transport
- encrypted storage where appropriate
- strict file validation
- isolated processing
- limited model context
- secrets stored outside source code
- structured logging without sensitive raw data
- retention/deletion policies

Raw financial records should not be unnecessarily sent to external model providers.

Use minimum necessary context.

---

# 40. Idempotency

A reconciliation job should have an idempotent job identifier.

If the same processing request is accidentally submitted twice, the system should avoid unintended duplicate processing where possible.

This matters especially in production workflows and retries.

---

# 41. Immutability

Raw input should be immutable.

Instead of:

```text
raw file
  ↓
modify raw data
```

use:

```text
raw file
  ↓
extracted representation
  ↓
normalized/canonical representation
  ↓
reconciliation results
```

Every transformation remains traceable.

---

# 42. Versioning

Important AI-generated artifacts should be versioned.

For example:

```text
schema_version
canonical_schema_version
plan_version
model_version
prompt_version
```

If a result is questioned later, the system should be able to determine which model and plan produced it.

---

# 43. End-to-End Example

Suppose the user uploads:

```text
orders.csv
payments.csv
settlements.csv
```

### Step 1 — Upload

Files are stored and assigned a reconciliation job ID.

### Step 2 — Extraction

The system extracts the tables.

### Step 3 — Schema understanding

The SLM determines:

```text
orders
payments
settlements
```

and identifies important fields.

### Step 4 — Canonical mapping

The system maps different names to stable concepts.

For example:

```text
order_id
payment.order_id
settlement.payment_reference
```

may represent linked identifiers.

### Step 5 — Planning

The LLM determines that the datasets can be reconciled through relationships such as:

```text
orders → payments → settlements
```

and creates a structured plan.

### Step 6 — Validation

The validator checks every dataset, field, operation, and parameter.

### Step 7 — Execution

The generic engine performs the bulk joins and comparisons.

### Step 8 — Results

Records are classified:

```text
MATCHED
MISMATCHED
EXCEPTION
UNRESOLVED
```

### Step 9 — Investigation

AI examines only the exceptions requiring reasoning.

### Step 10 — Metrics

Code calculates the exact match rate and other counts.

### Step 11 — Report

The dashboard presents the reconciliation result and evidence.

### Step 12 — Chat

The user can ask:

```text
Why was this transaction flagged?
```

The assistant uses only the relevant report context.

---

# 44. Separation of Responsibilities

A clean implementation should maintain these boundaries:

```text
Extraction
    → understands file formats

Schema Understanding
    → understands data meaning

Canonical Mapping
    → creates stable vocabulary

Planner
    → decides what operations should happen

Validator
    → verifies the plan

Execution Engine
    → performs operations

Exception Investigator
    → explains difficult cases

Metrics Engine
    → calculates exact statistics

Report Generator
    → presents results

Chat Assistant
    → answers contextual questions
```

No component should silently take over another component's responsibilities.

---

# 45. Recommended Project Structure

A possible backend structure:

```text
fin-recon/
│
├── app/
│   ├── api/
│   ├── core/
│   ├── models/
│   ├── schemas/
│   │
│   ├── ingestion/
│   │   ├── csv/
│   │   ├── excel/
│   │   └── pdf/
│   │
│   ├── schema_understanding/
│   ├── canonicalization/
│   ├── planning/
│   ├── validation/
│   ├── execution/
│   ├── investigation/
│   ├── reporting/
│   ├── chat/
│   ├── storage/
│   └── observability/
│
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── evaluation/
│   └── fixtures/
│
├── frontend/
│
├── configs/
│
├── scripts/
│
├── docs/
│
├── .env.example
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

The exact structure can change as implementation evolves. The important goal is separation of concerns.

---

# 46. Architectural Decision Summary

| Decision | Reason |
|---|---|
| Support heterogeneous files | Real finance workflows use different formats |
| Preserve raw input | Auditability |
| Schema understanding before reconciliation | Avoid hardcoded schemas |
| Canonical schema | Stable internal vocabulary |
| LLM-generated plan | Dynamic reconciliation logic |
| Plan validator | Prevent unsafe/invalid execution |
| Generic execution engine | Reusable across schemas |
| Deterministic bulk processing | Speed, cost, reliability |
| LLM fallback | Handle genuinely complex cases |
| AI only for exceptions | Reduce cost and latency |
| Code-based metrics | Exact results |
| Provenance | Explainability and audit |
| Temporary contextual chatbot | Useful investigation without unnecessary context |
| Versioned AI artifacts | Reproducibility |
| Observability | Debugging and production readiness |

---

# 47. Core Design Philosophy

FinRecon is not simply:

```text
Upload file → ask LLM → get answer
```

It is a controlled AI system:

```text
Understand
    ↓
Normalize
    ↓
Plan
    ↓
Validate
    ↓
Execute
    ↓
Investigate
    ↓
Measure
    ↓
Report
```

The LLM is a reasoning component inside the system—not the system itself.

That distinction is central to making FinRecon scalable, testable, cost-efficient, auditable, and defensible as a production-oriented engineering project.
