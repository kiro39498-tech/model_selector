"""Shared pytest fixtures.

Test isolation strategy (see pytest.ini):
- Mocked tests use an in-memory SQLite database and a mocked AI service.
  They do NOT require Neon or the live Qwen endpoint.
- Live integration tests (marked `live`) require a real DATABASE_URL and
  AI_API_KEY and are SKIPPED by default.

The FastAPI `get_db` dependency is overridden to use a per-test SQLite
session, so no real database connection is ever attempted in mocked tests.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base


# ---------------------------------------------------------------------------
# Markers
# ---------------------------------------------------------------------------
def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "live: requires a real Neon DATABASE_URL and AI_API_KEY; skipped by default",
    )


# ---------------------------------------------------------------------------
# Database (in-memory SQLite)
# ---------------------------------------------------------------------------
@pytest.fixture()
def db_engine() -> Iterator[Any]:
    """Create a fresh in-memory SQLite engine for each test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture()
def db_session(db_engine: Any) -> Iterator[Session]:
    """Yield a single session bound to the in-memory engine."""
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db_engine: Any) -> Iterator[TestClient]:
    """TestClient with get_db overridden to a fresh session per request.

    Each request gets its own session bound to the shared in-memory engine,
    mirroring the real application's per-request session lifecycle. This means
    committed data from one request is visible to the next (same engine).
    """
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)

    def _override_get_db() -> Iterator[Session]:
        session = factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# AI service mocking
# ---------------------------------------------------------------------------
class _AIResponse:
    """A deterministic stand-in for the AI service's chat_json output."""

    def __init__(self, payload: dict[str, Any], *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    def __call__(
        self,
        messages: list[dict[str, str]],
        validator: Any,
        **kwargs: Any,
    ) -> tuple[Any, dict[str, Any]]:
        if self.fail:
            from app.services.ai_service import AIServiceError

            raise AIServiceError("mocked AI service unavailable")
        # Emulate chat_json: validate the JSON string with the provided validator.
        raw = json.dumps(self.payload)
        model = validator(raw)
        return model, {"correlation_id": "test", "attempts": 1}


@pytest.fixture()
def mock_ai(monkeypatch: pytest.MonkeyPatch) -> _AIResponse:
    """Patch chat_json in the discovery and analysis modules.

    Returns a controllable response object. Tests set `.payload` / `.fail`.
    """
    resp = _AIResponse({})
    monkeypatch.setattr("app.routers.analysis.chat_json", resp)
    monkeypatch.setattr("app.services.discovery.chat_json", resp)
    return resp


@pytest.fixture()
def mock_ai_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force the AI service to be unavailable (simulates missing creds / 503)."""

    def _unavailable(*args: Any, **kwargs: Any) -> Any:
        from app.services.ai_service import AIServiceError

        raise AIServiceError("AI service is not configured. Set AI_API_KEY.")

    monkeypatch.setattr("app.routers.analysis.chat_json", _unavailable)
    monkeypatch.setattr("app.services.discovery.chat_json", _unavailable)
