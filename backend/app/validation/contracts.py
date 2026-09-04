"""The operation contract table: the single authority for what each
PlanStep.operation requires. Used by the validator (to reject bad plans)
and by the planner prompt (to describe the format precisely) so the two
never drift apart.
"""

from app.models.enums import ComparisonType, OperationType
from app.models.plan import PlanStep

BASE_REQUIRED: dict[OperationType, list[str]] = {
    OperationType.JOIN: ["left", "right", "left_field", "right_field"],
    OperationType.COMPARE: ["input", "comparison", "field_a", "field_b"],
    OperationType.MISSING: ["input", "side"],
    OperationType.DUPLICATE: ["input", "fields"],
    OperationType.FILTER: ["input", "field", "operator", "value"],
    OperationType.GROUP: ["input", "group_by"],
    OperationType.AGGREGATE: ["input", "agg_function", "agg_field"],
}

DESCRIPTIONS: dict[OperationType, str] = {
    OperationType.JOIN: (
        "Join two datasets or step outputs on a field. `left`/`right` are "
        "dataset_ids or earlier step_ids; `left_field`/`right_field` are "
        "canonical field names. Produces a joined relation later steps can "
        "reference by this step's step_id."
    ),
    OperationType.COMPARE: (
        "Compare two canonical fields on every row of `input` (usually a "
        "JOIN result). `comparison` selects the check: EQUALS, NOT_EQUALS, "
        "TOLERANCE (requires numeric `tolerance`), DATE_DIFF or DATE_WITHIN "
        "(both require integer `max_days`). Produces MATCHED/MISMATCHED "
        "results."
    ),
    OperationType.MISSING: (
        "Flag rows in `input` (a JOIN result) that have no counterpart on "
        "`side` ('left' or 'right'). Produces EXCEPTION results."
    ),
    OperationType.DUPLICATE: (
        "Flag rows in `input` (a dataset_id or step_id) that repeat the "
        "same combination of `fields`. Produces EXCEPTION results for every "
        "row beyond the first in each duplicate group."
    ),
    OperationType.FILTER: (
        "Keep only rows in `input` where `field` `operator` `value` holds. "
        "Produces a filtered relation for later steps."
    ),
    OperationType.GROUP: (
        "Group `input` by `group_by` (list of canonical field names). "
        "Produces a grouped relation for a following AGGREGATE step."
    ),
    OperationType.AGGREGATE: (
        "Apply `agg_function` (SUM, COUNT, AVG) to `agg_field` over `input` "
        "(optionally already grouped by a preceding GROUP step, or pass "
        "`group_by` directly here). Produces summary rows, not per-record "
        "results."
    ),
}


def required_fields(step: PlanStep) -> list[str]:
    """Base + conditional required fields for this step's operation."""

    required = list(BASE_REQUIRED.get(step.operation, []))
    if step.operation == OperationType.COMPARE:
        if step.comparison == ComparisonType.TOLERANCE:
            required.append("tolerance")
        elif step.comparison in (ComparisonType.DATE_DIFF, ComparisonType.DATE_WITHIN):
            required.append("max_days")
    return required


def describe_operations() -> str:
    lines = []
    for op, desc in DESCRIPTIONS.items():
        required = ", ".join(BASE_REQUIRED[op])
        lines.append(f"- {op.value} (requires: {required}): {desc}")
    return "\n".join(lines)
