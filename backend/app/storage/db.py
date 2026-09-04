from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import REPO_ROOT, settings


class Base(DeclarativeBase):
    pass


def _resolve_sqlite_url(database_url: str) -> str:
    """A relative sqlite:/// URL must resolve against the repo root, not
    the process's current working directory — otherwise `sqlite:///./x`
    lands in a different place depending on where uvicorn/pytest was
    launched from (e.g. repo root vs backend/)."""

    if not database_url.startswith("sqlite:///") or database_url.startswith("sqlite:////"):
        return database_url  # not sqlite, or already an absolute sqlite path
    relative_path = database_url.removeprefix("sqlite:///")
    absolute_path = (REPO_ROOT / relative_path).resolve()
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{absolute_path}"


_resolved_database_url = _resolve_sqlite_url(settings.database_url)

engine = create_engine(
    _resolved_database_url,
    connect_args={"check_same_thread": False} if _resolved_database_url.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    from app.storage import models  # noqa: F401  (register tables)

    Base.metadata.create_all(bind=engine)


def get_session() -> Session:
    return SessionLocal()
