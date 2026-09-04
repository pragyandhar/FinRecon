"""Relationship labels must come entirely from the plan the backend
generated for a job — never from hardcoded dataset names. These tests
deliberately use two unrelated naming schemes to prove that."""

from app.models.enums import ComparisonType, JoinType, OperationType
from app.models.plan import PlanStep, ReconciliationPlan
from app.reporting.labels import describe_step_relationship


def test_two_dataset_compare_label():
    plan = ReconciliationPlan(
        job_id="job_test",
        plan_version=1,
        steps=[
            PlanStep(
                step_id="s1_join", operation=OperationType.JOIN, left="orders", right="payments",
                left_field="order_id", right_field="order_id", join_type=JoinType.FULL_OUTER,
            ),
            PlanStep(
                step_id="s2_compare", operation=OperationType.COMPARE, input="s1_join",
                comparison=ComparisonType.TOLERANCE, field_a="order_amount", field_b="payment_amount", tolerance=1,
            ),
        ],
    )
    label = describe_step_relationship(plan, "s2_compare", {"orders", "payments"})
    assert label == "Orders ↔ Payments"


def test_chained_three_dataset_compare_label():
    plan = ReconciliationPlan(
        job_id="job_test",
        plan_version=1,
        steps=[
            PlanStep(
                step_id="s1_join", operation=OperationType.JOIN, left="orders", right="payments",
                left_field="order_id", right_field="order_id",
            ),
            PlanStep(
                step_id="s2_join", operation=OperationType.JOIN, left="s1_join", right="settlements",
                left_field="payment_id", right_field="payment_id",
            ),
            PlanStep(
                step_id="s3_compare", operation=OperationType.COMPARE, input="s2_join",
                comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount", tolerance=1,
            ),
        ],
    )
    label = describe_step_relationship(plan, "s3_compare", {"orders", "payments", "settlements"})
    assert label == "Orders ↔ Payments ↔ Settlements"


def test_single_dataset_duplicate_label():
    plan = ReconciliationPlan(
        job_id="job_test", plan_version=1,
        steps=[
            PlanStep(step_id="s1_dup", operation=OperationType.DUPLICATE, input="payments", fields=["payment_id"]),
        ],
    )
    label = describe_step_relationship(plan, "s1_dup", {"payments"})
    assert label == "Payments"


def test_label_derives_from_whatever_dataset_names_the_plan_actually_uses():
    """Different naming scheme entirely (a different reconciliation
    plan) must still produce a correct, non-hardcoded label."""

    plan = ReconciliationPlan(
        job_id="job_other",
        plan_version=1,
        steps=[
            PlanStep(
                step_id="j1", operation=OperationType.JOIN,
                left="gateway_transactions", right="bank_statement_lines",
                left_field="txn_ref", right_field="txn_ref",
            ),
            PlanStep(
                step_id="c1", operation=OperationType.COMPARE, input="j1",
                comparison=ComparisonType.TOLERANCE, field_a="txn_amount", field_b="statement_amount", tolerance=0.5,
            ),
        ],
    )
    label = describe_step_relationship(plan, "c1", {"gateway_transactions", "bank_statement_lines"})
    assert label == "Gateway Transactions ↔ Bank Statement Lines"


def test_unresolvable_step_falls_back_to_step_id_not_a_guess():
    plan = ReconciliationPlan(job_id="job_test", plan_version=1, steps=[])
    label = describe_step_relationship(plan, "missing_step", {"orders"})
    assert label == "missing_step"
