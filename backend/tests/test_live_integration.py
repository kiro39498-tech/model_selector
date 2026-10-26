"""Live integration tests (GATED).

These tests exercise the REAL Neon PostgreSQL database and the REAL configured
Qwen endpoint. They are SKIPPED by default and only run when:
  - the `live` marker is selected (e.g. `pytest -m live`), AND
  - RUN_LIVE_TESTS=1 is set, AND
  - DATABASE_URL and AI_API_KEY are present in the environment.

These are NOT mocked. A passing result here is evidence of live integration.
A skipped result is NOT evidence of integration.
"""
from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

pytestmark = pytest.mark.live


def _live_enabled() -> bool:
    return (
        os.environ.get("RUN_LIVE_TESTS") == "1"
        and settings.db_configured
        and settings.ai_configured
    )


@pytest.fixture()
def live_client() -> TestClient:
    """A TestClient that uses the REAL database and AI (no overrides)."""
    if not _live_enabled():
        pytest.skip(
            "Live integration requires RUN_LIVE_TESTS=1, DATABASE_URL, and "
            "AI_API_KEY. Skipped by default; not evidence of integration."
        )
    return TestClient(app)


def test_live_db_health(live_client) -> None:
    """The real database is reachable."""
    res = live_client.get("/health/db")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"


def test_live_ai_health(live_client) -> None:
    """The real AI endpoint is reachable."""
    res = live_client.get("/health/ai")
    assert res.status_code == 200
    assert res.json().get("status") == "ok"


def test_live_full_workflow(live_client) -> None:
    """End-to-end against the real Neon DB and Qwen endpoint.

    This is the definitive live integration test. It is intentionally not
    mocked. If it fails, that is a real integration problem, not a mock.
    """
    # 1. Create a project.
    pid = live_client.post(
        "/api/v1/projects",
        json={
            "name": "Live Integration Test",
            "initial_description": "A customer support assistant that classifies "
            "the intent of incoming support messages and drafts replies.",
        },
    ).json()["id"]

    # 2. Run discovery (real AI).
    disc = live_client.post(
        f"/api/v1/projects/{pid}/requirements/discovery",
        json={"message": "It should classify intent and draft a reply."},
    )
    assert disc.status_code == 200, disc.text

    # 3. Approve (requires no unresolved critical requirements).
    #    If discovery produced high-criticality proposed requirements, approval
    #    may be blocked; that is a legitimate, non-fabricated outcome.
    approve = live_client.post(f"/api/v1/projects/{pid}/requirements/approve")
    if approve.status_code == 409:
        pytest.skip(
            "Approval blocked by unresolved critical requirements from live "
            "discovery. Not a failure; requires manual resolution."
        )
    assert approve.status_code == 200, approve.text

    # 4. Run analysis (real AI) and confirm a structured, validated result.
    analysis = live_client.post(f"/api/v1/projects/{pid}/analysis")
    assert analysis.status_code == 202, analysis.text
    body = analysis.json()
    assert body["run"]["status"] == "completed"
    assert body["result"] is not None
    # The result is validated against the Pydantic schema (no arbitrary JSON).
    assert "components" in body["result"]
