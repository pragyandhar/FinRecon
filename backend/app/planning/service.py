import json

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import InvalidReconciliationPlanError
from app.core.model_client import ModelClient
from app.models.dataset import Dataset
from app.models.plan import ReconciliationPlan
from app.models.schema import CanonicalMapping, SchemaJSON
from app.models.validation import ValidationResult
from app.storage import repository as repo
from app.validation.contracts import describe_operations
from app.validation.service import validate_plan

SYSTEM_PROMPT_TEMPLATE = """You are a financial reconciliation planning \
agent. You design a reconciliation plan as a sequence of steps drawn ONLY \
from this fixed operation vocabulary — you may not invent new operations \
or execute anything yourself:

{operations}

All field references (left_field, right_field, field_a, field_b, fields, \
group_by, agg_field) must use the CANONICAL field names given to you, not \
the original column names. `left`/`right`/`input` reference either a \
dataset_id or an earlier step's step_id (steps run in the order listed, \
so a step may reference any step_id defined before it).

Design a plan that: joins datasets that should reconcile with each other, \
compares the amount/measure fields that should agree (use TOLERANCE with a \
sensible tolerance, default {default_tolerance} if you have no better \
signal), and flags MISSING counterparts and DUPLICATE keys where relevant. \
Prefer a small number of clear steps over an exhaustive one.

Respond with ONLY a JSON object of exactly this shape:
{{"steps": [{{"step_id": "s1", "operation": "JOIN", "left": "...", "right": "...", "left_field": "...", "right_field": "...", "join_type": "full_outer"}}, ...]}}
"""


def _build_user_prompt(schema: SchemaJSON, canonical_mapping: CanonicalMapping, datasets: list[Dataset]) -> str:
    row_counts = {d.dataset_id: d.row_count for d in datasets}
    payload = []
    for ds in schema.datasets:
        payload.append(
            {
                "dataset_id": ds.dataset_id,
                "purpose": ds.purpose,
                "row_count": row_counts.get(ds.dataset_id),
                "canonical_fields": sorted(canonical_mapping.mapping.get(ds.dataset_id, {}).keys()),
            }
        )
    return json.dumps({"datasets": payload})


def _repair_prompt(previous_steps: list[dict], validation: ValidationResult) -> str:
    errors = [f"step '{i.step_id}' field '{i.field}': {i.message}" for i in validation.issues]
    return json.dumps(
        {
            "previous_plan": {"steps": previous_steps},
            "validation_errors": errors,
            "instruction": "Fix every listed error and return a corrected, complete plan in the same JSON shape.",
        }
    )


def generate_validated_plan(
    db: Session,
    job_id: str,
    schema: SchemaJSON,
    canonical_mapping: CanonicalMapping,
    datasets: list[Dataset],
    client: ModelClient,
) -> tuple[ReconciliationPlan, ValidationResult]:
    system = SYSTEM_PROMPT_TEMPLATE.format(
        operations=describe_operations(), default_tolerance=settings.default_amount_tolerance
    )
    user = _build_user_prompt(schema, canonical_mapping, datasets)
    dataset_ids = {d.dataset_id for d in datasets}

    plan_version = 1
    last_validation: ValidationResult | None = None
    raw_steps: list[dict] = []

    max_attempts = settings.max_plan_retries + 1
    for attempt in range(max_attempts):
        usage = {"prompt": 0, "completion": 0}

        def on_usage(p: int, c: int) -> None:
            usage["prompt"], usage["completion"] = p, c

        prompt = user if attempt == 0 else _repair_prompt(raw_steps, last_validation)
        try:
            raw = client.complete_json(
                stage="reconciliation_planning", system=system, user=prompt, job_id=job_id, on_usage=on_usage
            )
            repo.log_model_call(
                db, job_id=job_id, stage="reconciliation_planning", model=settings.openai_model,
                prompt_tokens=usage["prompt"], completion_tokens=usage["completion"], latency_ms=0, success=True,
            )
        except Exception as exc:  # noqa: BLE001
            repo.log_model_call(
                db, job_id=job_id, stage="reconciliation_planning", model=settings.openai_model,
                prompt_tokens=0, completion_tokens=0, latency_ms=0, success=False, error=str(exc),
            )
            raise InvalidReconciliationPlanError(f"planning call failed: {exc}") from exc

        raw_steps = raw.get("steps", [])
        try:
            plan = ReconciliationPlan(job_id=job_id, plan_version=plan_version, steps=raw_steps)
        except ValidationError as exc:
            last_validation = ValidationResult(
                job_id=job_id,
                plan_version=plan_version,
                is_valid=False,
                issues=[{"message": f"plan JSON did not fit the contract: {exc}"}],
            )
            plan_version += 1
            continue

        validation = validate_plan(plan, canonical_mapping, dataset_ids)
        last_validation = validation
        repo.save_plan(db, plan)
        repo.save_validation_result(db, validation)
        if validation.is_valid:
            return plan, validation
        plan_version += 1

    raise InvalidReconciliationPlanError(
        f"planner could not produce a valid plan in {max_attempts} attempt(s): "
        f"{[i.message for i in last_validation.issues]}"
    )
