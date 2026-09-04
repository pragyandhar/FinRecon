from pydantic import BaseModel, Field


class ExceptionExplanation(BaseModel):
    """Output of the exception investigator for one EXCEPTION record.
    Evidence-grounded only — never fabricated. If the model cannot
    ground an explanation in the evidence it was given, `resolved` is
    False and `reason` says so explicitly rather than guessing."""

    record_id: str
    reason: str
    evidence_used: list[str] = Field(default_factory=list)
    likely_cause: str | None = None
    recommended_action: str | None = None
    confidence: float = 0.0
    resolved: bool = True
