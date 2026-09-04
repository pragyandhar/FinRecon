from sqlalchemy.orm import Session

from app.execution.engine import ExecutionOutput, run_plan
from app.models.plan import ReconciliationPlan
from app.models.schema import CanonicalMapping
from app.storage import repository as repo


def execute_plan(db: Session, job_id: str, plan: ReconciliationPlan, canonical_mapping: CanonicalMapping) -> ExecutionOutput:
    datasets = repo.get_datasets(db, job_id)
    rows_by_dataset = repo.get_rows_for_job(db, job_id)
    output = run_plan(job_id, plan, datasets, rows_by_dataset, canonical_mapping)
    repo.save_results(db, output.results)
    return output
