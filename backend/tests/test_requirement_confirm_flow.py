"""Tests for the requirement confirm/reject flow and the approval gate.

Regression coverage for the approval deadlock: a high-criticality requirement
could never become "confirmed" because the only place status was set to
"confirmed" was inside the approve step, which was itself blocked until every
high-criticality requirement was already confirmed.

These are UNIT tests using the in-memory SQLite `client` fixture. They do NOT
require Neon or the live AI endpoint.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> str:
    res = client.post(
        "/api/v1/projects",
        json={"name": "Deadlock Test", "initial_description": "d"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def _add_requirement(
    client: TestClient,
    project_id: str,
    code: str,
    *,
    criticality: str = "high",
    status: str = "proposed",
    category: str = "functional",
) -> None:
    res = client.post(
        f"/api/v1/projects/{project_id}/requirements",
        json={
            "code": code,
            "description": f"{code} desc",
            "category": category,
            "source": "user",
            "status": status,
            "criticality": criticality,
        },
    )
    assert res.status_code == 201, res.text


def test_approve_blocked_by_high_criticality_unresolved(client: TestClient) -> None:
    """A high-criticality proposed requirement blocks approval (409)."""
    pid = _create_project(client)
    _add_requirement(client, pid, "REQ-001", criticality="high", status="proposed")

    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 409
    body = res.json()
    assert "critical" in (body.get("error") or body.get("detail") or "").lower()


def test_confirm_then_approve_opens_gate(client: TestClient) -> None:
    """Confirming the high-criticality requirement lets approval succeed."""
    pid = _create_project(client)
    _add_requirement(client, pid, "REQ-001", criticality="high", status="proposed")

    # Confirm the requirement via the new PATCH endpoint.
    res = client.patch(
        f"/api/v1/projects/{pid}/requirements/REQ-001",
        json={"status": "confirmed"},
    )
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "confirmed"

    # Completeness no longer reports it as critical-unresolved.
    comp = client.get(f"/api/v1/projects/{pid}/requirements/completeness").json()
    assert "REQ-001" not in comp["critical_unresolved"]

    # Approval now succeeds.
    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "approved"


def test_reject_high_criticality_also_opens_gate(client: TestClient) -> None:
    """Rejecting a high-criticality requirement also clears the gate."""
    pid = _create_project(client)
    _add_requirement(client, pid, "REQ-001", criticality="high", status="proposed")

    res = client.patch(
        f"/api/v1/projects/{pid}/requirements/REQ-001",
        json={"status": "rejected"},
    )
    assert res.status_code == 200, res.text

    # Approval succeeds (rejected requirements are excluded from the gate).
    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 200, res.text


def test_patch_invalid_status_rejected(client: TestClient) -> None:
    """An invalid status value is rejected with 422."""
    pid = _create_project(client)
    _add_requirement(client, pid, "REQ-001", criticality="high", status="proposed")

    res = client.patch(
        f"/api/v1/projects/{pid}/requirements/REQ-001",
        json={"status": "not_a_real_status"},
    )
    assert res.status_code == 422


def test_patch_missing_requirement_404(client: TestClient) -> None:
    """PATCHing a non-existent requirement code returns 404."""
    pid = _create_project(client)
    res = client.patch(
        f"/api/v1/projects/{pid}/requirements/DOES-NOT-EXIST",
        json={"status": "confirmed"},
    )
    assert res.status_code == 404


def test_multiple_high_criticality_all_must_be_resolved(client: TestClient) -> None:
    """All high-criticality requirements must be resolved, not just one."""
    pid = _create_project(client)
    _add_requirement(client, pid, "REQ-001", criticality="high", status="proposed")
    _add_requirement(client, pid, "REQ-002", criticality="high", status="proposed")

    # Confirm only one -> still blocked.
    client.patch(
        f"/api/v1/projects/{pid}/requirements/REQ-001",
        json={"status": "confirmed"},
    )
    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 409

    # Confirm the second -> approval succeeds.
    client.patch(
        f"/api/v1/projects/{pid}/requirements/REQ-002",
        json={"status": "confirmed"},
    )
    res = client.post(f"/api/v1/projects/{pid}/requirements/approve")
    assert res.status_code == 200, res.text
