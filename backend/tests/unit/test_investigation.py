"""Regression tests for the exception-investigation budget cap.

The real-world incident this guards against: a plan that (for whatever
reason) produces far more EXCEPTION records than expected must never
turn into an unbounded number of AI calls. investigate_exceptions must
cap how many exceptions it ever sends to the model, no matter how many
exist, and account for every record either way -- investigated or
explicitly marked as skipped-for-budget, never silently dropped.
"""

from app.core.config import settings
from app.core.model_client import FakeModelClient
from app.investigation.service import investigate_exceptions
from app.models.result import ReconciliationResult


def _exception(record_id: str) -> ReconciliationResult:
    return ReconciliationResult(
        record_id=record_id, job_id="job_test", step_id="s1", status="EXCEPTION",
        rule_applied="MISSING:right", checks=[], reason="no counterpart found",
    )


def test_exceptions_beyond_the_cap_are_never_sent_to_the_model(db_session, monkeypatch):
    monkeypatch.setattr(settings, "max_exceptions_to_investigate", 200)
    total = 250
    results = [_exception(f"payment_id:PAY{i:04d}") for i in range(total)]
    client = FakeModelClient()  # no canned response needed -- see below

    explanations = investigate_exceptions(db_session, "job_test", results, client)

    # Every exception is accounted for, none silently dropped.
    assert len(explanations) == total

    # Only ceil(200 / 25) = 8 batches ever reached the model.
    assert len(client.calls) == 8

    by_id = {e.record_id: e for e in explanations}
    investigated_ids = {r.record_id for r in results[:200]}
    skipped_ids = {r.record_id for r in results[200:]}

    for record_id in skipped_ids:
        assert by_id[record_id].resolved is False
        assert "cap" in by_id[record_id].reason.lower()

    # None of the skipped record_ids were ever included in a model call.
    all_call_text = " ".join(c["user"] for c in client.calls)
    for record_id in skipped_ids:
        assert record_id not in all_call_text
    for record_id in investigated_ids:
        assert record_id in all_call_text


def test_small_exception_count_is_unaffected_by_the_cap(db_session, monkeypatch):
    monkeypatch.setattr(settings, "max_exceptions_to_investigate", 200)
    results = [_exception(f"payment_id:PAY{i:04d}") for i in range(5)]
    client = FakeModelClient()

    explanations = investigate_exceptions(db_session, "job_test", results, client)

    assert len(explanations) == 5
    assert len(client.calls) == 1
    assert all("cap" not in e.reason.lower() for e in explanations)
