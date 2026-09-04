from app.models.enums import ComparisonType, OperationType
from app.models.plan import PlanStep, ReconciliationPlan
from app.models.schema import CanonicalMapping
from app.validation.service import validate_plan

CANONICAL = CanonicalMapping(
    job_id="job_test",
    mapping={
        "payments": {"payment_id": "txn", "payment_amount": "amt"},
        "settlements": {"payment_id": "ref", "settlement_amount": "net"},
    },
)
DATASET_IDS = {"payments", "settlements"}


def test_valid_plan_passes():
    plan = ReconciliationPlan(
        job_id="job_test",
        plan_version=1,
        steps=[
            PlanStep(
                step_id="s1", operation=OperationType.JOIN, left="payments", right="settlements",
                left_field="payment_id", right_field="payment_id",
            ),
            PlanStep(
                step_id="s2", operation=OperationType.COMPARE, input="s1",
                comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount",
                tolerance=5,
            ),
        ],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert result.is_valid, result.issues


def test_missing_required_field_rejected():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[PlanStep(step_id="s1", operation=OperationType.JOIN, left="payments", right="settlements")],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    fields_flagged = {i.field for i in result.issues}
    assert {"left_field", "right_field"}.issubset(fields_flagged)


def test_unknown_dataset_rejected():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[
            PlanStep(
                step_id="s1", operation=OperationType.JOIN, left="payments", right="nonexistent_dataset",
                left_field="payment_id", right_field="payment_id",
            )
        ],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    assert any("nonexistent_dataset" in i.message for i in result.issues)


def test_unknown_canonical_field_rejected():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[
            PlanStep(
                step_id="s1", operation=OperationType.JOIN, left="payments", right="settlements",
                left_field="not_a_real_field", right_field="payment_id",
            )
        ],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    assert any("not_a_real_field" in i.message for i in result.issues)


def test_tolerance_requires_tolerance_value():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[
            PlanStep(
                step_id="s1", operation=OperationType.JOIN, left="payments", right="settlements",
                left_field="payment_id", right_field="payment_id",
            ),
            PlanStep(
                step_id="s2", operation=OperationType.COMPARE, input="s1",
                comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount",
            ),
        ],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    assert any(i.field == "tolerance" for i in result.issues)


def test_negative_tolerance_rejected():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[
            PlanStep(
                step_id="s1", operation=OperationType.JOIN, left="payments", right="settlements",
                left_field="payment_id", right_field="payment_id",
            ),
            PlanStep(
                step_id="s2", operation=OperationType.COMPARE, input="s1",
                comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount",
                tolerance=-5,
            ),
        ],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    assert any("tolerance must be >= 0" in i.message for i in result.issues)


def test_step_referencing_undefined_earlier_step_rejected():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[
            PlanStep(
                step_id="s2", operation=OperationType.COMPARE, input="never_defined",
                comparison=ComparisonType.EQUALS, field_a="payment_amount", field_b="settlement_amount",
            ),
        ],
    )
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    assert any("never_defined" in i.message for i in result.issues)


def test_duplicate_step_ids_rejected():
    step_kwargs = dict(
        step_id="s1", operation=OperationType.JOIN, left="payments", right="settlements",
        left_field="payment_id", right_field="payment_id",
    )
    plan = ReconciliationPlan(job_id="job_test", plan_version=1, steps=[PlanStep(**step_kwargs), PlanStep(**step_kwargs)])
    result = validate_plan(plan, CANONICAL, DATASET_IDS)
    assert not result.is_valid
    assert any("duplicate step_id" in i.message for i in result.issues)
