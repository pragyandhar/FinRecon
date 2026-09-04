import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.model_client import ModelClient
from app.models.investigation import ExceptionExplanation
from app.models.result import ReconciliationResult
from app.storage import repository as repo

# All EXCEPTION records for a job go into a small number of batched
# calls (not one call per record) to keep AI spend bounded regardless of
# how many exceptions a batch produces.
_BATCH_SIZE = 25

SYSTEM_PROMPT = """You are a financial reconciliation exception investigator. \
You are given a batch of EXCEPTION records, each with the deterministic \
rule that flagged it and the evidence rows involved. Explain each one \
using ONLY the evidence provided — never invent a value, a related \
transaction, or a cause that isn't supported by the evidence.

For each exception, decide if the evidence is sufficient to explain it:
- If yes: resolved=true, give reason/likely_cause/recommended_action grounded \
in the evidence, and confidence in [0,1].
- If the evidence is insufficient to explain it: resolved=false, reason \
should say what's missing, likely_cause/recommended_action may be null, \
confidence should be low.

Respond with ONLY a JSON object of exactly this shape:
{"explanations": [{"record_id": "...", "reason": "...", "evidence_used": ["..."], "likely_cause": "..." or null, "recommended_action": "..." or null, "confidence": 0.0, "resolved": true}]}
"""


def _record_payload(r: ReconciliationResult) -> dict:
    return {
        "record_id": r.record_id,
        "rule_applied": r.rule_applied,
        "reason": r.reason,
        "checks": [c.model_dump() for c in r.checks],
        "evidence": [e.model_dump() for e in r.evidence],
    }


def investigate_exceptions(
    db: Session, job_id: str, results: list[ReconciliationResult], client: ModelClient
) -> list[ExceptionExplanation]:
    exceptions = [r for r in results if r.status == "EXCEPTION"]
    if not exceptions:
        return []

    all_explanations: list[ExceptionExplanation] = []
    for i in range(0, len(exceptions), _BATCH_SIZE):
        batch = exceptions[i : i + _BATCH_SIZE]
        user = json.dumps({"exceptions": [_record_payload(r) for r in batch]}, default=str)

        usage = {"prompt": 0, "completion": 0}

        def on_usage(p: int, c: int) -> None:
            usage["prompt"], usage["completion"] = p, c

        try:
            raw = client.complete_json(
                stage="exception_investigation", system=SYSTEM_PROMPT, user=user, job_id=job_id, on_usage=on_usage
            )
            repo.log_model_call(
                db, job_id=job_id, stage="exception_investigation", model=settings.openai_model,
                prompt_tokens=usage["prompt"], completion_tokens=usage["completion"], latency_ms=0, success=True,
            )
        except Exception as exc:  # noqa: BLE001 — a failed investigation call must not crash the job
            repo.log_model_call(
                db, job_id=job_id, stage="exception_investigation", model=settings.openai_model,
                prompt_tokens=0, completion_tokens=0, latency_ms=0, success=False, error=str(exc),
            )
            all_explanations.extend(
                ExceptionExplanation(
                    record_id=r.record_id,
                    reason=f"investigation call failed: {exc}",
                    resolved=False,
                    confidence=0.0,
                )
                for r in batch
            )
            continue

        by_id = {e["record_id"]: e for e in raw.get("explanations", []) if "record_id" in e}
        for r in batch:
            data = by_id.get(r.record_id)
            if data is None:
                all_explanations.append(
                    ExceptionExplanation(
                        record_id=r.record_id,
                        reason="model did not return an explanation for this record",
                        resolved=False,
                        confidence=0.0,
                    )
                )
            else:
                try:
                    all_explanations.append(ExceptionExplanation(**data))
                except Exception as exc:  # noqa: BLE001
                    all_explanations.append(
                        ExceptionExplanation(
                            record_id=r.record_id,
                            reason=f"model returned a malformed explanation: {exc}",
                            resolved=False,
                            confidence=0.0,
                        )
                    )

    repo.save_exception_explanations(db, job_id, all_explanations)
    return all_explanations
