import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.storage.db import Base


@pytest.fixture()
def db_session():
    """An isolated in-memory SQLite DB per test — never touches the
    real backend/storage/finrecon.db file."""
    from app.storage import models  # noqa: F401  (register tables on Base)

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(bind=engine)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()
