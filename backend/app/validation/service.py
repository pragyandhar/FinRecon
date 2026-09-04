from app.models.enums import ComparisonType, FilterOperator, OperationType
from app.models.plan import PlanStep, ReconciliationPlan
from app.models.schema import CanonicalMapping
from app.models.validation import ValidationIssue, ValidationResult
from app.validation.contracts import required_fields


def _canonical_fields(ref: str, dataset_ids: set[str], canonical_mapping: CanonicalMapping) -> set[str] | None:
    """None means `ref` is a step_id (a derived relation), whose field
    set we can't statically know — skip field-existence checks for it
    rather than guessing."""

    if ref not in dataset_ids:
        return None
    return set(canonical_mapping.mapping.get(ref, {}).keys())


def validate_plan(
    plan: ReconciliationPlan, canonical_mapping: CanonicalMapping, dataset_ids: set[str]
) -> ValidationResult:
    issues: list[ValidationIssue] = []
    known_refs: set[str] = set(dataset_ids)
    seen_step_ids: set[str] = set()

    for step in plan.steps:
        if not step.step_id:
            issues.append(ValidationIssue(message="step is missing step_id"))
            continue
        if step.step_id in seen_step_ids:
            issues.append(ValidationIssue(step_id=step.step_id, message="duplicate step_id"))
        seen_step_ids.add(step.step_id)

        for missing in required_fields(step):
            if getattr(step, missing, None) in (None, "", []):
                issues.append(
                    ValidationIssue(step_id=step.step_id, field=missing, message=f"'{missing}' is required for {step.operation}")
                )

        _check_operation_semantics(step, known_refs, dataset_ids, canonical_mapping, issues)

        if step.operation in (OperationType.JOIN, OperationType.FILTER, OperationType.GROUP, OperationType.AGGREGATE):
            known_refs.add(step.step_id)

    return ValidationResult(
        job_id=plan.job_id, plan_version=plan.plan_version, is_valid=not issues, issues=issues
    )


def _check_operation_semantics(
    step: PlanStep,
    known_refs: set[str],
    dataset_ids: set[str],
    canonical_mapping: CanonicalMapping,
    issues: list[ValidationIssue],
) -> None:
    def ref_error(ref: str | None, field_name: str) -> None:
        if ref and ref not in known_refs:
            issues.append(
                ValidationIssue(step_id=step.step_id, field=field_name, message=f"'{ref}' is not a known dataset or earlier step_id")
            )

    def field_error(ref: str | None, field_value: str | None, field_name: str) -> None:
        if not ref or not field_value:
            return
        fields = _canonical_fields(ref, dataset_ids, canonical_mapping)
        if fields is not None and field_value not in fields:
            issues.append(
                ValidationIssue(
                    step_id=step.step_id,
                    field=field_name,
                    message=f"canonical field '{field_value}' not found in '{ref}' (available: {sorted(fields)})",
                )
            )

    if step.operation == OperationType.JOIN:
        ref_error(step.left, "left")
        ref_error(step.right, "right")
        field_error(step.left, step.left_field, "left_field")
        field_error(step.right, step.right_field, "right_field")

    elif step.operation == OperationType.COMPARE:
        ref_error(step.input, "input")
        if step.comparison == ComparisonType.TOLERANCE and step.tolerance is not None and step.tolerance < 0:
            issues.append(ValidationIssue(step_id=step.step_id, field="tolerance", message="tolerance must be >= 0"))
        if step.comparison in (ComparisonType.DATE_DIFF, ComparisonType.DATE_WITHIN) and step.max_days is not None and step.max_days < 0:
            issues.append(ValidationIssue(step_id=step.step_id, field="max_days", message="max_days must be >= 0"))

    elif step.operation == OperationType.MISSING:
        ref_error(step.input, "input")
        if step.side not in ("left", "right"):
            issues.append(ValidationIssue(step_id=step.step_id, field="side", message="side must be 'left' or 'right'"))

    elif step.operation == OperationType.DUPLICATE:
        ref_error(step.input, "input")
        for f in step.fields or []:
            field_error(step.input, f, "fields")

    elif step.operation == OperationType.FILTER:
        ref_error(step.input, "input")
        field_error(step.input, step.field, "field")
        if step.operator is not None and step.operator not in FilterOperator:
            issues.append(ValidationIssue(step_id=step.step_id, field="operator", message="unsupported operator"))

    elif step.operation == OperationType.GROUP:
        ref_error(step.input, "input")
        for f in step.group_by or []:
            field_error(step.input, f, "group_by")

    elif step.operation == OperationType.AGGREGATE:
        ref_error(step.input, "input")
        if step.agg_field:
            field_error(step.input, step.agg_field, "agg_field")
