from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_client, get_db
from app.chat.service import ask
from app.core.model_client import ModelClient
from app.models.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/reconciliation", tags=["chat"])


@router.post("/jobs/{job_id}/chat", response_model=ChatResponse)
def chat(
    job_id: str,
    request: ChatRequest,
    db: Session = Depends(get_db),
    client: ModelClient = Depends(get_client),
) -> ChatResponse:
    return ask(db, job_id, request, client)
