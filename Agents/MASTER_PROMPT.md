# FinRecon — Master Team Prompt

## Mission
Build the complete FinRecon project autonomously as a production-oriented AI financial reconciliation platform for the Razorpay Buildathon.

The user should ultimately only need to start the application, upload the supplied datasets, run reconciliation, inspect exceptions, ask the contextual AI assistant questions, and record a polished 5-minute demo.

Do not repeatedly ask the user what to do next. Make reasonable engineering decisions, implement them, test them, fix failures, and continue.

## Product
FinRecon is a general financial reconciliation platform. The demo uses Orders, Payments, and Settlements, but the reconciliation engine must NOT hardcode those exact schemas.

The same architecture should support scenarios such as:
- gateway transactions vs bank statements
- internal ledger vs bank statements
- merchant payouts vs settlements
- refunds vs payments
- chargebacks vs transactions
- UPI/card/network records vs internal records
- tax records vs transaction records

## Required Architecture
```text
Upload CSV / Excel / PDF
        ↓
File validation
        ↓
Data extraction
        ↓
Schema understanding (SLM)
        ↓
Canonical semantic mapping
        ↓
Reconciliation plan generation (LLM)
        ↓
Plan validation
        ↓
Generic deterministic execution engine
        ↓
LLM fallback for genuinely unsupported complex cases
        ↓
Reconciliation results + evidence
        ↓
AI exception investigation
        ↓
Deterministic metrics
        ↓
Report/dashboard
        ↓
Contextual AI chat
```

## Non-Negotiable Rules

### Do not hardcode the demo schema
Never write logic like:
```python
if column == "amount_paid":
    compare_with("settled_amount")
```

The execution engine must consume a validated dynamic plan.

Supported generic operations should include, where useful:
`JOIN`, `COMPARE`, `EQUALS`, `NOT_EQUALS`, `TOLERANCE`, `MISSING`, `DUPLICATE`, `DATE_DIFF`, `DATE_WITHIN`, `SUM`, `COUNT`, `FILTER`, `GROUP`, `AGGREGATE`.

**Hardcode capabilities, not financial field names.**

### AI must produce structured output
Use typed schemas / JSON validation. Never directly execute arbitrary LLM-generated code.

### Validate before execution
Every LLM-generated reconciliation plan must pass structural and semantic validation.

### Use deterministic code for predictable work
Use code for joins, calculations, comparisons, aggregations, counts, percentages, and metrics. Use AI for schema interpretation, planning, difficult reasoning, exception explanations, and contextual chat.

### Preserve evidence
Every result must point to the relevant source records, fields, and rule.

### Never fabricate
If evidence is insufficient, return `UNRESOLVED`.

### Preserve raw input
Uploaded source files are immutable.

## Four Agents
1. **Agent 1 — Backend & Data Pipeline**
2. **Agent 2 — AI / LLM Intelligence**
3. **Agent 3 — Frontend & UX**
4. **Agent 4 — QA, Integration, Demo & Production Hardening**

## Shared Documentation
Maintain:
```text
/docs/architecture.md
/docs/contracts.md
/docs/decisions.md
/docs/integration-notes.md
```

`/docs/contracts.md` is the single source of truth for interfaces between agents. It must define structured representations for:
- extracted datasets
- schema
- canonical mapping
- reconciliation plan
- validation result
- reconciliation result
- exception
- report
- chat

If a contract changes:
1. Update `contracts.md`.
2. Document the decision in `decisions.md`.
3. Update affected code.
4. Run tests.

## Working Rules
- Inspect the existing repository before changing anything.
- Integrate with existing work instead of replacing it unnecessarily.
- Never delete another agent's work merely because you prefer a different implementation.
- If parallel branches/worktrees are available, use them. Otherwise work sequentially.
- Communicate through repository docs and code contracts.
- Keep business logic separate from API/UI code.
- Do not stop at a skeleton. Implement the actual flow.

## External AI Dependency
If model credentials or external services are unavailable:
- keep a clean model abstraction;
- provide a documented local/demo implementation where appropriate;
- keep production integration ready;
- do not replace the architecture with hardcoded demo results.

## Definition of Done
The final repository must have:
- working CSV upload
- Excel/PDF support where implemented
- dynamic schema understanding
- canonical mapping
- dynamic reconciliation plan
- plan validation
- generic reconciliation engine
- matched/mismatched/exception/unresolved results
- evidence/provenance
- AI exception investigation
- exact deterministic metrics
- dashboard
- contextual AI chat
- working supplied datasets
- tests for critical operations
- clear setup instructions
- no secrets committed
- no hardcoded demo-only reconciliation logic
- clean error handling
- demo-ready UX

## Priority
1. End-to-end working product
2. Correct reconciliation
3. Clean architecture
4. Dynamic schema/plan behavior
5. Evidence and explainability
6. UX
7. Tests
8. Performance/cost
9. Extra features

**Build the project. Do not merely describe what should be built.**
