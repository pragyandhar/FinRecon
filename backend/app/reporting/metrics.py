from app.models.report import Metrics
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


def compute_metrics(results: list[ReconciliationResult]) -> Metrics:
    """Every number here is a plain count/sum over `results` — no model
    is ever asked to compute or estimate a metric."""

    total = len(results)
    matched = sum(1 for r in results if r.status == "MATCHED")
    mismatched = sum(1 for r in results if r.status == "MISMATCHED")
    exceptions = sum(1 for r in results if r.status == "EXCEPTION")
    unresolved = sum(1 for r in results if r.status == "UNRESOLVED")

    variance = 0.0
    for r in results:
        if r.status != "MISMATCHED":
            continue
        for check in r.checks:
            a, b = _numeric(check.expected), _numeric(check.actual)
            if a is not None and b is not None:
                variance += abs(a - b)

    return Metrics(
        total_records=total,
        matched=matched,
        mismatched=mismatched,
        exceptions=exceptions,
        unresolved=unresolved,
        match_rate=_safe_rate(matched, total),
        mismatch_rate=_safe_rate(mismatched, total),
        exception_rate=_safe_rate(exceptions, total),
        unresolved_rate=_safe_rate(unresolved, total),
        total_variance_amount=round(variance, 2),
    )
