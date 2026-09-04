from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import RecordStatus


class CheckDetail(BaseModel):
    field: str | None = None
    expected: Any = None
    actual: Any = None
    result: str  # e.g. "EQUAL" | "NOT_EQUAL" | "WITHIN_TOLERANCE" | "OUT_OF_TOLERANCE"


class Evidence(BaseModel):
    dataset_id: str
    row_id: str
    values: dict[str, Any] = Field(default_factory=dict)


class ReconciliationResult(BaseModel):
    record_id: str
    job_id: str
    step_id: str
    status: RecordStatus
    rule_applied: str
    checks: list[CheckDetail] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    reason: str | None = None
