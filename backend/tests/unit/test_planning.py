import pytest

from app.core.config import settings
from app.core.errors import InvalidReconciliationPlanError
from app.core.model_client import FakeModelClient
from app.models.dataset import Dataset, DatasetColumn
from app.models.schema import CanonicalMapping, SchemaDataset, SchemaField, SchemaJSON
from app.planning.service import generate_validated_plan

SCHEMA = SchemaJSON(
    job_id="job_test",
    datasets=[
        SchemaDataset(dataset_id="payments", purpose="p", fields=[SchemaField(name="Txn ID", semantic_type="identifier", role="primary_key")]),
        SchemaDataset(dataset_id="settlements", purpose="s", fields=[SchemaField(name="Ref", semantic_type="identifier", role="primary_key")]),
    ],
)
CANONICAL = CanonicalMapping(
    job_id="job_test",
    mapping={"payments": {"payment_id": "Txn ID"}, "settlements": {"payment_id": "Ref"}},
)
DATASETS = [
    Dataset(dataset_id="payments", job_id="job_test", source_file="payments.csv", columns=[DatasetColumn(name="Txn ID", raw_type="string")], row_count=2),
    Dataset(dataset_id="settlements", job_id="job_test", source_file="settlements.csv", columns=[DatasetColumn(name="Ref", raw_type="string")], row_count=2),
]

VALID_PLAN = {
    "steps": [
        {"step_id": "s1", "operation": "JOIN", "left": "payments", "right": "settlements", "left_field": "payment_id", "right_field": "payment_id"},
    ]
}
# Missing left_field/right_field -> validator rejects this.
INVALID_PLAN = {"steps": [{"step_id": "s1", "operation": "JOIN", "left": "payments", "right": "settlements"}]}


def test_valid_plan_on_first_try(db_session):
    client = FakeModelClient({"reconciliation_planning": VALID_PLAN})
    plan, validation = generate_validated_plan(db_session, "job_test", SCHEMA, CANONICAL, DATASETS, client)
    assert validation.is_valid
    assert len(client.calls) == 1


def test_repairs_after_one_invalid_attempt(db_session):
    client = FakeModelClient({"reconciliation_planning": [INVALID_PLAN, VALID_PLAN]})
    plan, validation = generate_validated_plan(db_session, "job_test", SCHEMA, CANONICAL, DATASETS, client)
    assert validation.is_valid
    assert len(client.calls) == 2
    # the repair prompt must carry the validator's error back to the model
    assert "left_field" in client.calls[1]["user"]


def test_gives_up_after_max_retries(db_session, monkeypatch):
    monkeypatch.setattr(settings, "max_plan_retries", 1)
    client = FakeModelClient({"reconciliation_planning": INVALID_PLAN})
    with pytest.raises(InvalidReconciliationPlanError):
        generate_validated_plan(db_session, "job_test", SCHEMA, CANONICAL, DATASETS, client)
    assert len(client.calls) == 2  # 1 initial + 1 retry, then it stops
