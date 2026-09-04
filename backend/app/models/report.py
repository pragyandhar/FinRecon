from pydantic import BaseModel, Field

from app.models.investigation import ExceptionExplanation
from app.models.result import ReconciliationResult


class Metrics(BaseModel):
    """Every field here is computed by code from ReconciliationResult
    rows — never guessed or asserted by a model."""

    total_records: int
    matched: int
    mismatched: int
    exceptions: int
    unresolved: int
    match_rate: float
    mismatch_rate: float
    exception_rate: float
    unresolved_rate: float
    total_variance_amount: float = 0.0


class Report(BaseModel):
    job_id: str
    generated_at: str
    metrics: Metrics
    results: list[ReconciliationResult] = Field(default_factory=list)
    exception_explanations: list[ExceptionExplanation] = Field(default_factory=list)
    ai_calls_made: int = 0
