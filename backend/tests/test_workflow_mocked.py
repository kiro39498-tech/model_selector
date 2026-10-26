"""Mocked end-to-end workflow tests.

These tests use an in-memory SQLite database and a mocked AI service.
They do NOT require Neon or the live Qwen endpoint. They verify the
application's behavior and contracts, NOT live integration.
"""
from __future__ import annotations

from tests.sample_payloads import sample_analysis_payload, sample_discovery_payload


def _create_project(client, name="Test App", desc="A support assistant") -> str:
    res = client.post(
        "/api/v1/projects",
        json={"name": name, "initial_description": desc},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


# ---------------------------------------------------------------------------
# Project creation and persistence
# ---------------------------------------------------------------------------
def test_project_creation_and_persistence(client) -> None:
    pid = _create_project(client)
    # Persisted and retrievable.
    got = client.get(f"/api/v1/projects/{pid}")
    assert got.status_code == 200
    body = got.json()
    assert body["id"] == pid
    assert body["name"] == "Test App"
    assert body["status"] == "discovery"
    # Listed.
    listed = client.get("/api/v1/projects").json()
    assert any(p["id"] == pid for p in listed)


def test_project_not_found(client) -> None:
    res = client.get("/api/v1/projects/does-not-exist")
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Requirements discovery and follow-up questions
# ---------------------------------------------------------------------------
def test_discovery_returns_questions_and_persists_requirements(client, mock_ai) -> None:
    pid = _create_project(client)
    mock_ai.payload = sample_discovery_payload()

    res = client.post(
        f"/api/v1/projects/{pid}/requirements/discovery",
        json={"message": "I want a support assistant that classifies intent."},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["questions"] == ["Who are the target users?"]
    assert len(body["requirements"]) == 1

    # The extracted requirement is persisted.
    reqs = client.get(f"/api/v1/projects/{pid}/requirements").json()
    assert len(reqs) == 1
    assert reqs[0]["code"] == "REQ-001"
    assert reqs[0]["source"] == "user"


def test_discovery_dedupes_requirements(client, mock_ai) -> None:
    pid = _create_project(client)
    mock_ai.payload = sample_discovery_payload()
    client.post(
        f"/api/v1/projects/{pid}/requirements/discovery",
        json={"message": "first"},
    )
    client.post(
        f"/api/v1/projects/{pid}/requirements/discovery",
        json={"message": "second"},
    )
    reqs = client.get(f"/api/v1/projects/{pid}/requirements").json()
    # Same code is not duplicated.
    assert len(reqs) == 1


# ---------------------------------------------------------------------------
# Completeness and approval
# ---------------------------------------------------------------------------
def test_completeness_by_category(client) -> None:
    pid = _create_project(client)
    res = client.get(f"/api/v1/projects/{pid}/requirements/completeness")
    assert res.status_code == 200
    body = res.json()
    # No requirements yet -> every category is 0.0 and not ready.
    assert body["ready_for_approval"] is False
    assert body["by_category"]["ai"] == 0.0


def test_approve_creates_version_and_sets_status(client) -> None:
    pid = _create_project(client)
    # Add a confirmed requirement directly (no high-criticality blocker).
    client.post(
        f"/api/v1/projects/{pid}/requirements",
        json={
            "code": "REQ-001",
            "description": "Classify intent.",
            "category": "ai",
            "status": "confirmed",
            "criticality": "medium",
        },
    )
    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"
    # Project status is now approved.
    assert client.get(f"/api/v1/projects/{pid}").json()["status"] == "approved"


# ---------------------------------------------------------------------------
# Prevention of analysis when critical requirements are unresolved
# ---------------------------------------------------------------------------
def test_analysis_blocked_before_approval(client, mock_ai) -> None:
    pid = _create_project(client)
    mock_ai.payload = sample_analysis_payload()
    # Project is in "discovery" status, not approved.
    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 409
    assert "approved" in res.json().get("error", "")


def test_approve_blocked_when_critical_unresolved(client) -> None:
    pid = _create_project(client)
    # A high-criticality requirement that is not confirmed.
    client.post(
        f"/api/v1/projects/{pid}/requirements",
        json={
            "code": "REQ-001",
            "description": "Critical security requirement.",
            "category": "non_functional",
            "status": "proposed",
            "criticality": "high",
        },
    )
    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 409
    assert "critical" in res.json().get("error", "").lower()


# ---------------------------------------------------------------------------
# Architecture generation and component-level recommendations
# ---------------------------------------------------------------------------
def _approve_project(client, pid: str) -> None:
    client.post(
        f"/api/v1/projects/{pid}/requirements",
        json={
            "code": "REQ-001",
            "description": "Classify intent.",
            "category": "ai",
            "status": "confirmed",
            "criticality": "medium",
        },
    )
    client.post(f"/api/v1/projects/{pid}/requirements/approve")


def _patch_session_factory(monkeypatch, db_engine) -> None:
    """Point the background analysis worker at the in-memory engine."""
    from sqlalchemy.orm import sessionmaker

    from app.routers import analysis as analysis_mod

    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    monkeypatch.setattr(analysis_mod, "get_session_factory", lambda: factory)


def test_analysis_generates_components_and_recommendations(
    client, db_engine, mock_ai, monkeypatch
) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    pid = _create_project(client)
    _approve_project(client, pid)
    mock_ai.payload = sample_analysis_payload()

    # POST returns 202 immediately with a 'running' run.
    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 202, res.text
    assert res.json()["status"] == "running"

    # The background task completes; poll the run detail for the result.
    run_id = res.json()["id"]
    detail = client.get(f"/api/v1/projects/{pid}/analysis/{run_id}").json()
    assert detail["run"]["status"] == "completed"
    assert detail["result"] is not None
    assert len(detail["result"]["components"]) == 1
    comp = detail["result"]["components"][0]
    assert comp["ai_required"] is True
    assert len(comp["model_recommendations"]) == 3


def test_three_ranked_recommendations_rendered(
    client, db_engine, mock_ai, monkeypatch
) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    pid = _create_project(client)
    _approve_project(client, pid)
    mock_ai.payload = sample_analysis_payload()
    res = client.post(f"/api/v1/projects/{pid}/analysis")
    run_id = res.json()["id"]

    # Fetch the run and confirm three ranked recommendations.
    result = client.get(f"/api/v1/projects/{pid}/analysis/{run_id}").json()
    recs = result["result"]["components"][0]["model_recommendations"]
    assert [r["rank"] for r in recs] == [1, 2, 3]
    # All three are verified against the registry.
    assert all(r["verified"] for r in recs)


# ---------------------------------------------------------------------------
# SLM/LLM classification at the 150B threshold
# ---------------------------------------------------------------------------
def test_classification_at_150b_threshold(client) -> None:
    # 150B exactly is an LLM; 149B is an SLM; 27B is an SLM.
    from app.services.classification import classify_billions

    assert classify_billions(150.0)[0] == "LLM"
    assert classify_billions(149.0)[0] == "SLM"
    assert classify_billions(27.0)[0] == "SLM"
    assert classify_billions(200.0)[0] == "LLM"
    assert classify_billions(None)[0] == "unknown"


# ---------------------------------------------------------------------------
# No fabricated results when the AI service is unavailable
# ---------------------------------------------------------------------------
def test_analysis_unavailable_returns_503_not_fabricated(
    client, db_engine, mock_ai_unavailable, monkeypatch
) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    pid = _create_project(client)
    _approve_project(client, pid)

    # POST returns 202 (analysis is async); the failure surfaces on the run.
    res = client.post(f"/api/v1/projects/{pid}/analysis")
    assert res.status_code == 202
    run_id = res.json()["id"]

    # The run is recorded as failed, with no fabricated result.
    detail = client.get(f"/api/v1/projects/{pid}/analysis/{run_id}").json()
    assert detail["run"]["status"] == "failed"
    assert detail["run"]["error"]
    assert detail["result"] is None


def test_discovery_unavailable_returns_503(client, mock_ai_unavailable) -> None:
    pid = _create_project(client)
    res = client.post(
        f"/api/v1/projects/{pid}/requirements/discovery",
        json={"message": "hello"},
    )
    assert res.status_code == 503


def test_health_reports_config_status_without_secrets(client) -> None:
    res = client.get("/health")
    assert res.status_code == 200
    body = res.json()
    assert "ai_configured" in body
    assert "db_configured" in body
    # No secret values are exposed.
    assert "ai_api_key" not in body
    assert "database_url" not in body
