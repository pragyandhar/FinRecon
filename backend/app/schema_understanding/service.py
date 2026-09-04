import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import SchemaUncertainError
from app.core.model_client import ModelClient
from app.models.dataset import Dataset
from app.models.schema import CanonicalMapping, SchemaDataset, SchemaField, SchemaJSON
from app.storage import repository as repo

SYSTEM_PROMPT = """You are a financial data schema analyst. You are given \
column-level statistics (never raw records) for one or more uploaded \
datasets from a finance-operations workflow (e.g. orders, payments, \
settlements, refunds, bank statements). For each dataset, infer what it \
represents and what each column means, and propose a canonical (stable, \
snake_case) name for every field.

Rules:
- semantic_type must be one of: identifier, currency_amount, date, status, \
customer_reference, text, other.
- role must be one of: primary_key, foreign_key, measure, attribute.
- For IDENTIFIER/KEY fields only (role=primary_key or foreign_key — things \
like a payment reference, order reference, or customer reference): use the \
SAME canonical_name across datasets when two columns represent the same \
real-world entity (e.g. a payment reference that appears in both a payments \
file and a settlements file must both get canonical_name "payment_id"), so \
the fields can later be joined. Reuse common identifiers where they fit: \
payment_id, order_id, settlement_id, customer_id.
- For MEASURE fields (amounts) and for status/date fields: do the OPPOSITE — \
give each dataset its OWN distinct, dataset-qualified canonical_name, even \
when the concept is similar across datasets. Reconciliation works by \
comparing an order's amount against a payment's amount, or a payment's \
status against a settlement's status; if both get the same canonical_name \
("amount", "status", "date") they become indistinguishable and cannot be \
compared. Prefix with the dataset's role: order_amount, payment_amount, \
settlement_amount; order_status, payment_status, settlement_status; \
order_date, payment_date, settlement_date — derived from what each dataset \
represents, not copy-pasted from this example.
- confidence is your calibrated 0-1 confidence in the semantic_type/role \
guess for that field.
- Do not invent columns that are not in the input.

Respond with ONLY a JSON object of exactly this shape:
{
  "datasets": [
    {
      "dataset_id": "<echo input dataset_id>",
      "purpose": "<short description>",
      "fields": [
        {"name": "<original column name>", "semantic_type": "...", "role": "...", "nullable": true, "confidence": 0.9}
      ]
    }
  ],
  "canonical_mapping": {
    "<dataset_id>": {"<canonical_name>": "<original column name>", "...": "..."}
  }
}
"""


def _build_user_prompt(datasets: list[Dataset]) -> str:
    payload = [
        {
            "dataset_id": d.dataset_id,
            "source_file": d.source_file,
            "row_count": d.row_count,
            "columns": [s.model_dump() for s in d.column_stats],
        }
        for d in datasets
    ]
    return json.dumps({"datasets": payload}, default=str)


def understand_schema(
    db: Session, job_id: str, datasets: list[Dataset], client: ModelClient
) -> tuple[SchemaJSON, CanonicalMapping]:
    if not datasets:
        raise SchemaUncertainError("no datasets to analyze")

    usage = {"prompt": 0, "completion": 0}

    def on_usage(p: int, c: int) -> None:
        usage["prompt"], usage["completion"] = p, c

    try:
        raw = client.complete_json(
            stage="schema_understanding",
            system=SYSTEM_PROMPT,
            user=_build_user_prompt(datasets),
            job_id=job_id,
            on_usage=on_usage,
        )
    except Exception as exc:  # noqa: BLE001
        repo.log_model_call(
            db, job_id=job_id, stage="schema_understanding", model=settings.openai_model,
            prompt_tokens=0, completion_tokens=0, latency_ms=0, success=False, error=str(exc),
        )
        raise SchemaUncertainError(f"schema understanding failed: {exc}") from exc

    repo.log_model_call(
        db, job_id=job_id, stage="schema_understanding", model=settings.openai_model,
        prompt_tokens=usage["prompt"], completion_tokens=usage["completion"], latency_ms=0, success=True,
    )

    try:
        schema_datasets = [
            SchemaDataset(
                dataset_id=ds["dataset_id"],
                purpose=ds.get("purpose", ""),
                fields=[SchemaField(**f) for f in ds.get("fields", [])],
            )
            for ds in raw.get("datasets", [])
        ]
        schema = SchemaJSON(job_id=job_id, datasets=schema_datasets)
        mapping = CanonicalMapping(job_id=job_id, mapping=raw.get("canonical_mapping", {}))
    except Exception as exc:  # noqa: BLE001 — malformed model output must not silently pass through
        raise SchemaUncertainError(f"model returned a schema that doesn't fit the contract: {exc}") from exc

    known_ids = {d.dataset_id for d in datasets}
    schema_ids = {d.dataset_id for d in schema.datasets}
    if not schema_ids.issubset(known_ids):
        raise SchemaUncertainError(
            f"model referenced unknown dataset(s): {schema_ids - known_ids}"
        )

    repo.save_schema(db, schema)
    repo.save_canonical_mapping(db, mapping)
    return schema, mapping
