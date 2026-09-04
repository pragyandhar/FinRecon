import csv
import io

from app.models.report import Report


def results_to_csv(report: Report) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["record_id", "status", "rule_applied", "reason", "checks", "evidence"])
    for r in report.results:
        writer.writerow(
            [
                r.record_id,
                r.status,
                r.rule_applied,
                r.reason or "",
                "; ".join(f"{c.field}: expected={c.expected} actual={c.actual} -> {c.result}" for c in r.checks),
                "; ".join(f"{e.dataset_id}:{e.row_id}" for e in r.evidence),
            ]
        )
    return buffer.getvalue()
