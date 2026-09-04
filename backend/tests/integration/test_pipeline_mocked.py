"""End-to-end pipeline test: upload -> extract -> schema understanding ->
canonicalization -> planning -> validation -> execution -> investigation
-> report -> chat. Every AI call goes through FakeModelClient with canned
responses, so this test spends zero real API budget while still proving
the whole wiring works, not just isolated units.
"""

import pytest

from app.chat.service import ask as chat_ask
from app.core.config import settings
from app.core.model_client import FakeModelClient
from app.execution.service import execute_plan
from app.investigation.service import investigate_exceptions
from app.ingestion.service import ingest_uploaded_files
from app.models.chat import ChatRequest
from app.planning.service import generate_validated_plan
from app.reporting.service import generate_report
from app.schema_understanding.service import understand_schema

PAYMENTS_CSV = b"Txn ID,Amount Paid\nTX1,1000\nTX2,500\nTX3,200\n"
SETTLEMENTS_CSV = b"Settlement Ref,Net Amount\nTX1,997\nTX2,500\n"

SCHEMA_RESPONSE = {
    "datasets": [
        {
            "dataset_id": "payments",
            "purpose": "payment records",
            "fields": [
                {"name": "Txn ID", "semantic_type": "identifier", "role": "primary_key", "nullable": False, "confidence": 0.9},
                {"name": "Amount Paid", "semantic_type": "currency_amount", "role": "measure", "nullable": False, "confidence": 0.9},
            ],
        },
        {
            "dataset_id": "settlements",
            "purpose": "settlement records",
            "fields": [
                {"name": "Settlement Ref", "semantic_type": "identifier", "role": "primary_key", "nullable": False, "confidence": 0.9},
                {"name": "Net Amount", "semantic_type": "currency_amount", "role": "measure", "nullable": False, "confidence": 0.9},
            ],
        },
    ],
    "canonical_mapping": {
        "payments": {"payment_id": "Txn ID", "payment_amount": "Amount Paid"},
        "settlements": {"payment_id": "Settlement Ref", "settlement_amount": "Net Amount"},
    },
}

PLAN_RESPONSE = {
    "steps": [
        {"step_id": "s1", "operation": "JOIN", "left": "payments", "right": "settlements", "left_field": "payment_id", "right_field": "payment_id", "join_type": "full_outer"},
        {"step_id": "s2", "operation": "COMPARE", "input": "s1", "comparison": "TOLERANCE", "field_a": "payment_amount", "field_b": "settlement_amount", "tolerance": 5},
        {"step_id": "s3", "operation": "MISSING", "input": "s1", "side": "right"},
    ]
}

INVESTIGATION_RESPONSE = {
    "explanations": [
        {
            "record_id": "payment_id:TX3",
            "reason": "TX3 has no matching settlement row.",
            "evidence_used": ["payments.payment_id=TX3"],
            "likely_cause": "Settlement not yet processed",
            "recommended_action": "Check settlement batch for TX3",
            "confidence": 0.8,
            "resolved": True,
        }
    ]
}

CHAT_RESPONSE = {"reply": "TX3 could not be reconciled because no settlement record exists for it yet."}


@pytest.fixture(autouse=True)
def _isolated_raw_storage(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "raw_storage_dir", str(tmp_path))


def test_full_pipeline_end_to_end(db_session):
    job_id = "job_e2e"
    from app.storage import repository as repo

    repo.create_job(db_session, job_id)

    datasets = ingest_uploaded_files(
        db_session, job_id, [("payments.csv", PAYMENTS_CSV), ("settlements.csv", SETTLEMENTS_CSV)]
    )
    assert {d.dataset_id for d in datasets} == {"payments", "settlements"}

    client = FakeModelClient(
        {
            "schema_understanding": SCHEMA_RESPONSE,
            "reconciliation_planning": PLAN_RESPONSE,
            "exception_investigation": INVESTIGATION_RESPONSE,
            "chat": CHAT_RESPONSE,
        }
    )

    schema, canonical_mapping = understand_schema(db_session, job_id, datasets, client)
    assert {d.dataset_id for d in schema.datasets} == {"payments", "settlements"}

    plan, validation = generate_validated_plan(db_session, job_id, schema, canonical_mapping, datasets, client)
    assert validation.is_valid
    assert len(plan.steps) == 3

    output = execute_plan(db_session, job_id, plan, canonical_mapping)
    statuses = sorted(r.status for r in output.results)
    assert statuses == ["EXCEPTION", "EXCEPTION", "MATCHED", "MATCHED"]

    explanations = investigate_exceptions(db_session, job_id, output.results, client)
    assert len(explanations) == 2
    assert all(e.record_id == "payment_id:TX3" for e in explanations)
    assert all(e.resolved for e in explanations)

    report = generate_report(db_session, job_id)
    assert report.metrics.total_records == 4
    assert report.metrics.matched == 2
    assert report.metrics.exceptions == 2
    assert report.metrics.match_rate == 0.5
    assert report.ai_calls_made == 3  # schema, planning, investigation

    chat_response = chat_ask(
        db_session, job_id, ChatRequest(message="Why was TX3 flagged?", record_id="payment_id:TX3"), client
    )
    assert "TX3" in chat_response.reply
    assert chat_response.context_used  # scoped context, not the whole dataset
