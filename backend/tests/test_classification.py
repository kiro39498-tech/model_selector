"""Tests for the model classification policy.

These tests do not require a database or AI endpoint.
"""
from __future__ import annotations

from app.services.classification import classify, classify_billions


def test_150b_is_llm() -> None:
    # Exactly 150B is an LLM per the application policy.
    classification, _ = classify_billions(150.0)
    assert classification == "LLM"


def test_149b_is_slm() -> None:
    classification, _ = classify_billions(149.0)
    assert classification == "SLM"


def test_27b_is_slm() -> None:
    classification, _ = classify_billions(27.0)
    assert classification == "SLM"


def test_200b_is_llm() -> None:
    classification, _ = classify_billions(200.0)
    assert classification == "LLM"


def test_unknown_when_none() -> None:
    classification, reason = classify(None)
    assert classification == "unknown"
    assert "unknown" in reason.lower()


def test_reason_is_provided() -> None:
    _, reason = classify_billions(70.0)
    assert reason  # non-empty
    assert "SLM" in reason
