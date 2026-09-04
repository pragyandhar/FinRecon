from sqlalchemy.orm import Session

from app.core.errors import FinReconError
from app.core.logging import get_logger
from app.core.model_client import ModelClient
from app.execution.service import execute_plan
from app.ingestion.service import ingest_uploaded_files
from app.investigation.service import investigate_exceptions
from app.models.enums import JobStatus
from app.planning.service import generate_validated_plan
from app.reporting.service import generate_report
from app.schema_understanding.service import understand_schema
from app.storage import repository as repo

logger = get_logger(__name__)


def run_reconciliation_pipeline(
    db: Session, job_id: str, uploads: list[tuple[str, bytes]], client: ModelClient
) -> None:
    """Understand -> Standardize -> Plan -> Validate -> Execute ->
    Investigate -> Report. Runs as a background task after the upload
    request returns; the frontend polls job status. Any explicit
    FinReconError (or anything unexpected) marks the job FAILED with a
    real error code instead of leaving it stuck or faking success.
    """

    try:
        repo.update_job_status(db, job_id, JobStatus.EXTRACTING)
        datasets = ingest_uploaded_files(db, job_id, uploads)

        repo.update_job_status(db, job_id, JobStatus.UNDERSTANDING_SCHEMA)
        schema, canonical_mapping = understand_schema(db, job_id, datasets, client)

        repo.update_job_status(db, job_id, JobStatus.PLANNING)
        plan, validation = generate_validated_plan(db, job_id, schema, canonical_mapping, datasets, client)

        repo.update_job_status(db, job_id, JobStatus.VALIDATING_PLAN)
        repo.update_job_status(db, job_id, JobStatus.RECONCILING)
        execution_output = execute_plan(db, job_id, plan, canonical_mapping)

        repo.update_job_status(db, job_id, JobStatus.INVESTIGATING)
        investigate_exceptions(db, job_id, execution_output.results, client)

        repo.update_job_status(db, job_id, JobStatus.GENERATING_REPORT)
        generate_report(db, job_id)

        repo.update_job_status(db, job_id, JobStatus.COMPLETED)
    except FinReconError as exc:
        logger.warning("job %s failed at a known stage: %s", job_id, exc.to_dict())
        repo.update_job_status(db, job_id, JobStatus.FAILED, error_code=exc.code, error_message=exc.message)
    except Exception as exc:  # noqa: BLE001 — last resort: never leave a job stuck silently
        logger.exception("job %s failed unexpectedly", job_id)
        repo.update_job_status(db, job_id, JobStatus.FAILED, error_code="INTERNAL_ERROR", error_message=str(exc))
