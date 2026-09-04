from app.models.report import Metrics, StepMetrics
from app.models.result import ReconciliationResult


def _safe_rate(count: int, total: int) -> float:
    return round(count / total, 4) if total else 0.0


def _numeric(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _variance(results: list[ReconciliationResult]) -> float:
    variance = 0.0
    for r in results:
        if r.status != "MISMATCHED":
            continue
        for check in r.checks:
            a, b = _numeric(check.expected), _numeric(check.actual)
            if a is not None and b is not None:
                variance += abs(a - b)
    return round(variance, 2)


def _counts(results: list[ReconciliationResult]) -> dict[str, int]:
    return {
        "total": len(results),
        "matched": sum(1 for r in results if r.status == "MATCHED"),
        "mismatched": sum(1 for r in results if r.status == "MISMATCHED"),
        "exceptions": sum(1 for r in results if r.status == "EXCEPTION"),
        "unresolved": sum(1 for r in results if r.status == "UNRESOLVED"),
    }


def compute_metrics(results: list[ReconciliationResult]) -> Metrics:
    """Every number here is a plain count/sum over `results` — no model
    is ever asked to compute or estimate a metric.

    This is a combined total across every check a plan ran. If a plan
    runs two distinct comparisons over the same underlying records
    (e.g. order_amount vs payment_amount, AND payment_amount vs
    settlement_amount), each contributes its own results here — that's
    by design, not double-counting, but a single blended rate over the
    combination can hide which specific check is actually failing. See
    `compute_step_metrics` for the per-check breakdown that doesn't.
    """

    c = _counts(results)
    return Metrics(
        total_records=c["total"],
        matched=c["matched"],
        mismatched=c["mismatched"],
        exceptions=c["exceptions"],
        unresolved=c["unresolved"],
        match_rate=_safe_rate(c["matched"], c["total"]),
        mismatch_rate=_safe_rate(c["mismatched"], c["total"]),
        exception_rate=_safe_rate(c["exceptions"], c["total"]),
        unresolved_rate=_safe_rate(c["unresolved"], c["total"]),
        total_variance_amount=_variance(results),
    )


def compute_step_metrics(results: list[ReconciliationResult]) -> list[StepMetrics]:
    """One Metrics breakdown per plan step (one per distinct check),
    in the order steps first appear in `results`, so "order_amount vs
    payment_amount" and "payment_amount vs settlement_amount" (say)
    each get their own honest match rate instead of being blended."""

    by_step: dict[str, list[ReconciliationResult]] = {}
    for r in results:
        by_step.setdefault(r.step_id, []).append(r)

    breakdown = []
    for step_id, step_results in by_step.items():
        c = _counts(step_results)
        breakdown.append(
            StepMetrics(
                step_id=step_id,
                rule_applied=step_results[0].rule_applied,
                total_records=c["total"],
                matched=c["matched"],
                mismatched=c["mismatched"],
                exceptions=c["exceptions"],
                unresolved=c["unresolved"],
                match_rate=_safe_rate(c["matched"], c["total"]),
                mismatch_rate=_safe_rate(c["mismatched"], c["total"]),
                exception_rate=_safe_rate(c["exceptions"], c["total"]),
                unresolved_rate=_safe_rate(c["unresolved"], c["total"]),
                total_variance_amount=_variance(step_results),
            )
        )
    return breakdown
