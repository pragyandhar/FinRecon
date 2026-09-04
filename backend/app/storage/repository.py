from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import JobNotFoundError
from app.core.util import now_iso
from app.models.chat import ChatMessage
from app.models.dataset import ColumnStats, Dataset, DatasetColumn, DatasetRow
from app.models.enums import JobStatus
from app.models.investigation import ExceptionExplanation
from app.models.job import Job
from app.models.plan import ReconciliationPlan
from app.models.report import Report
from app.models.result import ReconciliationResult
from app.models.schema import CanonicalMapping, SchemaJSON
from app.models.validation import ValidationResult
from app.storage import models as m


# ---- jobs -------------------------------------------------------------

def create_job(db: Session, job_id: str) -> Job:
    ts = now_iso()
    row = m.JobRow(job_id=job_id, status=JobStatus.UPLOADED, created_at=ts, updated_at=ts)
    db.add(row)
    db.commit()
    return Job(job_id=job_id, status=JobStatus.UPLOADED, created_at=ts, updated_at=ts)


def update_job_status(
    db: Session,
    job_id: str,
    status: JobStatus,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    row = db.get(m.JobRow, job_id)
    if row is None:
        raise JobNotFoundError(f"job {job_id} not found")
    row.status = status
    row.updated_at = now_iso()
    row.error_code = error_code
    row.error_message = error_message
    db.commit()


def get_job(db: Session, job_id: str) -> Job:
    row = db.get(m.JobRow, job_id)
    if row is None:
        raise JobNotFoundError(f"job {job_id} not found")
    return Job(
        job_id=row.job_id,
        status=JobStatus(row.status),
        created_at=row.created_at,
        updated_at=row.updated_at,
        error_code=row.error_code,
        error_message=row.error_message,
    )


# ---- datasets -----------------------------------------------------------

def save_dataset(db: Session, dataset: Dataset) -> None:
    existing = db.scalars(
        select(m.DatasetRow_).where(
            m.DatasetRow_.job_id == dataset.job_id, m.DatasetRow_.dataset_id == dataset.dataset_id
        )
    ).first()
    columns_json = [c.model_dump() for c in dataset.columns]
    column_stats_json = [s.model_dump() for s in dataset.column_stats]
    if existing is not None:
        existing.source_file = dataset.source_file
        existing.row_count = dataset.row_count
        existing.columns_json = columns_json
        existing.column_stats_json = column_stats_json
    else:
        db.add(
            m.DatasetRow_(
                dataset_id=dataset.dataset_id,
                job_id=dataset.job_id,
                source_file=dataset.source_file,
                row_count=dataset.row_count,
                columns_json=columns_json,
                column_stats_json=column_stats_json,
            )
        )
    db.commit()


def save_rows(db: Session, job_id: str, rows: list[DatasetRow]) -> None:
    db.bulk_save_objects(
        [
            m.DataRow(
                row_id=r.row_id,
                dataset_id=r.dataset_id,
                job_id=job_id,
                source_file=r.source_file,
                sheet=r.sheet,
                row_index=r.row_index,
                values_json=r.values,
            )
            for r in rows
        ]
    )
    db.commit()


def get_datasets(db: Session, job_id: str) -> list[Dataset]:
    rows = db.scalars(select(m.DatasetRow_).where(m.DatasetRow_.job_id == job_id)).all()
    return [
        Dataset(
            dataset_id=r.dataset_id,
            job_id=r.job_id,
            source_file=r.source_file,
            columns=[DatasetColumn(**c) for c in r.columns_json],
            row_count=r.row_count,
            column_stats=[ColumnStats(**s) for s in r.column_stats_json],
        )
        for r in rows
    ]


def get_rows(db: Session, dataset_id: str) -> list[DatasetRow]:
    rows = db.scalars(select(m.DataRow).where(m.DataRow.dataset_id == dataset_id)).all()
    return [
        DatasetRow(
            row_id=r.row_id,
            dataset_id=r.dataset_id,
            values=r.values_json,
            source_file=r.source_file,
            sheet=r.sheet,
            row_index=r.row_index,
        )
        for r in rows
    ]


def get_rows_for_job(db: Session, job_id: str) -> dict[str, list[DatasetRow]]:
    rows = db.scalars(select(m.DataRow).where(m.DataRow.job_id == job_id)).all()
    by_dataset: dict[str, list[DatasetRow]] = {}
    for r in rows:
        by_dataset.setdefault(r.dataset_id, []).append(
            DatasetRow(
                row_id=r.row_id,
                dataset_id=r.dataset_id,
                values=r.values_json,
                source_file=r.source_file,
                sheet=r.sheet,
                row_index=r.row_index,
            )
        )
    return by_dataset


# ---- schema / canonical mapping -----------------------------------------

def save_schema(db: Session, schema: SchemaJSON) -> None:
    db.merge(m.SchemaRow(job_id=schema.job_id, schema_json=schema.model_dump()))
    db.commit()


def get_schema(db: Session, job_id: str) -> SchemaJSON | None:
    row = db.get(m.SchemaRow, job_id)
    return SchemaJSON(**row.schema_json) if row else None


def save_canonical_mapping(db: Session, mapping: CanonicalMapping) -> None:
    db.merge(m.CanonicalMappingRow(job_id=mapping.job_id, mapping_json=mapping.model_dump()))
    db.commit()


def get_canonical_mapping(db: Session, job_id: str) -> CanonicalMapping | None:
    row = db.get(m.CanonicalMappingRow, job_id)
    return CanonicalMapping(**row.mapping_json) if row else None


# ---- plan / validation ---------------------------------------------------

def save_plan(db: Session, plan: ReconciliationPlan) -> None:
    db.merge(
        m.ReconciliationPlanRow(
            job_id=plan.job_id,
            plan_version=plan.plan_version,
            steps_json=[s.model_dump(mode="json") for s in plan.steps],
        )
    )
    db.commit()


def get_latest_plan(db: Session, job_id: str) -> ReconciliationPlan | None:
    row = db.scalars(
        select(m.ReconciliationPlanRow)
        .where(m.ReconciliationPlanRow.job_id == job_id)
        .order_by(m.ReconciliationPlanRow.plan_version.desc())
    ).first()
    if row is None:
        return None
    return ReconciliationPlan(job_id=row.job_id, plan_version=row.plan_version, steps=row.steps_json)


def save_validation_result(db: Session, result: ValidationResult) -> None:
    db.merge(
        m.ValidationResultRow(
            job_id=result.job_id,
            plan_version=result.plan_version,
            is_valid=result.is_valid,
            issues_json=[i.model_dump() for i in result.issues],
        )
    )
    db.commit()


# ---- results ---------------------------------------------------------

def save_results(db: Session, results: list[ReconciliationResult]) -> None:
    db.bulk_save_objects(
        [
            m.ReconciliationResultRow(
                record_id=r.record_id,
                job_id=r.job_id,
                step_id=r.step_id,
                status=r.status,
                rule_applied=r.rule_applied,
                checks_json=[c.model_dump(mode="json") for c in r.checks],
                evidence_json=[e.model_dump(mode="json") for e in r.evidence],
                reason=r.reason,
            )
            for r in results
        ]
    )
    db.commit()


def get_results(db: Session, job_id: str, status: str | None = None) -> list[ReconciliationResult]:
    stmt = select(m.ReconciliationResultRow).where(m.ReconciliationResultRow.job_id == job_id)
    if status:
        stmt = stmt.where(m.ReconciliationResultRow.status == status)
    rows = db.scalars(stmt).all()
    return [
        ReconciliationResult(
            record_id=r.record_id,
            job_id=r.job_id,
            step_id=r.step_id,
            status=r.status,
            rule_applied=r.rule_applied,
            checks=r.checks_json,
            evidence=r.evidence_json,
            reason=r.reason,
        )
        for r in rows
    ]


# ---- exception explanations -----------------------------------------

def save_exception_explanations(db: Session, job_id: str, explanations: list[ExceptionExplanation]) -> None:
    for e in explanations:
        db.merge(
            m.ExceptionExplanationRow(
                job_id=job_id,
                record_id=e.record_id,
                reason=e.reason,
                evidence_used_json=e.evidence_used,
                likely_cause=e.likely_cause,
                recommended_action=e.recommended_action,
                confidence=e.confidence,
                resolved=e.resolved,
            )
        )
    db.commit()


def get_exception_explanations(db: Session, job_id: str) -> list[ExceptionExplanation]:
    rows = db.scalars(
        select(m.ExceptionExplanationRow).where(m.ExceptionExplanationRow.job_id == job_id)
    ).all()
    return [
        ExceptionExplanation(
            record_id=r.record_id,
            reason=r.reason,
            evidence_used=r.evidence_used_json,
            likely_cause=r.likely_cause,
            recommended_action=r.recommended_action,
            confidence=r.confidence,
            resolved=r.resolved,
        )
        for r in rows
    ]


def get_exception_explanation(db: Session, job_id: str, record_id: str) -> ExceptionExplanation | None:
    row = db.get(m.ExceptionExplanationRow, {"job_id": job_id, "record_id": record_id})
    if row is None:
        return None
    return ExceptionExplanation(
        record_id=row.record_id,
        reason=row.reason,
        evidence_used=row.evidence_used_json,
        likely_cause=row.likely_cause,
        recommended_action=row.recommended_action,
        confidence=row.confidence,
        resolved=row.resolved,
    )


# ---- report ------------------------------------------------------------

def save_report(db: Session, report: Report) -> None:
    db.merge(
        m.ReportRow(
            job_id=report.job_id,
            generated_at=report.generated_at,
            report_json=report.model_dump(mode="json"),
        )
    )
    db.commit()


def get_report(db: Session, job_id: str) -> Report | None:
    row = db.get(m.ReportRow, job_id)
    return Report(**row.report_json) if row else None


# ---- chat ---------------------------------------------------------------

def create_chat_session(db: Session, session_id: str, job_id: str) -> None:
    db.merge(m.ChatSessionRow(session_id=session_id, job_id=job_id, created_at=now_iso()))
    db.commit()


def chat_session_exists(db: Session, session_id: str) -> bool:
    return db.get(m.ChatSessionRow, session_id) is not None


def add_chat_message(db: Session, session_id: str, message: ChatMessage) -> None:
    db.add(
        m.ChatMessageRow(
            session_id=session_id, role=message.role, content=message.content, created_at=now_iso()
        )
    )
    db.commit()


def get_chat_history(db: Session, session_id: str) -> list[ChatMessage]:
    rows = db.scalars(
        select(m.ChatMessageRow)
        .where(m.ChatMessageRow.session_id == session_id)
        .order_by(m.ChatMessageRow.id.asc())
    ).all()
    return [ChatMessage(role=r.role, content=r.content) for r in rows]


# ---- model call audit -----------------------------------------------

def log_model_call(
    db: Session,
    *,
    job_id: str | None,
    stage: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    latency_ms: int,
    success: bool,
    error: str | None = None,
) -> None:
    db.add(
        m.ModelCallRow(
            job_id=job_id,
            stage=stage,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
            created_at=now_iso(),
        )
    )
    db.commit()


def count_model_calls(db: Session, job_id: str) -> int:
    rows = db.scalars(select(m.ModelCallRow).where(m.ModelCallRow.job_id == job_id)).all()
    return len(rows)
