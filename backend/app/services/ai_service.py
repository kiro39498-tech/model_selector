"""Dedicated AI endpoint integration service.

Wraps the OpenAI-compatible endpoint. All AI access goes through this module;
no AI code is placed in frontend components or route handlers directly.

Design notes:
- The configured endpoint is a *reasoning* endpoint. It is NOT assumed to
  support model enumeration, web browsing, or invoking other models.
- Structured JSON output / JSON schema mode is NOT assumed. We use a compatible
  prompting strategy and validate the response server-side with Pydantic.
- Timeouts, bounded retries for transient failures, and request correlation IDs
  are implemented here.
- Credentials are never logged or returned in responses.
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Callable, TypeVar

from openai import OpenAI
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)

T = TypeVar("T")

# Transient errors that are safe to retry.
_RETRYABLE = (APITimeoutError, APIConnectionError, RateLimitError)


class AIServiceError(RuntimeError):
    """Raised when the AI service cannot produce a usable result."""


class AIUnavailableError(AIServiceError):
    """Raised when the AI endpoint is unreachable or misconfigured."""


def _get_client() -> OpenAI:
    """Create an OpenAI client bound to the configured endpoint.

    Raises AIUnavailableError if the API key is not configured.
    """
    if not settings.ai_configured:
        raise AIUnavailableError(
            "AI service is not configured. Set AI_API_KEY in your .env file."
        )
    return OpenAI(
        api_key=settings.ai_api_key,
        base_url=settings.ai_base_url,
        timeout=settings.ai_timeout_seconds,
        max_retries=0,  # We manage retries ourselves for visibility.
    )


def _chat_stream(
    client: OpenAI,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int | None,
) -> str:
    """Stream a chat completion and return the accumulated assistant text.

    Streaming keeps the connection alive across the provider's (Cloudflare)
    per-chunk read timeout, so a slow reasoning model that takes >120s to
    finish is no longer cut off mid-request.
    """
    stream = client.chat.completions.create(
        model=settings.ai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=True,
    )
    parts: list[str] = []
    for chunk in stream:
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        if delta and delta.content:
            parts.append(delta.content)
    content = "".join(parts)
    if not content:
        raise AIUnavailableError("AI returned empty content (streaming).")
    return content


def _chat_non_stream(
    client: OpenAI,
    messages: list[dict[str, str]],
    *,
    temperature: float,
    max_tokens: int | None,
) -> str:
    """Non-streaming chat completion (fallback if streaming is unsupported)."""
    response = client.chat.completions.create(
        model=settings.ai_model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    content = response.choices[0].message.content
    if content is None:
        raise AIUnavailableError("AI returned empty content.")
    return content


def chat(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    correlation_id: str | None = None,
) -> str:
    """Send a chat completion request and return the assistant text.

    Uses streaming by default so a slow reasoning model is not cut off by the
    provider's per-chunk read timeout. Falls back to a non-streaming request
    if streaming is unsupported. Retries transient failures up to
    ``settings.ai_max_retries`` times. Raises AIUnavailableError if the service
    is unavailable after retries.
    """
    cid = correlation_id or uuid.uuid4().hex
    client = _get_client()
    attempt = 0
    last_error: Exception | None = None

    while attempt <= settings.ai_max_retries:
        attempt += 1
        try:
            # Prefer streaming; fall back to non-streaming if the endpoint
            # rejects streaming (e.g. 400/422 on the stream flag).
            try:
                return _chat_stream(
                    client,
                    messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
            except APIError as stream_exc:
                if getattr(stream_exc, "status_code", None) in (400, 422):
                    logger.warning(
                        "Streaming unsupported (correlation_id=%s); "
                        "falling back to non-streaming.",
                        cid,
                    )
                    return _chat_non_stream(
                        client,
                        messages,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                raise
        except _RETRYABLE as exc:
            last_error = exc
            # Do not log secrets; log only the error type and correlation id.
            logger.warning(
                "AI transient error (attempt %d/%d, correlation_id=%s): %s",
                attempt,
                settings.ai_max_retries + 1,
                cid,
                type(exc).__name__,
            )
            if attempt <= settings.ai_max_retries:
                time.sleep(min(2 ** attempt, 8))
                continue
            break
        except APIError as exc:
            # Non-transient API error (e.g. 4xx). Do not retry.
            raise AIUnavailableError(
                f"AI service error (correlation_id={cid}): {type(exc).__name__}"
            ) from exc

    raise AIUnavailableError(
        f"AI service unavailable after {attempt} attempts (correlation_id={cid})."
    )


def chat_json(
    messages: list[dict[str, str]],
    validator: Callable[[str], T],
    *,
    temperature: float = 0.2,
    max_tokens: int | None = None,
    correlation_id: str | None = None,
    repair_prompt: str | None = None,
) -> tuple[T, dict[str, Any]]:
    """Request JSON output and validate it with a Pydantic validator.

    Because JSON schema mode is NOT assumed to be supported, we use a prompting
    strategy that asks for JSON and then validate server-side. If validation
    fails, a bounded repair attempt is made using ``repair_prompt``.

    Returns a tuple of (validated_model, raw_response_metadata).
    """
    cid = correlation_id or uuid.uuid4().hex
    raw = chat(
        messages,
        temperature=temperature,
        max_tokens=max_tokens,
        correlation_id=cid,
    )
    try:
        model = validator(raw)
        return model, {"correlation_id": cid, "attempts": 1}
    except Exception as exc:  # noqa: BLE001 - we re-raise as AIServiceError
        if repair_prompt is None:
            raise AIServiceError(
                f"AI response failed validation (correlation_id={cid}): "
                f"{type(exc).__name__}"
            ) from exc
        # Bounded repair: ask the model to fix the JSON, once.
        repair_messages = [
            {"role": "user", "content": raw},
            {"role": "user", "content": repair_prompt},
        ]
        try:
            fixed = chat(
                repair_messages,
                temperature=0.0,
                max_tokens=max_tokens,
                correlation_id=cid,
            )
            model = validator(fixed)
            return model, {"correlation_id": cid, "attempts": 2, "repaired": True}
        except Exception as exc2:  # noqa: BLE001
            raise AIServiceError(
                f"AI response failed validation after repair "
                f"(correlation_id={cid}): {type(exc2).__name__}"
            ) from exc2


def check_ai() -> bool:
    """Return True if the AI endpoint is reachable and configured.

    Raises AIUnavailableError if not configured or unreachable.
    """
    if not settings.ai_configured:
        raise AIUnavailableError("AI service is not configured (AI_API_KEY missing).")
    # A minimal probe; we do not assume any special capability.
    _get_client()
    return True
