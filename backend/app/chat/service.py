import json

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.errors import ModelExecutionFailedError
from app.core.model_client import ModelClient
from app.core.util import new_id
from app.models.chat import ChatMessage, ChatRequest, ChatResponse
from app.storage import repository as repo

SYSTEM_PROMPT = """You are FinRecon's contextual report assistant. You \
answer questions about ONE reconciliation job using only the context \
given to you below (a specific record's result/evidence/AI explanation, \
or job-level metrics) — never the full dataset, which you do not have. \
If the context doesn't contain enough information to answer, say so \
plainly instead of guessing. Be concise and factual.

If given job-level context: "combined_metrics" is the sum across every \
distinct check the reconciliation plan ran (e.g. if the plan compared \
order_amount vs payment_amount AND separately payment_amount vs \
settlement_amount, combined totals add both together, so a record count \
can legitimately exceed the number of rows in any one input file). \
"metrics_by_check" breaks that same total down per individual check — use \
it to explain apparent discrepancies in the combined numbers, or to say \
which specific check is driving a low match rate.

Respond with ONLY a JSON object: {"reply": "<your answer>"}
"""


def _find_context(db: Session, job_id: str, request: ChatRequest) -> tuple[dict, list[str]]:
    results = repo.get_results(db, job_id)

    target = None
    if request.record_id:
        target = next((r for r in results if r.record_id == request.record_id), None)
    else:
        target = next(
            (r for r in results if r.record_id in request.message or r.record_id.split(":")[-1] in request.message),
            None,
        )

    if target is not None:
        context: dict = {"result": target.model_dump(mode="json")}
        used = [f"result:{target.record_id}"]
        explanation = repo.get_exception_explanation(db, job_id, target.record_id)
        if explanation is not None:
            context["explanation"] = explanation.model_dump(mode="json")
            used.append(f"explanation:{target.record_id}")
        return context, used

    report = repo.get_report(db, job_id)
    if report is not None:
        return (
            {
                "combined_metrics": report.metrics.model_dump(mode="json"),
                "metrics_by_check": [s.model_dump(mode="json") for s in report.by_step],
            },
            ["metrics", "by_step"],
        )
    return {}, []


def ask(db: Session, job_id: str, request: ChatRequest, client: ModelClient) -> ChatResponse:
    if not settings.enable_chat:
        raise ModelExecutionFailedError("chat is disabled (ENABLE_CHAT=false)")

    session_id = request.session_id or new_id("chat")
    if not repo.chat_session_exists(db, session_id):
        repo.create_chat_session(db, session_id, job_id)

    history = repo.get_chat_history(db, session_id)
    context, context_used = _find_context(db, job_id, request)

    user_prompt = json.dumps(
        {
            "question": request.message,
            "context": context,
            "recent_history": [h.model_dump() for h in history[-6:]],
        },
        default=str,
    )

    repo.add_chat_message(db, session_id, ChatMessage(role="user", content=request.message))

    usage = {"prompt": 0, "completion": 0}

    def on_usage(p: int, c: int) -> None:
        usage["prompt"], usage["completion"] = p, c

    try:
        raw = client.complete_json(
            stage="chat", system=SYSTEM_PROMPT, user=user_prompt, job_id=job_id, on_usage=on_usage
        )
        reply = raw.get("reply", "")
        repo.log_model_call(
            db, job_id=job_id, stage="chat", model=settings.openai_model,
            prompt_tokens=usage["prompt"], completion_tokens=usage["completion"], latency_ms=0, success=True,
        )
    except Exception as exc:  # noqa: BLE001
        repo.log_model_call(
            db, job_id=job_id, stage="chat", model=settings.openai_model,
            prompt_tokens=0, completion_tokens=0, latency_ms=0, success=False, error=str(exc),
        )
        raise ModelExecutionFailedError(f"chat call failed: {exc}") from exc

    repo.add_chat_message(db, session_id, ChatMessage(role="assistant", content=reply))
    return ChatResponse(session_id=session_id, reply=reply, context_used=context_used)
