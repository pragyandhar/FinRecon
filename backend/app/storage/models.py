from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.storage.db import Base


class JobRow(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[str] = mapped_column(String)
    updated_at: Mapped[str] = mapped_column(String)
    error_code: Mapped[str | None] = mapped_column(String, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DatasetRow_(Base):
    """Dataset-level metadata (one row per extracted dataset).

    `dataset_id` is a short, human/LLM-friendly name ("payments") that is
    only unique *within* a job, not globally — the real key is
    (job_id, dataset_id), enforced by the unique constraint below.
    """

    __tablename__ = "datasets"
    __table_args__ = (UniqueConstraint("job_id", "dataset_id", name="uq_dataset_job"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.job_id"), index=True)
    source_file: Mapped[str] = mapped_column(String)
    row_count: Mapped[int] = mapped_column(Integer)
    columns_json: Mapped[list] = mapped_column(JSON)
    column_stats_json: Mapped[list] = mapped_column(JSON)


class DataRow(Base):
    """One record inside a dataset."""

    __tablename__ = "dataset_rows"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    row_id: Mapped[str] = mapped_column(String, index=True)
    dataset_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    source_file: Mapped[str] = mapped_column(String)
    sheet: Mapped[str | None] = mapped_column(String, nullable=True)
    row_index: Mapped[int] = mapped_column(Integer)
    values_json: Mapped[dict] = mapped_column(JSON)


class SchemaRow(Base):
    __tablename__ = "schemas"

    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.job_id"), primary_key=True)
    schema_json: Mapped[dict] = mapped_column(JSON)


class CanonicalMappingRow(Base):
    __tablename__ = "canonical_mappings"

    job_id: Mapped[str] = mapped_column(String, ForeignKey("jobs.job_id"), primary_key=True)
    mapping_json: Mapped[dict] = mapped_column(JSON)


class ReconciliationPlanRow(Base):
    __tablename__ = "reconciliation_plans"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    steps_json: Mapped[list] = mapped_column(JSON)


class ValidationResultRow(Base):
    __tablename__ = "validation_results"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    plan_version: Mapped[int] = mapped_column(Integer, primary_key=True)
    is_valid: Mapped[bool] = mapped_column(Boolean)
    issues_json: Mapped[list] = mapped_column(JSON)


class ReconciliationResultRow(Base):
    __tablename__ = "reconciliation_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    record_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    step_id: Mapped[str] = mapped_column(String)
    status: Mapped[str] = mapped_column(String, index=True)
    rule_applied: Mapped[str] = mapped_column(String)
    checks_json: Mapped[list] = mapped_column(JSON)
    evidence_json: Mapped[list] = mapped_column(JSON)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ExceptionExplanationRow(Base):
    __tablename__ = "exceptions"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    evidence_used_json: Mapped[list] = mapped_column(JSON)
    likely_cause: Mapped[str | None] = mapped_column(String, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String, nullable=True)
    confidence: Mapped[float] = mapped_column(Float)
    resolved: Mapped[bool] = mapped_column(Boolean)


class ReportRow(Base):
    __tablename__ = "reports"

    job_id: Mapped[str] = mapped_column(String, primary_key=True)
    generated_at: Mapped[str] = mapped_column(String)
    report_json: Mapped[dict] = mapped_column(JSON)


class ChatSessionRow(Base):
    __tablename__ = "chat_sessions"

    session_id: Mapped[str] = mapped_column(String, primary_key=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    created_at: Mapped[str] = mapped_column(String)


class ChatMessageRow(Base):
    __tablename__ = "chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String, ForeignKey("chat_sessions.session_id"), index=True)
    role: Mapped[str] = mapped_column(String)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String)


class ModelCallRow(Base):
    """Audit trail for every AI call — required to keep the $ budget
    visible and to answer 'why did the system decide this' later."""

    __tablename__ = "model_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    job_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    stage: Mapped[str] = mapped_column(String)
    model: Mapped[str] = mapped_column(String)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    success: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String)
