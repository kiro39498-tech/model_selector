"""Requirements discovery service.

Implements conversational, adaptive requirements discovery using the configured
AI endpoint. The AI generates follow-up questions and extracts requirements
from the user's text. All output is validated with Pydantic.

Verified vs. inferred requirements are clearly distinguished:
- Requirements the user explicitly stated are marked source="user".
- Requirements the AI inferred are marked source="inferred" and are NOT treated
  as user-approved.
"""
from __future__ import annotations

import json
import logging
import uuid

from app.schemas import DiscoveryResponse, RequirementIn
from app.services.ai_service import AIServiceError, chat_json

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a senior solution architect conducting requirements discovery for "
    "a software application. The user has described an application they want to "
    "build. Your job is to understand it end to end and ask only the follow-up "
    "questions that materially affect requirements, architecture, or model "
    "selection. Do not ask questions whose answers are already provided. "
    "Extract requirements from what the user has said. Mark requirements the "
    "user explicitly stated with source 'user'; mark anything you inferred with "
    "source 'inferred'. Never fabricate requirements. "
    "Categories: business, functional, data, non_functional, ai, operational. "
    "Respond ONLY with a JSON object matching the schema."
)


def _build_messages(
    initial_description: str,
    history: list[dict[str, str]],
    existing_requirements: list[dict],
) -> list[dict[str, str]]:
    existing = "\n".join(
        f"- [{r.get('code')}] ({r.get('category')}) {r.get('description')}"
        for r in existing_requirements
    )
    user_content = (
        f"Initial application description:\n{initial_description}\n\n"
        f"Existing requirements already captured:\n{existing or '(none)'}\n\n"
        "Produce a JSON object with keys: questions (list of follow-up "
        "questions, max 5), requirements (list of extracted requirements, each "
        "with code, description, category, source, status, criticality), "
        "outstanding_categories (list of categories still needing information), "
        "ambiguities (list of detected ambiguities). "
        "Only include requirements that are supported by the user's text. "
        "Do not invent requirements."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
        *history,
    ]


def _validate(raw: str) -> DiscoveryResponse:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise AIServiceError(f"AI response is not valid JSON: {exc}") from exc
    return DiscoveryResponse.model_validate(data)


def run_discovery(
    initial_description: str,
    history: list[dict[str, str]],
    existing_requirements: list[dict],
    correlation_id: str | None = None,
) -> DiscoveryResponse:
    """Run one turn of requirements discovery.

    Returns a validated DiscoveryResponse. Raises AIServiceError if the AI
    service is unavailable or the response cannot be validated.
    """
    cid = correlation_id or uuid.uuid4().hex
    messages = _build_messages(initial_description, history, existing_requirements)
    result, _meta = chat_json(
        messages,
        _validate,
        correlation_id=cid,
        repair_prompt=(
            "Your previous response was not valid JSON or did not match the "
            "required schema. Return ONLY a valid JSON object with keys: "
            "questions, requirements, outstanding_categories, ambiguities."
        ),
    )
    return result
