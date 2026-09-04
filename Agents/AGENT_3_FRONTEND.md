# Agent 3 — Frontend & UX

## Mission
Build the real FinRecon frontend connected to the backend. The user must be able to complete the entire reconciliation workflow without touching code.

## Read First
Read:
- `/MASTER_PROMPT.md`
- `/docs/architecture.md`
- `/docs/contracts.md`
- backend API code and documentation

## Main Journey
```text
Open FinRecon
→ Upload files
→ See detected datasets
→ Start reconciliation
→ See processing stages
→ See results
→ Inspect mismatch/exception
→ See evidence
→ Ask AI why
→ View/download report
```

## Responsibilities

### Upload
Support multiple files. Show:
- filename
- file type
- validation
- upload state
- processing state

Do not hardcode dataset names into the UI.

### Processing
Show real backend job states where available:
`uploaded`, `extracting`, `understanding_schema`, `planning`, `validating_plan`, `reconciling`, `investigating`, `reporting`, `completed`, `failed`.

Do not fake progress.

### Dashboard
Immediately show:
- match rate
- matched
- mismatched
- exceptions
- unresolved
- useful variance/missing/duplicate summaries

### Results
Create searchable/filterable results with:
`All`, `Matched`, `Mismatched`, `Exception`, `Unresolved`.

### Exception detail
Show:
- source records
- relevant fields
- expected/actual values
- rule
- evidence
- AI explanation
- likely cause
- recommended next check
- confidence

Clearly distinguish deterministic facts from AI reasoning.

### Chat
Provide a contextual assistant with questions such as:
- Why was this transaction flagged?
- What caused this mismatch?
- Which records have the largest variance?
- Show unresolved cases.

Use the current reconciliation job context.

### UX
Prioritize:
- clarity
- professional fintech feel
- responsive layout
- accessibility
- useful loading/error/empty states
- low visual clutter

### Demo
Make this path extremely smooth:
`Upload files → Start → processing → summary → open mismatch → evidence → ask AI → report`.

### Quality
Use reusable components and proper state management. Never hardcode reconciliation results. Display backend data.

Create `/docs/integration-notes-frontend.md` with routes, API dependencies, configuration, components, demo flow, and limitations.

Test the frontend against the real backend.
