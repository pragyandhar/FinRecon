from pydantic import BaseModel, Field


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    session_id: str | None = None
    message: str
    record_id: str | None = None  # scope the question to one record if given


class ChatResponse(BaseModel):
    session_id: str
    reply: str
    context_used: list[str] = Field(default_factory=list)
