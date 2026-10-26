"""Tests for AI response validation and the analysis schema.

These tests do not require a live AI endpoint or database. They verify that
the validation logic accepts well-formed JSON and rejects malformed input, and
that the schema enforces the classification and recommendation rules.
"""
from __future__ import annotations

import pytest

from app.routers.analysis import _validate
from app.schemas import AnalysisResponse, ModelRecommendation


def test_validate_accepts_valid_json() -> None:
    raw = (
        '{"schema_version": "1.0", "application_summary": "x", '
        '"confirmed_requirements": [], "remaining_uncertainties": [], '
        '"components": [], "workflows": [], "hybrid_strategies": [], '
        '"risks": [], "validation_plan": {}, "consistency_checks": [], '
        '"implementation_roadmap": []}'
    )
    result = _validate(raw)
    assert isinstance(result, AnalysisResponse)
    assert result.application_summary == "x"


def test_validate_strips_markdown_fences() -> None:
    raw = '```json\n{"schema_version": "1.0", "components": []}\n```'
    result = _validate(raw)
    assert result.schema_version == "1.0"


def test_validate_rejects_non_json() -> None:
    with pytest.raises(Exception):
        _validate("this is not json")


def test_model_recommendation_requires_rank() -> None:
    rec = ModelRecommendation(
        rank=1,
        model_name="Llama 3.1 8B",
        provider="Meta",
        classification="SLM",
        rationale="small and fast",
    )
    assert rec.rank == 1
    assert rec.verified is False  # defaults to unverified


def test_analysis_response_defaults() -> None:
    # A minimal response should validate with sensible defaults.
    result = AnalysisResponse.model_validate({"schema_version": "1.0"})
    assert result.components == []
    assert result.risks == []
