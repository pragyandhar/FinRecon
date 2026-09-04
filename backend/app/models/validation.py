from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    step_id: str | None = None
    field: str | None = None
    message: str


class ValidationResult(BaseModel):
    job_id: str
    plan_version: int
    is_valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
