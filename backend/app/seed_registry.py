"""Seed the model registry with a small, clearly-labeled curated set.

IMPORTANT: This seed is illustrative. It contains only widely-documented model
facts (name, provider, approximate parameter counts, official documentation
URLs). It does NOT include benchmark scores (those must be measured, not
invented). Availability and evidence quality are labeled conservatively.

Run with:  python -m app.seed_registry
"""
from __future__ import annotations

from app.db import get_session_factory
from app.models import ModelRegistry
from app.services.classification import classify_billions

# Each entry: (name, provider, version, family, total_billions, active_billions,
# modalities, context_window, tool_calling, structured_output, license,
# deployment_options, availability_status, doc_url, evidence_quality)
#
# Parameter counts are approximate and drawn from commonly-documented figures.
# They are labeled evidence_quality="documented" only where an official doc URL
# is provided; availability is labeled conservatively.
SEED: list[dict] = [
    {
        "name": "qwen3.8-27b",
        "provider": "Alibaba (configured reasoning endpoint)",
        "version": "3.8",
        "family": "Qwen",
        "total_billions": 27.0,
        "active_billions": None,
        "modalities": ["text"],
        "context_window": None,
        "tool_calling": None,
        "structured_output": None,
        "license": "unknown",
        "deployment_options": ["hosted"],
        "availability_status": "available",
        "doc_url": "http://indiaai.maqsoftware.net/v1",
        "evidence_quality": "documented",
        "note": "Configured reasoning endpoint. Not assumed to enumerate models or browse.",
    },
    {
        "name": "Llama 3.1 8B",
        "provider": "Meta",
        "version": "3.1",
        "family": "Llama",
        "total_billions": 8.0,
        "active_billions": None,
        "modalities": ["text"],
        "context_window": 131072,
        "tool_calling": True,
        "structured_output": True,
        "license": "Llama 3.1 Community License",
        "deployment_options": ["open_weight", "self_hosted"],
        "availability_status": "open_weight",
        "doc_url": "https://ai.meta.com/llama/llama3_1/",
        "evidence_quality": "documented",
    },
    {
        "name": "Llama 3.1 70B",
        "provider": "Meta",
        "version": "3.1",
        "family": "Llama",
        "total_billions": 70.0,
        "active_billions": None,
        "modalities": ["text"],
        "context_window": 131072,
        "tool_calling": True,
        "structured_output": True,
        "license": "Llama 3.1 Community License",
        "deployment_options": ["open_weight", "self_hosted"],
        "availability_status": "open_weight",
        "doc_url": "https://ai.meta.com/llama/llama3_1/",
        "evidence_quality": "documented",
    },
    {
        "name": "GPT-4o",
        "provider": "OpenAI",
        "version": "4o",
        "family": "GPT",
        "total_billions": None,  # Not publicly disclosed.
        "active_billions": None,
        "modalities": ["text", "image", "audio"],
        "context_window": 128000,
        "tool_calling": True,
        "structured_output": True,
        "license": "proprietary",
        "deployment_options": ["hosted"],
        "availability_status": "available",
        "doc_url": "https://platform.openai.com/docs/models",
        "evidence_quality": "documented",
        "note": "Parameter count not publicly disclosed; classified as unknown.",
    },
    {
        "name": "Claude 3.5 Sonnet",
        "provider": "Anthropic",
        "version": "3.5",
        "family": "Claude",
        "total_billions": None,  # Not publicly disclosed.
        "active_billions": None,
        "modalities": ["text", "image"],
        "context_window": 200000,
        "tool_calling": True,
        "structured_output": True,
        "license": "proprietary",
        "deployment_options": ["hosted"],
        "availability_status": "available",
        "doc_url": "https://docs.anthropic.com/claude/models",
        "evidence_quality": "documented",
        "note": "Parameter count not publicly disclosed; classified as unknown.",
    },
    {
        "name": "Mistral 7B",
        "provider": "Mistral AI",
        "version": "7B",
        "family": "Mistral",
        "total_billions": 7.0,
        "active_billions": None,
        "modalities": ["text"],
        "context_window": 32768,
        "tool_calling": True,
        "structured_output": True,
        "license": "Apache 2.0",
        "deployment_options": ["open_weight", "self_hosted"],
        "availability_status": "open_weight",
        "doc_url": "https://mistral.ai/news/mistral-7b",
        "evidence_quality": "documented",
    },
]


def seed() -> int:
    """Insert seed models if not already present. Returns count inserted."""
    factory = get_session_factory()
    session = factory()
    inserted = 0
    try:
        for entry in SEED:
            existing = (
                session.query(ModelRegistry)
                .filter(ModelRegistry.name == entry["name"])
                .first()
            )
            if existing is not None:
                continue
            classification, reason = classify_billions(entry["total_billions"])
            model = ModelRegistry(
                name=entry["name"],
                provider=entry["provider"],
                version=entry["version"],
                family=entry["family"],
                total_params=(
                    int(entry["total_billions"] * 1_000_000_000)
                    if entry["total_billions"] is not None
                    else None
                ),
                active_params=(
                    int(entry["active_billions"] * 1_000_000_000)
                    if entry.get("active_billions") is not None
                    else None
                ),
                classification=classification,
                classification_reason=reason,
                modalities=entry["modalities"],
                context_window=entry["context_window"],
                tool_calling=entry["tool_calling"],
                structured_output=entry["structured_output"],
                license=entry["license"],
                deployment_options=entry["deployment_options"],
                availability_status=entry["availability_status"],
                doc_url=entry["doc_url"],
                pricing=None,  # Not invented.
                last_verified=None,  # Not asserted without verification.
                confidence=0.6 if entry["evidence_quality"] == "documented" else 0.3,
                evidence_quality=entry["evidence_quality"],
            )
            session.add(model)
            inserted += 1
        session.commit()
    finally:
        session.close()
    return inserted


if __name__ == "__main__":
    count = seed()
    print(f"Seeded {count} model registry entries.")
