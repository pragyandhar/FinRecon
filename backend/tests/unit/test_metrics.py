from app.models.result import CheckDetail, ReconciliationResult
from app.reporting.metrics import compute_metrics, compute_step_metrics


def _result(
    record_id: str, status: str, checks: list[CheckDetail] | None = None, step_id: str = "s1", rule: str = "TOLERANCE(10)"
) -> ReconciliationResult:
    return ReconciliationResult(
        record_id=record_id, job_id="job_test", step_id=step_id, status=status,
        rule_applied=rule, checks=checks or [],
    )


def test_metrics_exact_counts_and_rates():
    results = [
        _result("r1", "MATCHED"),
        _result("r2", "MATCHED"),
        _result("r3", "MISMATCHED", [CheckDetail(field="amt", expected=100, actual=80, result="OUT_OF_TOLERANCE")]),
        _result("r4", "EXCEPTION"),
        _result("r5", "UNRESOLVED"),
    ]
    metrics = compute_metrics(results)
    assert metrics.total_records == 5
    assert metrics.matched == 2
    assert metrics.mismatched == 1
    assert metrics.exceptions == 1
    assert metrics.unresolved == 1
    assert metrics.match_rate == 0.4
    assert metrics.total_variance_amount == 20.0


def test_metrics_empty_results():
    metrics = compute_metrics([])
    assert metrics.total_records == 0
    assert metrics.match_rate == 0.0


def test_step_metrics_do_not_blend_distinct_checks():
    """Regression test for the real-data bug: two distinct compare steps
    (order vs payment, payment vs settlement) over 100 records each must
    each report their own honest match rate, not one blended figure."""

    results = (
        [_result(f"order_id:ORD{i:04d}", "MATCHED", step_id="s2_order_payment") for i in range(91)]
        + [_result(f"order_id:ORD{i:04d}", "MISMATCHED", step_id="s2_order_payment") for i in range(91, 100)]
        + [_result(f"payment_id:PAY{i:04d}", "MATCHED", step_id="s4_payment_settlement") for i in range(82)]
        + [_result(f"payment_id:PAY{i:04d}", "MISMATCHED", step_id="s4_payment_settlement") for i in range(82, 100)]
    )

    overall = compute_metrics(results)
    assert overall.total_records == 200  # combined total across both checks, not a bug

    breakdown = compute_step_metrics(results)
    assert len(breakdown) == 2
    by_step = {s.step_id: s for s in breakdown}
    assert by_step["s2_order_payment"].total_records == 100
    assert by_step["s2_order_payment"].match_rate == 0.91
    assert by_step["s4_payment_settlement"].total_records == 100
    assert by_step["s4_payment_settlement"].match_rate == 0.82
    # the blended overall rate must not equal either individual step's rate here
    assert overall.match_rate not in (0.91, 0.82)
