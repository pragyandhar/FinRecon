# Context: AI Finance Ops Reconciliation Buildathon

## 1. Why this project matters

The project is being built for Razorpay's Buildathon.

The goal is to build a working finance-operations agent and submit a
project with a five-minute video pitch. If shortlisted, the project will
be evaluated by a technical panel.

The relevant track is the **AI Finance Controller** track.

The stated bar is:

> Build an agent that closes one finance ops loop across 50+ records of
> synthetic data, reporting its match rate and the exceptions it could
> not resolve.

This means the project must demonstrate more than a small AI demo or a
cherry-picked successful example.

The system should:

-   Process a batch of at least 50 records.
-   Work across multiple financial datasets or documents.
-   Determine which records match.
-   Identify mismatches and exceptions.
-   Report measurable results such as match rate.
-   Be honest about unresolved cases.
-   Keep enough traceability to explain why a result was produced.

The broader problem is automating repetitive finance-operations work
that is often performed manually using spreadsheets and reconciliation
workflows.

The project should aim toward production-quality engineering rather than
a purely flashy prototype.

------------------------------------------------------------------------

## 2. Core problem

Financial information can exist in multiple sources that describe the
same underlying business activity.

For example:

-   Orders
-   Payments
-   Settlements
-   Refunds
-   Other financial records

The same concept may have different names or structures across files.

The system therefore needs to understand unfamiliar input formats,
determine how datasets relate to one another, formulate reconciliation
logic, execute that logic across a batch, and explain exceptions.

The core mental model is:

**Understand → Standardize → Plan → Validate → Execute → Investigate →
Report**

------------------------------------------------------------------------

# 3. Complete architecture

## Step 1: Input and ingestion

The user uploads one or more files.

Supported inputs can include:

-   CSV
-   Excel
-   PDF
-   Other tabular financial documents where practical

The system should preserve the original files and raw data.

The ingestion layer extracts the usable records and document structure.

------------------------------------------------------------------------

## Step 2: SLM for document and schema understanding

An SLM analyzes the extracted data and determines what the datasets
contain.

It identifies things such as:

-   Dataset names
-   Column names
-   Data types
-   Likely primary keys
-   Likely foreign keys
-   Unique fields
-   Nullability
-   Sample values
-   Semantic meaning of fields
-   Potential relationships between datasets

The output is a structured **Schema JSON**.

Example:

``` json
{
  "datasets": [
    {
      "name": "payments",
      "fields": [
        {
          "name": "Txn ID",
          "type": "string",
          "semantic_type": "transaction_identifier"
        },
        {
          "name": "Amount Paid",
          "type": "number",
          "semantic_type": "payment_amount"
        }
      ]
    }
  ]
}
```

The SLM is not expected to reconcile transactions at this stage.

Its job is to understand the structure and meaning of the incoming data.

------------------------------------------------------------------------

# 4. Canonical schema

The system then creates a standardized internal representation.

A canonical schema provides a common vocabulary for downstream
components.

For example:

``` text
"Txn ID"
"Transaction Ref"
"Payment Reference"
"Payment No"
        ↓
payment_id
```

Similarly:

``` text
"Amount Paid"
"Paid Amount"
"Transaction Amount"
        ↓
payment_amount
```

The original files remain untouched.

The canonical schema is a mapping layer that allows downstream
components to work with consistent internal names even when incoming
files use different terminology.

The canonical schema should also preserve the mapping back to the
original dataset and column.

Example:

``` json
{
  "payments": {
    "payment_id": "Txn ID",
    "customer_id": "User Ref",
    "payment_amount": "Amount Paid"
  },
  "settlements": {
    "settlement_id": "Settlement Ref",
    "payment_id": "Transaction Ref",
    "settlement_amount": "Net Amount"
  }
}
```

The canonical schema answers:

**What data do we have, and what does each field represent?**

------------------------------------------------------------------------

# 5. LLM Rule-Making Agent

The canonical schema, dataset metadata, relevant statistics, and allowed
reconciliation operations are passed to an LLM.

The LLM acts as the **Rule-Making Agent**.

Its job is to determine:

-   Which datasets should be reconciled.
-   Which fields relate to each other.
-   Which keys should be used for joins.
-   Which comparisons should be performed.
-   What constitutes a match.
-   What constitutes a mismatch.
-   What constitutes an exception.
-   What tolerances or date windows are appropriate when justified.

The LLM does not directly execute the reconciliation.

It generates a structured **Reconciliation Plan JSON**.

Example:

``` json
{
  "joins": [
    {
      "dataset_a": "payments",
      "field_a": "payment_id",
      "dataset_b": "settlements",
      "field_b": "payment_id"
    }
  ],
  "checks": [
    {
      "operation": "TOLERANCE",
      "fields": [
        "payments.payment_amount",
        "settlements.settlement_amount"
      ],
      "tolerance": 10
    }
  ]
}
```

The plan should use only a controlled set of supported operations.

Possible operations include:

-   JOIN
-   COMPARE
-   EQUALS
-   NOT_EQUALS
-   TOLERANCE
-   MISSING
-   DUPLICATE
-   DATE_DIFF
-   DATE_WITHIN
-   SUM
-   COUNT
-   AGGREGATE

The exact operation vocabulary should be kept small and well-defined.

------------------------------------------------------------------------

# 6. Plan Validator

The Plan Validator sits between the Rule-Making LLM and the execution
layer.

It acts as a contract checker.

It verifies:

-   The JSON structure is valid.
-   The operation is supported.
-   Required parameters exist.
-   Referenced datasets exist.
-   Referenced fields exist.
-   Field types are compatible.
-   Required relationships exist.
-   Values such as tolerances are valid.
-   The plan does not contain unsupported instructions.

Each operation has a defined contract.

For example:

``` text
JOIN requires:
- dataset_a
- field_a
- dataset_b
- field_b

TOLERANCE requires:
- fields
- tolerance
```

If the plan is invalid, it should be rejected and sent back to the
Rule-Making Agent for regeneration or correction.

Only a validated plan reaches execution.

------------------------------------------------------------------------

# 7. Generic Execution Engine

The execution engine is normal code, not an LLM.

It is a generic interpreter for the supported reconciliation operations.

The important design principle is:

**Hardcode capabilities, not financial column names.**

The engine knows how to perform operations such as:

``` text
JOIN
COMPARE
EQUALS
TOLERANCE
MISSING
DUPLICATE
DATE_DIFF
DATE_WITHIN
AGGREGATE
```

It does not hardcode:

``` text
payment.amount
settlement.amount
order.amount
```

Those fields come dynamically from the validated reconciliation plan.

The engine interprets the plan and executes it against the actual data.

This makes it reusable across different datasets.

------------------------------------------------------------------------

# 8. LLM fallback for unsupported complexity

The generic execution engine will not be able to handle every possible
reconciliation instruction.

Therefore, the architecture can contain an LLM fallback.

The flow is:

``` text
Validated plan
      ↓
Can generic engine execute it?
      ↓
YES → Generic Execution Engine
      ↓
NO → LLM Executor
```

The LLM executor should be used only for cases that genuinely require
reasoning beyond the supported deterministic operations.

This creates two paths:

**Fast path:** deterministic execution.

**Complex path:** LLM reasoning.

This is an important cost and latency optimization.

------------------------------------------------------------------------

# 9. Reconciliation results

The execution stage produces structured results.

Each relevant record should receive a clear outcome such as:

-   MATCHED
-   MISMATCHED
-   EXCEPTION
-   UNRESOLVED

The system should preserve evidence for the decision.

Example:

``` text
Transaction: TX1023
Status: MISMATCHED

Payment amount: ₹1,000
Settlement amount: ₹950
Difference: ₹50
Rule applied: TOLERANCE
```

The system should never silently discard records.

------------------------------------------------------------------------

# 10. Exception Investigator

Exceptions can be passed to an SLM or LLM for deeper explanation.

The model should receive only the relevant context rather than the
entire dataset whenever possible.

For example:

``` text
Transaction
Related records
Rules applied
Observed values
Difference
Relevant metadata
```

It can answer:

-   Why was this transaction flagged?
-   Which records caused the exception?
-   What evidence supports the finding?
-   What is the likely reason?
-   What should a human check next?

This component is where natural-language reasoning provides the most
value.

------------------------------------------------------------------------

# 11. Report generation

The report should primarily be generated from structured results.

Basic metrics should be calculated by code, not guessed by an LLM.

Example:

``` text
Records processed: 100
Matched: 91
Mismatched: 6
Exceptions: 3
Match rate: 91%
```

The report can include:

-   Total records
-   Match rate
-   Mismatch count
-   Exception count
-   Exception categories
-   Exception explanations
-   Evidence
-   Processing information
-   Audit trail

The report can be displayed in the UI and exported as formats such as
PDF, CSV, or JSON.

------------------------------------------------------------------------

# 12. Contextual SLM chatbot

The UI contains a small temporary chat interface for questions about the
current report.

Example:

> Why was TX1023 flagged?

The SLM receives the relevant report and transaction context.

It should not need to process the entire dataset for every question.

The chat is contextual to the current report.

Closing the chat ends the temporary conversational state.

Opening it again starts a fresh session.

A reset control clears the current chat context.

------------------------------------------------------------------------

# 13. Cost and latency strategy

The architecture deliberately avoids using expensive LLM calls for every
record.

The intended pattern is:

``` text
SLM
→ schema understanding

LLM
→ one reconciliation plan

Code
→ bulk reconciliation

LLM/SLM
→ only complex or exceptional cases

Code
→ metrics and basic report generation

SLM
→ natural-language chat
```

The same reconciliation plan can be reused across the entire batch.

If the same or sufficiently similar schema appears again, the system can
cache and reuse the relevant schema mapping or reconciliation plan after
validation.

The goal is:

**Use AI where reasoning is required. Use code where computation is
predictable.**

------------------------------------------------------------------------

# 14. Observability and auditability

Every important stage should be traceable:

``` text
Original input
→ extracted schema
→ canonical schema
→ reconciliation plan
→ validation result
→ execution result
→ exception reasoning
→ final report
```

Tools such as LangSmith can be used for model tracing, evaluation, and
debugging.

The audit trail should make it possible to answer:

> Why did the system classify this record this way?

------------------------------------------------------------------------

# 15. Core design principles

1.  Unknown input formats should not require rewriting the whole system.
2.  Original data should remain untouched.
3.  AI should generate structured plans, not uncontrolled actions.
4.  Plans should be validated before execution.
5.  The execution engine should be generic.
6.  LLM calls should be limited to tasks that require reasoning.
7.  Basic arithmetic and metrics should be deterministic.
8.  Exceptions should be explicit rather than silently resolved.
9.  Every important decision should have traceable evidence.
10. The system should report its actual match rate honestly.

The central architecture is:

**Input → Extraction → SLM Schema Understanding → Canonical Schema → LLM
Rule-Making → Plan Validation → Generic Execution / LLM Fallback →
Reconciliation Results → Exception Investigation → Report → Contextual
Chat**
