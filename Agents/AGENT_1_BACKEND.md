# Agent 1 — Backend & Data Pipeline

## Mission
Own the backend foundation, ingestion, extraction, storage, APIs, domain models, metrics, and generic reconciliation execution engine.

## Read First
Read:
- `/MASTER_PROMPT.md`
- `/docs/architecture.md`
- `/docs/contracts.md`
- existing repository code

## Responsibilities

### 1. Backend foundation
Build or improve:
- backend application
- configuration management
- environment handling
- logging
- error handling
- typed domain models
- API structure

Keep API, service, domain, and infrastructure responsibilities separated.

### 2. File ingestion
Support CSV, XLSX where practical, and PDF table extraction where practical.

Create a common extractor interface so downstream code does not care about the file format.

Preserve provenance:
- source file
- dataset ID
- row ID
- sheet/page/table information where available
- original values

### 3. Internal models
Create typed models for:
- Dataset
- Field
- Row
- Schema
- Canonical mapping
- Reconciliation plan
- Validation result
- Reconciliation result
- Exception
- Report

Align them with `/docs/contracts.md`.

### 4. Generic execution engine
Implement a plan interpreter such as:
```text
execute(plan, datasets)
```

Support generic operations where useful:
`JOIN`, `COMPARE`, `EQUALS`, `NOT_EQUALS`, `TOLERANCE`, `MISSING`, `DUPLICATE`, `DATE_DIFF`, `DATE_WITHIN`, `FILTER`, `GROUP`, `SUM`, `COUNT`, `AGGREGATE`.

The engine must dynamically resolve dataset IDs and field names from the validated plan.

Never hardcode:
`orders.order_amount -> payments.amount_paid -> settlements.settled_amount`.

### 5. Results and evidence
Each result should contain:
- source record IDs
- rule applied
- relevant fields
- expected/observed values
- comparison outcome
- final status

Statuses:
`MATCHED`, `MISMATCHED`, `EXCEPTION`, `UNRESOLVED`.

### 6. Metrics
Calculate in code:
- total
- matched
- mismatched
- exceptions
- unresolved
- match rate
- mismatch rate
- exception rate
- variance summaries

Never ask an LLM to calculate these.

### 7. APIs
Expose clean endpoints for:
- upload
- create reconciliation job
- job status
- results
- exceptions
- report
- contextual chat

### 8. Storage
Use a simple production-oriented design. Local/object storage for originals and a relational DB for metadata/results is acceptable. Do not over-engineer.

### 9. Tests
Test:
- exact matches
- amount mismatches
- tolerance
- missing records
- duplicates
- date differences
- reordered rows
- null values
- multiple datasets
- invalid plans
- unsupported operations

## Integration
Agent 2 provides AI outputs; consume them through shared contracts.
Agent 3 consumes your APIs.
Agent 4 validates the complete system.

Create `/docs/integration-notes-backend.md` containing implemented components, API endpoints, contracts, tests, assumptions, and limitations.

Run the backend tests and fix failures before handoff.
