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


class StepMetrics(Metrics):
    """Metrics scoped to one plan step (one check), e.g. "order_amount
    vs payment_amount". A job's overall Metrics sums across every check
    a plan ran — if a plan runs two distinct comparisons over the same
    100 records, that's 200 combined results by design, not a bug. But
    a single blended match rate over that combined total would hide
    which specific relationship is actually broken, so this breakdown
    is what the report and dashboard should lead with."""

    step_id: str
    rule_applied: str


class Report(BaseModel):
    job_id: str
    generated_at: str
    metrics: Metrics
    by_step: list[StepMetrics] = Field(default_factory=list)
    results: list[ReconciliationResult] = Field(default_factory=list)
    exception_explanations: list[ExceptionExplanation] = Field(default_factory=list)
    ai_calls_made: int = 0
