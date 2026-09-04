from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import (
    AggregateFunction,
    ComparisonType,
    FilterOperator,
    JoinType,
    OperationType,
)


class PlanStep(BaseModel):
    """One generic operation. Only `operation` selects behavior; every
    other field is a parameter consumed dynamically by the execution
    engine. Which fields are required for a given operation is defined
    by the contract table in app/validation/contracts.py, not by this
    model — this model stays permissive so a slightly-off LLM step can
    still be structurally parsed and then rejected with a precise error.
    """

    step_id: str
    operation: OperationType
    description: str | None = None

    # JOIN — left/right are dataset_ids or earlier step_ids.
    left: str | None = None
    right: str | None = None
    left_field: str | None = None
    right_field: str | None = None
    join_type: JoinType = JoinType.FULL_OUTER

    # COMPARE / MISSING / DUPLICATE — `input` is a dataset_id or step_id
    # (usually a JOIN result) this step reads from.
    input: str | None = None
    comparison: ComparisonType | None = None
    field_a: str | None = None
    field_b: str | None = None
    tolerance: float | None = None
    max_days: int | None = None
    side: str | None = None  # MISSING: "left" | "right"
    fields: list[str] | None = None  # DUPLICATE: key fields

    # FILTER
    field: str | None = None
    operator: FilterOperator | None = None
    value: Any = None

    # GROUP / AGGREGATE
    group_by: list[str] | None = None
    agg_function: AggregateFunction | None = None
    agg_field: str | None = None


class ReconciliationPlan(BaseModel):
    job_id: str
    plan_version: int = 1
    steps: list[PlanStep] = Field(default_factory=list)
