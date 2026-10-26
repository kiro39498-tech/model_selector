"""Model classification policy.

Application convention (NOT a universal scientific definition):
- A model with fewer than 150 billion parameters is an SLM.
- A model with 150 billion or more parameters is an LLM.
- Unknown parameter counts are classified as 'unknown'.

The threshold is stored in configuration so it can be changed deliberately.
"""
from __future__ import annotations

from app.config import settings


def classify(total_params: int | None) -> tuple[str, str]:
    """Classify a model by total parameter count.

    Returns (classification, reason).

    - total_params is the raw parameter count (e.g. 27_000_000_000 for 27B).
    - If total_params is None, classification is 'unknown'.
    - The threshold is read from configuration.
    """
    if total_params is None:
        return "unknown", "Parameter count is unknown; classified as unknown until verified."

    threshold = settings.classification_threshold_params
    if total_params < threshold:
        billions = total_params / 1_000_000_000
        return (
            "SLM",
            f"{billions:.0f}B parameters is fewer than the "
            f"{settings.classification_threshold_billions:.0f}B threshold, so it is an SLM.",
        )
    billions = total_params / 1_000_000_000
    return (
        "LLM",
        f"{billions:.0f}B parameters is >= the "
        f"{settings.classification_threshold_billions:.0f}B threshold, so it is an LLM.",
    )


def classify_billions(total_billions: float | None) -> tuple[str, str]:
    """Convenience wrapper that accepts parameter count in billions."""
    if total_billions is None:
        return classify(None)
    return classify(int(total_billions * 1_000_000_000))
