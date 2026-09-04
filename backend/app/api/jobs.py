from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile
from sqlalchemy.orm import Session
from starlette.responses import PlainTextResponse

from app.api.deps import get_client, get_db
from app.core.model_client import ModelClient
from app.core.pipeline import run_reconciliation_pipeline
from app.core.util import new_id
from app.models.job import Job
from app.models.report import Report
from app.models.result import ReconciliationResult
from app.reporting.export import results_to_csv
from app.storage import repository as repo
from app.storage.db import get_session

router = APIRouter(prefix="/reconciliation", tags=["reconciliation"])


def _run_pipeline_in_background(job_id: str, uploads: list[tuple[str, bytes]], client: ModelClient) -> None:
    # Runs after the request has returned, in its own DB session — the
    # request-scoped session from get_db() is already closed by then.
    db = get_session()
    try:
        run_reconciliation_pipeline(db, job_id, uploads, client)
    finally:
        db.close()


@router.post("/jobs", response_model=Job)
async def create_job(
    background_tasks: BackgroundTasks,
    files: list[UploadFile],
    db: Session = Depends(get_db),
    client: ModelClient = Depends(get_client),
) -> Job:
    job_id = new_id("job")
    job = repo.create_job(db, job_id)

    uploads = [(f.filename, await f.read()) for f in files]
    background_tasks.add_task(_run_pipeline_in_background, job_id, uploads, client)
    return job


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str, db: Session = Depends(get_db)) -> Job:
    return repo.get_job(db, job_id)


@router.get("/jobs/{job_id}/results", response_model=list[ReconciliationResult])
def get_results(job_id: str, status: str | None = None, db: Session = Depends(get_db)) -> list[ReconciliationResult]:
    return repo.get_results(db, job_id, status=status)


@router.get("/jobs/{job_id}/exceptions")
def get_exceptions(job_id: str, db: Session = Depends(get_db)) -> list[dict]:
    results = repo.get_results(db, job_id, status="EXCEPTION")
    explanations = {e.record_id: e for e in repo.get_exception_explanations(db, job_id)}
    return [
        {
            "result": r.model_dump(mode="json"),
            "explanation": explanations[r.record_id].model_dump(mode="json") if r.record_id in explanations else None,
        }
        for r in results
    ]


@router.get("/jobs/{job_id}/report")
def get_report(job_id: str, format: str = "json", db: Session = Depends(get_db)):
    report: Report = repo.get_report(db, job_id)
    if format == "csv":
        return PlainTextResponse(results_to_csv(report), media_type="text/csv")
    return report
