import os
import tempfile

import pytest
from fastapi.testclient import TestClient

# Point at a temp DB before importing the app.
_fd, _path = tempfile.mkstemp(suffix=".db")
os.close(_fd)
os.environ["RECALL_DATABASE_URL"] = f"sqlite:///{_path}"
os.environ["RECALL_API_TOKEN"] = "test-token"
os.environ["RECALL_RELAX_LOOPBACK_CHECK"] = "false"
# Restrict CORS to the real app origins used in tests.
os.environ["RECALL_CORS_ORIGINS"] = "http://localhost:5173,http://127.0.0.1:5173"

from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.main import app  # noqa: E402

AUTH = {"X-API-Key": "test-token"}


@pytest.fixture(autouse=True)
def _reset_db():
    Base.metadata.drop_all(bind=engine)
    init_db()
    yield


@pytest.fixture
def client():
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        c.headers.update(AUTH)
        yield c


@pytest.fixture
def raw_client():
    """TestClient without default auth headers."""
    with TestClient(app, client=("127.0.0.1", 50000)) as c:
        yield c


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
