# Agent 2 — AI / LLM Intelligence

## Mission
Own all AI-specific components:
- schema understanding
- semantic field interpretation
- canonical mapping
- reconciliation-plan generation
- plan repair
- complex fallback
- exception investigation
- contextual report chatbot

## Read First
Read:
- `/MASTER_PROMPT.md`
- `/docs/architecture.md`
- `/docs/contracts.md`
- existing backend interfaces

## Responsibilities

### 1. Schema understanding
Input:
- dataset names
- field names
- sample values
- inferred types
- null/uniqueness statistics
- relationship hints

Infer:
- dataset purpose
- field meaning
- identifier candidates
- primary/foreign-key candidates
- amount/currency/date/status fields
- relationships

Return structured Schema JSON.

### 2. Canonical mapping
Map different field names to stable semantic concepts without modifying raw data.

Example:
`Txn ID`, `Payment Reference`, `Gateway Ref` → `payment_id`.

Include confidence/evidence where useful.

### 3. Reconciliation planner
Use an LLM to create a structured `ReconciliationPlan` from:
- schema
- canonical mapping
- relationships
- statistics
- allowed operations
- execution constraints

The plan must use only supported operations and dynamically selected fields. Never assume the demo's exact columns.

### 4. Plan repair
When validation fails, send structured validation errors plus relevant schema back to the model and request a corrected plan. Enforce a finite retry count.

### 5. Complex fallback
Provide a constrained interface for genuinely unsupported operations. Give the model only relevant data and rules. Return structured output and `UNRESOLVED` when evidence is insufficient.

Never execute arbitrary generated code.

### 6. Exception investigator
Explain:
- what happened
- conflicting records
- relevant values
- rule applied
- likely cause
- evidence
- recommended human check
- confidence

Never invent evidence.

### 7. Contextual chat
Answer questions using only relevant report/result context rather than the entire dataset.

### 8. Model abstraction
Use a provider-independent interface such as:
`ModelClient`, `SLMClient`, `LLMClient`.

Keep model names/settings in configuration.

### 9. Reliability
Implement:
- structured output validation
- timeouts
- retries
- graceful failure
- confidence handling
- fallback

### 10. Cost discipline
Never use one LLM call per row.

Preferred:
`schema → SLM`
`plan → LLM`
`bulk execution → code`
`exceptions → AI`
`chat → SLM`

### 11. Tests
Test:
- alternate column names
- ambiguous fields
- valid plans
- invalid plans
- plan repair
- unsupported operations
- exception explanations
- malformed model output
- unresolved behavior

Use mock model clients for unit tests.

Create `/docs/integration-notes-ai.md` describing interfaces, prompts, schemas, configuration, fallback behavior, and tests.

Integrate with Agent 1's contracts.
