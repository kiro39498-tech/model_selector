"""Tests for the asynchronous analysis flow (202 + polling).

These are UNIT tests using the in-memory SQLite `client` fixture and a mocked
AI service. They do NOT require Neon or the live Qwen endpoint.

The analysis endpoint now returns 202 immediately and runs the heavy AI work in
the background. The background worker uses `get_session_factory()` (not the
`get_db` dependency), so these tests patch it to the in-memory engine.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.routers import analysis as analysis_mod
from tests.sample_payloads import sample_analysis_payload


def _patch_session_factory(
    monkeypatch: pytest.MonkeyPatch, engine: object
) -> None:
    """Point the background worker's session factory at the in-memory engine."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(analysis_mod, "get_session_factory", lambda: factory)


def _approved_project(client: TestClient) -> str:
    pid = client.post(
        "/api/v1/projects",
        json={"name": "Async Test", "initial_description": "d"},
    ).json()["id"]
    # Approve (no critical requirements -> gate opens).
    client.post(f"/api/v1/projects/{pid}/requirements/approve")
    return pid


def test_analysis_returns_202_running(
    client: TestClient, db_engine, mock_ai, monkeypatch
) -> None:
    """POST /analysis returns 202 immediately with a 'running' run.

    The AI is mocked so the background task completes quickly and never calls
    the real endpoint.
    """
    _patch_session_factory(monkeypatch, db_engine)
    mock_ai.payload = sample_analysis_payload()
    pid = _approved_project(client)

    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "running"
    assert body["id"]


def test_analysis_completes_in_background(
    client: TestClient, db_engine, mock_ai, monkeypatch
) -> None:
    """After the background task, the run is 'completed' with a result."""
    _patch_session_factory(monkeypatch, db_engine)
    pid = _approved_project(client)
    mock_ai.payload = sample_analysis_payload()

    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 202
    run_id = res.json()["id"]

    # The background task runs synchronously under TestClient; the run is done.
    detail = client.get(f"/api/v1/projects/{pid}/analysis/{run_id}").json()
    assert detail["run"]["status"] == "completed"
    assert detail["result"] is not None
    assert detail["result"]["components"]


def test_analysis_failed_when_ai_unavailable(
    client: TestClient, db_engine, mock_ai_unavailable, monkeypatch
) -> None:
    """A failed AI call leaves the run 'failed' (not stuck 'running')."""
    _patch_session_factory(monkeypatch, db_engine)
    pid = _approved_project(client)

    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 202
    run_id = res.json()["id"]

    detail = client.get(f"/api/v1/projects/{pid}/analysis/{run_id}").json()
    assert detail["run"]["status"] == "failed"
    assert detail["run"]["error"] is not None
    # No fabricated result on failure.
    assert detail["result"] is None


def test_analysis_blocked_before_approval(
    client: TestClient, db_engine, monkeypatch
) -> None:
    """Analysis is blocked (409) until requirements are approved."""
    _patch_session_factory(monkeypatch, db_engine)
    pid = client.post(
        "/api/v1/projects",
        json={"name": "Not Approved", "initial_description": "d"},
    ).json()["id"]

    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 409
