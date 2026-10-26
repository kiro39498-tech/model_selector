"""Tests for the orchestrator (AI-driven, conversational SLM/LLM decision).

These are UNIT tests using the in-memory SQLite `client` fixture and a
mocked AI service. They do NOT require Neon or the live Qwen endpoint.

The orchestrator is AI-driven and conversational: `decide(req)` returns an
`OrchestratorResponse` that is either a decision (SLM/LLM) or a
clarification question. The AI call (`chat_json`) is mocked so no real
endpoint is hit.
"""
from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.routers import orchestrator as orchestrator_mod
from app.services.orchestrator import _validate, decide
from app.schemas import OrchestratorRequest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _patch_session_factory(
    monkeypatch: pytest.MonkeyPatch, engine: object
) -> None:
    """Point the background worker's session factory at the in-memory engine."""
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    monkeypatch.setattr(orchestrator_mod, "get_session_factory", lambda: factory)


class _MockChat:
    """A controllable stand-in for `chat_json`.

    It validates the JSON payload with the provided validator (mirroring the
    real chat_json) and returns the resulting model.
    """

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
        raw = json.dumps(self.payload)
        model = validator(raw)
        return model, {"correlation_id": "test", "attempts": 1}


def _mock_chat(
    monkeypatch: pytest.MonkeyPatch, payload: dict[str, Any], *, fail: bool = False
) -> _MockChat:
    """Patch `chat_json` in the orchestrator service module."""
    mock = _MockChat(payload, fail=fail)
    monkeypatch.setattr("app.services.orchestrator.chat_json", mock)
    return mock


_DECISION_PAYLOAD = {
    "status": "decision",
    "decision": {
        "recommendation": "LLM",
        "confidence": 0.9,
        "use_case": "reasoning",
        "rationale": "Open-ended reasoning task.",
        "factors": [
            {
                "name": "open_endedness",
                "signal": "complex",
                "weight": 0.4,
                "direction": "LLM",
                "explanation": "needs reasoning",
            }
        ],
        "suggested_llm": "qwen3.8-27b",
    },
}

_CLARIFY_PAYLOAD = {
    "status": "clarify",
    "question": {
        "question": "Is this a one-off task or high-volume?",
        "why": "Volume affects whether an SLM's latency/cost advantage matters.",
        "options": ["one-off", "high-volume"],
    },
}


# ---------------------------------------------------------------------------
# _validate (unit)
# ---------------------------------------------------------------------------
def test_validate_decision() -> None:
    raw = json.dumps(_DECISION_PAYLOAD)
    resp = _validate(raw)
    assert resp.status == "decision"
    assert resp.decision is not None
    assert resp.decision.recommendation == "LLM"
    # direction normalised to lowercase.
    assert resp.decision.factors[0].direction == "llm"


def test_validate_clarify() -> None:
    raw = json.dumps(_CLARIFY_PAYLOAD)
    resp = _validate(raw)
    assert resp.status == "clarify"
    assert resp.question is not None
    assert resp.question.question
    assert resp.question.options == ["one-off", "high-volume"]


def test_validate_tolerates_markdown_fences() -> None:
    raw = "```json\n" + json.dumps(_DECISION_PAYLOAD) + "\n```"
    resp = _validate(raw)
    assert resp.status == "decision"
    assert resp.decision is not None


def test_validate_tolerates_flat_decision() -> None:
    # The AI sometimes returns the decision fields flat at the top level
    # instead of nested under a "decision" key.
    flat = {
        "status": "decision",
        "recommendation": "SLM",
        "confidence": 0.95,
        "use_case": "classification",
        "rationale": "narrow task",
        "factors": [
            {"name": "task_type", "signal": "classification", "weight": 0.3, "direction": "SLM", "explanation": "x"}
        ],
        "suggested_slm": "a small model",
        "suggested_llm": None,
    }
    resp = _validate(json.dumps(flat))
    assert resp.status == "decision"
    assert resp.decision is not None
    assert resp.decision.recommendation == "SLM"
    assert resp.decision.factors[0].direction == "slm"


# ---------------------------------------------------------------------------
# decide (service, mocked AI)
# ---------------------------------------------------------------------------
def test_decide_returns_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_chat(monkeypatch, _DECISION_PAYLOAD)
    resp = decide(OrchestratorRequest(prompt="Analyze the legal implications"))
    assert resp.status == "decision"
    assert resp.decision is not None
    assert resp.decision.recommendation == "LLM"


def test_decide_returns_clarify(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_chat(monkeypatch, _CLARIFY_PAYLOAD)
    resp = decide(OrchestratorRequest(prompt="Help me with this"))
    assert resp.status == "clarify"
    assert resp.question is not None


def test_decide_raises_when_ai_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    _mock_chat(monkeypatch, _DECISION_PAYLOAD, fail=True)
    from app.services.ai_service import AIServiceError

    with pytest.raises(AIServiceError):
        decide(OrchestratorRequest(prompt="Analyze the legal implications"))


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
def test_decide_endpoint_rejects_empty_prompt(client: TestClient) -> None:
    res = client.post("/api/v1/orchestrator/decide", json={"prompt": ""})
    assert res.status_code == 422


def test_decide_returns_202(
    client: TestClient, db_engine, monkeypatch
) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    _mock_chat(monkeypatch, _DECISION_PAYLOAD)

    res = client.post(
        "/api/v1/orchestrator/decide",
        json={"prompt": "Write a detailed strategy for market entry"},
    )
    assert res.status_code == 202
    body = res.json()
    assert body["status"] == "running"
    assert body["id"]


def test_decide_completes_with_decision(
    client: TestClient, db_engine, monkeypatch
) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    _mock_chat(monkeypatch, _DECISION_PAYLOAD)

    res = client.post(
        "/api/v1/orchestrator/decide",
        json={"prompt": "Analyze the legal implications of this contract"},
    )
    run_id = res.json()["id"]

    detail = client.get(f"/api/v1/orchestrator/decide/{run_id}").json()
    assert detail["run"]["status"] == "completed"
    assert detail["response"] is not None
    assert detail["response"]["status"] == "decision"
    assert detail["response"]["decision"]["recommendation"] == "LLM"


def test_decide_completes_with_clarify(
    client: TestClient, db_engine, monkeypatch
) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    _mock_chat(monkeypatch, _CLARIFY_PAYLOAD)

    res = client.post(
        "/api/v1/orchestrator/decide",
        json={"prompt": "Help me with this"},
    )
    run_id = res.json()["id"]

    detail = client.get(f"/api/v1/orchestrator/decide/{run_id}").json()
    assert detail["run"]["status"] == "completed"
    assert detail["response"]["status"] == "clarify"
    assert detail["response"]["question"] is not None


def test_decide_404(client: TestClient) -> None:
    res = client.get("/api/v1/orchestrator/decide/does-not-exist")
    assert res.status_code == 404


def test_decide_list(client: TestClient, db_engine, monkeypatch) -> None:
    _patch_session_factory(monkeypatch, db_engine)
    _mock_chat(monkeypatch, _DECISION_PAYLOAD)

    client.post("/api/v1/orchestrator/decide", json={"prompt": "Classify spam"})
    runs = client.get("/api/v1/orchestrator/decide").json()
    assert isinstance(runs, list)
    assert len(runs) >= 1
