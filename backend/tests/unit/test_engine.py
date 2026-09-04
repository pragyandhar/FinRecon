"""Unit tests for the deterministic execution engine. These are the
tests that matter most: the engine is the piece that must never depend
on any specific financial column name, must not care about row order,
and must never silently drop a record."""

from pathlib import Path

import pytest

from app.core.errors import PlanExecutionError
from app.execution.engine import run_plan
from app.models.dataset import Dataset, DatasetColumn, DatasetRow
from app.models.enums import ComparisonType, JoinType, OperationType
from app.models.plan import PlanStep, ReconciliationPlan
from app.models.schema import CanonicalMapping


def _dataset(dataset_id: str, columns: list[str]) -> Dataset:
    return Dataset(
        dataset_id=dataset_id,
        job_id="job_test",
        source_file=f"{dataset_id}.csv",
        columns=[DatasetColumn(name=c, raw_type="string") for c in columns],
        row_count=0,
    )


def _row(dataset_id: str, row_id: str, values: dict, index: int) -> DatasetRow:
    return DatasetRow(
        row_id=row_id, dataset_id=dataset_id, values=values, source_file=f"{dataset_id}.csv", row_index=index
    )


PAYMENTS = _dataset("payments", ["txn", "amt", "date"])
SETTLEMENTS = _dataset("settlements", ["ref", "net", "sdate"])

CANONICAL = CanonicalMapping(
    job_id="job_test",
    mapping={
        "payments": {"payment_id": "txn", "payment_amount": "amt", "payment_date": "date"},
        "settlements": {"payment_id": "ref", "settlement_amount": "net", "settlement_date": "sdate"},
    },
)


def _payments_rows(order: list[str] | None = None) -> list[DatasetRow]:
    data = {
        "TX1": {"txn": "TX1", "amt": 1000, "date": "2024-01-01"},
        "TX2": {"txn": "TX2", "amt": 500, "date": "2024-01-02"},
        "TX3": {"txn": "TX3", "amt": 200, "date": "2024-01-03"},
    }
    order = order or list(data.keys())
    return [_row("payments", f"payments_{i:03d}", data[k], i) for i, k in enumerate(order)]


def _settlements_rows(order: list[str] | None = None) -> list[DatasetRow]:
    data = {
        "TX1": {"ref": "TX1", "net": 990, "sdate": "2024-01-05"},
        "TX2": {"ref": "TX2", "net": 500, "sdate": "2024-01-02"},
    }
    order = order or list(data.keys())
    return [_row("settlements", f"settlements_{i:03d}", data[k], i) for i, k in enumerate(order)]


def _base_plan(extra_steps: list[PlanStep]) -> ReconciliationPlan:
    join = PlanStep(
        step_id="s1_join",
        operation=OperationType.JOIN,
        left="payments",
        right="settlements",
        left_field="payment_id",
        right_field="payment_id",
        join_type=JoinType.FULL_OUTER,
    )
    return ReconciliationPlan(job_id="job_test", plan_version=1, steps=[join, *extra_steps])


def test_tolerance_match_and_mismatch():
    compare = PlanStep(
        step_id="s2_compare",
        operation=OperationType.COMPARE,
        input="s1_join",
        comparison=ComparisonType.TOLERANCE,
        field_a="payment_amount",
        field_b="settlement_amount",
        tolerance=10,
    )
    plan = _base_plan([compare])
    rows_by_dataset = {"payments": _payments_rows(), "settlements": _settlements_rows()}
    output = run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, CANONICAL)

    by_id = {r.record_id: r for r in output.results}
    assert by_id["payment_id:TX1"].status == "MATCHED"  # diff=10, boundary inclusive
    assert by_id["payment_id:TX2"].status == "MATCHED"  # diff=0
    assert by_id["payment_id:TX3"].status == "EXCEPTION"  # settlement side missing entirely
    assert len(output.results) == 3


def test_row_order_does_not_matter():
    compare = PlanStep(
        step_id="s2_compare", operation=OperationType.COMPARE, input="s1_join",
        comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount", tolerance=10,
    )
    plan = _base_plan([compare])
    rows_by_dataset = {
        "payments": _payments_rows(order=["TX3", "TX1", "TX2"]),
        "settlements": _settlements_rows(order=["TX2", "TX1"]),
    }
    output = run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, CANONICAL)
    by_id = {r.record_id: r.status for r in output.results}
    assert by_id == {"payment_id:TX1": "MATCHED", "payment_id:TX2": "MATCHED", "payment_id:TX3": "EXCEPTION"}


def test_missing_detects_unmatched_right_side():
    missing = PlanStep(step_id="s3_missing", operation=OperationType.MISSING, input="s1_join", side="right")
    plan = _base_plan([missing])
    rows_by_dataset = {"payments": _payments_rows(), "settlements": _settlements_rows()}
    output = run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, CANONICAL)

    assert len(output.results) == 1
    assert output.results[0].record_id == "payment_id:TX3"
    assert output.results[0].status == "EXCEPTION"
    assert output.results[0].rule_applied == "MISSING:right"


def test_date_within_window():
    compare = PlanStep(
        step_id="s4_date", operation=OperationType.COMPARE, input="s1_join",
        comparison=ComparisonType.DATE_WITHIN, field_a="payment_date", field_b="settlement_date", max_days=3,
    )
    plan = _base_plan([compare])
    rows_by_dataset = {"payments": _payments_rows(), "settlements": _settlements_rows()}
    output = run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, CANONICAL)
    by_id = {r.record_id: r.status for r in output.results}
    assert by_id["payment_id:TX1"] == "MISMATCHED"  # 4 days apart, window is 3
    assert by_id["payment_id:TX2"] == "MATCHED"  # same day


def test_duplicate_detection():
    dup_row = _row("payments", "payments_dup", {"txn": "TX1", "amt": 1000, "date": "2024-01-01"}, 99)
    duplicate_step = PlanStep(
        step_id="s5_dup", operation=OperationType.DUPLICATE, input="payments", fields=["payment_id"]
    )
    plan = ReconciliationPlan(job_id="job_test", plan_version=1, steps=[duplicate_step])
    rows_by_dataset = {"payments": [*_payments_rows(), dup_row]}
    output = run_plan("job_test", plan, [PAYMENTS], rows_by_dataset, CANONICAL)

    assert len(output.results) == 1
    assert output.results[0].status == "EXCEPTION"
    assert output.results[0].record_id == "payment_id:TX1"


def test_null_amount_is_exception_not_a_fabricated_match():
    rows = _payments_rows()
    rows[0] = _row("payments", "payments_000", {"txn": "TX1", "amt": None, "date": "2024-01-01"}, 0)
    compare = PlanStep(
        step_id="s2_compare", operation=OperationType.COMPARE, input="s1_join",
        comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount", tolerance=10,
    )
    plan = _base_plan([compare])
    rows_by_dataset = {"payments": rows, "settlements": _settlements_rows()}
    output = run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, CANONICAL)
    by_id = {r.record_id: r for r in output.results}
    assert by_id["payment_id:TX1"].status == "EXCEPTION"
    assert by_id["payment_id:TX1"].reason == "one or both compared values are missing"


def test_evidence_preserved_for_every_result():
    compare = PlanStep(
        step_id="s2_compare", operation=OperationType.COMPARE, input="s1_join",
        comparison=ComparisonType.TOLERANCE, field_a="payment_amount", field_b="settlement_amount", tolerance=10,
    )
    plan = _base_plan([compare])
    rows_by_dataset = {"payments": _payments_rows(), "settlements": _settlements_rows()}
    output = run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, CANONICAL)
    matched = next(r for r in output.results if r.record_id == "payment_id:TX2")
    dataset_ids = {e.dataset_id for e in matched.evidence}
    assert dataset_ids == {"payments", "settlements"}
    assert all(e.values for e in matched.evidence)


def test_colliding_canonical_field_names_fail_loudly_not_silently():
    """Regression test for a real bug: if canonical mapping ever gives two
    joined datasets the SAME non-key canonical name (e.g. both "amount"
    instead of "payment_amount"/"settlement_amount"), pandas' merge
    disambiguates with suffixes and the plan's field reference becomes
    ambiguous. The engine must raise a clear error here, never silently
    pick one side's value and call it a comparison."""

    bad_canonical = CanonicalMapping(
        job_id="job_test",
        mapping={
            "payments": {"payment_id": "txn", "amount": "amt"},
            "settlements": {"payment_id": "ref", "amount": "net"},
        },
    )
    compare = PlanStep(
        step_id="s2_compare", operation=OperationType.COMPARE, input="s1_join",
        comparison=ComparisonType.TOLERANCE, field_a="amount", field_b="amount", tolerance=10,
    )
    plan = _base_plan([compare])
    rows_by_dataset = {"payments": _payments_rows(), "settlements": _settlements_rows()}

    with pytest.raises(PlanExecutionError, match="ambiguous"):
        run_plan("job_test", plan, [PAYMENTS, SETTLEMENTS], rows_by_dataset, bad_canonical)


def test_join_on_low_cardinality_field_refuses_combinatorial_blowup():
    """Regression test for a real production incident: the planner
    joined on a non-unique field (here simulated directly) instead of an
    actual ID. Every row sharing a value pairs with every row on the
    other side sharing it, so 20x20 inputs joined on a field where every
    row shares one value produces 400 rows -- a 20x blowup relative to
    the input size. Left unchecked this cascades into thousands of
    downstream "exceptions" queued for individual AI investigation:
    hours of runtime and real API spend on a plan that was never valid.
    The engine must refuse immediately instead."""

    n = 20
    payments_ds = _dataset("payments", ["txn", "status"])
    settlements_ds = _dataset("settlements", ["ref", "status"])
    canonical = CanonicalMapping(
        job_id="job_test",
        mapping={
            "payments": {"payment_id": "txn", "status": "status"},
            "settlements": {"payment_id": "ref", "status": "status"},
        },
    )
    payments_rows = [
        _row("payments", f"payments_{i:03d}", {"txn": f"TX{i}", "status": "SUCCESS"}, i) for i in range(n)
    ]
    settlements_rows = [
        _row("settlements", f"settlements_{i:03d}", {"ref": f"ST{i}", "status": "SUCCESS"}, i) for i in range(n)
    ]

    bad_join = PlanStep(
        step_id="s1_join", operation=OperationType.JOIN, left="payments", right="settlements",
        left_field="status", right_field="status", join_type=JoinType.FULL_OUTER,
    )
    plan = ReconciliationPlan(job_id="job_test", plan_version=1, steps=[bad_join])

    with pytest.raises(PlanExecutionError, match="per-record identifier"):
        run_plan(
            "job_test", plan, [payments_ds, settlements_ds],
            {"payments": payments_rows, "settlements": settlements_rows}, canonical,
        )


def test_real_incident_data_merchant_id_join_now_refused():
    """Reproduces the exact production incident with the actual data
    that caused it: merchant_ledger_100.csv and
    gateway_transactions_100.csv both share a "merchant_id" field that
    IS a legitimate, correctly-shared identifier (role-wise) -- but
    only 15 distinct merchants across 100 rows each, so joining
    individual transactions on it produces 776 rows from 100x100
    inputs (7.76x), which the size-based guard alone (10x threshold)
    would NOT have caught. The uniqueness-based guard must catch it
    directly, on the join key itself, regardless of output size."""

    import pandas as pd

    data_dir = Path(__file__).resolve().parents[3] / "data"
    ledger_df = pd.read_csv(data_dir / "merchant_ledger_100.csv")
    gateway_df = pd.read_csv(data_dir / "gateway_transactions_100.csv")

    ledger_ds = _dataset("merchant_ledger", list(ledger_df.columns))
    gateway_ds = _dataset("gateway_transactions", list(gateway_df.columns))
    canonical = CanonicalMapping(
        job_id="job_test",
        mapping={
            "merchant_ledger": {"merchant_id": "merchant_id"},
            "gateway_transactions": {"merchant_id": "merchant_id"},
        },
    )
    ledger_rows = [
        _row("merchant_ledger", f"ledger_{i:03d}", {"merchant_id": v}, i)
        for i, v in enumerate(ledger_df["merchant_id"])
    ]
    gateway_rows = [
        _row("gateway_transactions", f"gateway_{i:03d}", {"merchant_id": v}, i)
        for i, v in enumerate(gateway_df["merchant_id"])
    ]

    bad_join = PlanStep(
        step_id="s1_join", operation=OperationType.JOIN, left="merchant_ledger", right="gateway_transactions",
        left_field="merchant_id", right_field="merchant_id", join_type=JoinType.FULL_OUTER,
    )
    plan = ReconciliationPlan(job_id="job_test", plan_version=1, steps=[bad_join])

    with pytest.raises(PlanExecutionError, match="unique"):
        run_plan(
            "job_test", plan, [ledger_ds, gateway_ds],
            {"merchant_ledger": ledger_rows, "gateway_transactions": gateway_rows}, canonical,
        )


def test_real_incident_data_correct_join_key_is_not_falsely_rejected():
    """The other half of the proof: the guard must not be so strict it
    rejects a genuinely correct join on this same real data. ledger's
    transaction_reference and gateway's gateway_reference are ~100%
    unique per-transaction references -- the guard must let this
    through and the engine must execute it normally."""

    import pandas as pd

    data_dir = Path(__file__).resolve().parents[3] / "data"
    ledger_df = pd.read_csv(data_dir / "merchant_ledger_100.csv")
    gateway_df = pd.read_csv(data_dir / "gateway_transactions_100.csv")

    ledger_ds = _dataset("merchant_ledger", list(ledger_df.columns))
    gateway_ds = _dataset("gateway_transactions", list(gateway_df.columns))
    canonical = CanonicalMapping(
        job_id="job_test",
        mapping={
            "merchant_ledger": {"txn_ref": "transaction_reference"},
            "gateway_transactions": {"txn_ref": "gateway_reference"},
        },
    )
    ledger_rows = [
        _row("merchant_ledger", f"ledger_{i:03d}", {"transaction_reference": v}, i)
        for i, v in enumerate(ledger_df["transaction_reference"])
    ]
    gateway_rows = [
        _row("gateway_transactions", f"gateway_{i:03d}", {"gateway_reference": v}, i)
        for i, v in enumerate(gateway_df["gateway_reference"])
    ]

    good_join = PlanStep(
        step_id="s1_join", operation=OperationType.JOIN, left="merchant_ledger", right="gateway_transactions",
        left_field="txn_ref", right_field="txn_ref", join_type=JoinType.FULL_OUTER,
    )
    plan = ReconciliationPlan(job_id="job_test", plan_version=1, steps=[good_join])

    output = run_plan(
        "job_test", plan, [ledger_ds, gateway_ds],
        {"merchant_ledger": ledger_rows, "gateway_transactions": gateway_rows}, canonical,
    )
    # No results yet (no COMPARE step), but critically: no exception raised,
    # and the join itself must have run (checked via the engine's internal
    # relation, proven indirectly by reaching this line without error).
    assert output.results == []
