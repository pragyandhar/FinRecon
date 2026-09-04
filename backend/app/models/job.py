from pydantic import BaseModel

from app.models.enums import JobStatus


class Job(BaseModel):
    job_id: str
    status: JobStatus
    created_at: str
    updated_at: str
    error_code: str | None = None
    error_message: str | None = None
