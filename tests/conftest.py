"""Test configuration for GeoLux.

Matches Stargate patterns: SQLite in-memory test DB, FastAPI TestClient
with dependency override.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from db.database import Base, set_engine, get_db

test_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
set_engine(test_engine)
TestSession = sessionmaker(bind=test_engine)


@pytest.fixture(autouse=True)
def _reset_circuit_breaker():
    """Reset the LLM circuit breaker between tests to prevent test interaction."""
    from api.stability.wrapper import _circuit_breaker
    _circuit_breaker.reset()
    yield
    _circuit_breaker.reset()


@pytest.fixture
def db():
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    yield session
    session.close()
    Base.metadata.drop_all(bind=test_engine)


def _override_get_db():
    Base.metadata.create_all(bind=test_engine)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    from api.app import app
    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
