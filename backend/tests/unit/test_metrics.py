from app.models.result import CheckDetail, ReconciliationResult
from app.reporting.metrics import compute_metrics


def _result(record_id: str, status: str, checks: list[CheckDetail] | None = None) -> ReconciliationResult:
    return ReconciliationResult(
        record_id=record_id, job_id="job_test", step_id="s1", status=status,
        rule_applied="TOLERANCE(10)", checks=checks or [],
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
