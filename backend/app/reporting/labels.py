"""Turns a plan step into a human-readable relationship label, e.g.
"Orders ↔ Payments", by tracing the step's input references back
through the plan to the raw datasets that ultimately feed it. Purely
derived from the plan the backend generated for this job — nothing
here is hardcoded to any specific dataset name.
"""

from app.models.enums import OperationType
from app.models.plan import PlanStep, ReconciliationPlan


def _resolve_dataset_ids(
    ref: str,
    steps_by_id: dict[str, PlanStep],
    dataset_ids: set[str],
    seen: set[str],
) -> list[str]:
    """Returns dataset_ids in the order the plan actually references
    them (left before right on a JOIN), deduplicated — not alphabetical,
    since alphabetical order can silently reverse what the plan says."""

    if ref in dataset_ids:
        return [ref]
    if ref in seen:
        return []  # guard against a malformed/cyclic plan
    seen.add(ref)

    step = steps_by_id.get(ref)
    if step is None:
        return []
    if step.operation == OperationType.JOIN:
        left = _resolve_dataset_ids(step.left, steps_by_id, dataset_ids, seen) if step.left else []
        right = _resolve_dataset_ids(step.right, steps_by_id, dataset_ids, seen) if step.right else []
        ordered = left + [d for d in right if d not in left]
        return ordered
    if step.input:
        return _resolve_dataset_ids(step.input, steps_by_id, dataset_ids, seen)
    return []


def _format_dataset_name(dataset_id: str) -> str:
    return dataset_id.replace("_", " ").replace("-", " ").title()


def describe_step_relationship(plan: ReconciliationPlan, step_id: str, dataset_ids: set[str]) -> str:
    """e.g. "Orders ↔ Payments" for a compare over a JOIN of those two
    datasets, or just "Payments" for a duplicate check on one dataset.
    Falls back to the raw step_id if the plan doesn't resolve cleanly
    (e.g. a step referencing a dataset that no longer exists) rather
    than guessing at a name."""

    steps_by_id = {s.step_id: s for s in plan.steps}
    step = steps_by_id.get(step_id)
    if step is None:
        return step_id

    if step.operation == OperationType.JOIN:
        resolved = _resolve_dataset_ids(step_id, steps_by_id, dataset_ids, set())
    elif step.input:
        resolved = _resolve_dataset_ids(step.input, steps_by_id, dataset_ids, set())
    else:
        resolved = []

    if not resolved:
        return step_id

    return " ↔ ".join(_format_dataset_name(d) for d in resolved)
