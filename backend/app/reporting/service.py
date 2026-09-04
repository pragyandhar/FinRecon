from sqlalchemy.orm import Session

from app.core.util import now_iso
from app.models.report import Report
from app.reporting.metrics import compute_metrics
from app.storage import repository as repo


def generate_report(db: Session, job_id: str) -> Report:
    results = repo.get_results(db, job_id)
    metrics = compute_metrics(results)
    explanations = repo.get_exception_explanations(db, job_id)
    ai_calls = repo.count_model_calls(db, job_id)

    report = Report(
        job_id=job_id,
        generated_at=now_iso(),
        metrics=metrics,
        results=results,
        exception_explanations=explanations,
        ai_calls_made=ai_calls,
    )
    repo.save_report(db, report)
    return report
