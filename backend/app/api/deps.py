from collections.abc import Generator

from sqlalchemy.orm import Session

from app.core.model_client import ModelClient, get_model_client
from app.storage.db import get_session


def get_db() -> Generator[Session, None, None]:
    db = get_session()
    try:
        yield db
    finally:
        db.close()


def get_client() -> ModelClient:
    return get_model_client()
