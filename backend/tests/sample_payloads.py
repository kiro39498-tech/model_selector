"""Sample payloads for mocked tests.

These are deterministic, valid payloads that conform to the application's
Pydantic schemas. They are NOT live integration results.
"""
from __future__ import annotations

from typing import Any


def sample_analysis_payload() -> dict[str, Any]:
    """A valid AnalysisResponse payload with three ranked recommendations.

    The three candidates are drawn from the curated registry and are
    classified per the 150B policy. No benchmark scores are included.
    """
    return {
        "schema_version": "1.0",
        "application_summary": "A customer support assistant.",
        "confirmed_requirements": ["REQ-001"],
        "remaining_uncertainties": [],
        "components": [
            {
                "component_id": "C-001",
                "name": "Intent classification",
                "purpose": "Classify the user's intent from a support message.",
                "input_contract": {"text": "user message"},
                "output_contract": {"intent": "string"},
                "dependencies": [],
                "ai_required": True,
                "recommended_approach": "slm",
                "classification": "SLM",
                "model_recommendations": [
                    {
                        "rank": 1,
                        "model_name": "Llama 3.1 8B",
                        "provider": "Meta",
                        "total_params": 8_000_000_000,
                        "classification": "SLM",
                        "deployment_option": "self_hosted",
                        "rationale": "Small, fast, suitable for routine classification.",
                        "evidence": ["Official model card"],
                        "strengths": ["Low latency"],
                        "weaknesses": ["Limited reasoning"],
                        "cost": None,
                        "confidence": 0.7,
                        "unverified": [],
                        "source_links": ["https://ai.meta.com/llama/llama3_1/"],
                        "verified": True,
                    },
                    {
                        "rank": 2,
                        "model_name": "Mistral 7B",
                        "provider": "Mistral AI",
                        "total_params": 7_000_000_000,
                        "classification": "SLM",
                        "deployment_option": "self_hosted",
                        "rationale": "Comparable size, Apache-2.0 license.",
                        "evidence": ["Official announcement"],
                        "strengths": ["Permissive license"],
                        "weaknesses": ["Smaller context"],
                        "cost": None,
                        "confidence": 0.6,
                        "unverified": [],
                        "source_links": ["https://mistral.ai/news/mistral-7b"],
                        "verified": True,
                    },
                    {
                        "rank": 3,
                        "model_name": "Llama 3.1 70B",
                        "provider": "Meta",
                        "total_params": 70_000_000_000,
                        "classification": "SLM",
                        "deployment_option": "self_hosted",
                        "rationale": "Larger SLM for higher-quality classification.",
                        "evidence": ["Official model card"],
                        "strengths": ["Higher quality"],
                        "weaknesses": ["Higher cost/latency"],
                        "cost": None,
                        "confidence": 0.5,
                        "unverified": [],
                        "source_links": ["https://ai.meta.com/llama/llama3_1/"],
                        "verified": True,
                    },
                ],
                "decision_rationale": "Routine classification suits an SLM.",
                "evidence": ["Task is deterministic classification."],
                "alternatives": ["deterministic rules"],
                "risks": ["Misclassification on ambiguous input."],
                "validation_plan": {"metric": "f1"},
                "requirement_ids": ["REQ-001"],
                "confidence": 0.7,
                "unresolved_questions": [],
            }
        ],
        "workflows": [],
        "hybrid_strategies": [],
        "risks": [],
        "validation_plan": {},
        "consistency_checks": [],
        "implementation_roadmap": [],
    }


def sample_discovery_payload() -> dict[str, Any]:
    """A valid DiscoveryResponse payload."""
    return {
        "questions": ["Who are the target users?"],
        "requirements": [
            {
                "code": "REQ-001",
                "description": "Classify support message intent.",
                "category": "ai",
                "source": "user",
                "status": "proposed",
                "criticality": "high",
            }
        ],
        "outstanding_categories": ["business"],
        "ambiguities": [],
    }
