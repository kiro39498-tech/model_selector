"""Orchestrator: decides whether a task should use an SLM or an LLM.

This is the core decision engine of the application. It is **AI-driven and
conversational**: given a task/query (and the conversation so far), the AI
reasons about whether the task is clear enough to decide.

- If the task is clear, it returns a **decision** (SLM or LLM) with a
  rationale and the factors it weighed.
- If the task is ambiguous or missing key detail that would change the
  decision, it asks a **follow-up question** instead of guessing.

The client maintains the conversation and sends it back on each turn, so
the AI can reason over the full context. There is no rule-based fallback:
the decision is always made by the AI (never fabricated).
"""
from __future__ import annotations

import json
import uuid

from app.schemas import (
    OrchestratorMessage,
    OrchestratorRequest,
    OrchestratorResponse,
)
from app.services.ai_service import AIServiceError, chat_json

# ---------------------------------------------------------------------------
# JSON helpers (tolerate prose-wrapped / truncated JSON from the AI)
# ---------------------------------------------------------------------------


def _extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from possibly prose-wrapped text.

    A reasoning model may emit prose before/after the JSON, or wrap it in
    markdown fences. This returns the substring from the first '{' to the
    matching last '}'.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.lower().startswith("json"):
            stripped = stripped[4:]
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        return stripped
    return stripped[start : end + 1]


def _repair_truncated_json(text: str) -> str:
    """Best-effort repair of a JSON object truncated mid-generation.

    Closes any open string, then balances open brackets/braces. This lets a
    response cut off by the token cap still parse into a partial-but-valid
    object, which the schema (with defaults) can validate.
    """
    out: list[str] = []
    in_string = False
    escaped = False
    stack: list[str] = []
    for ch in text:
        if in_string:
            out.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
            out.append(ch)
            continue
        if ch in "{[":
            stack.append(ch)
            out.append(ch)
            continue
        if ch in "}]":
            if stack:
                stack.pop()
            out.append(ch)
            continue
        out.append(ch)
    if in_string:
        out.append('"')
    for opener in reversed(stack):
        out.append("}" if opener == "{" else "]")
    return "".join(out)


def _validate(raw: str) -> OrchestratorResponse:
    """Validate raw AI text as an OrchestratorResponse.

    Tolerates a JSON object wrapped in markdown fences or prose, and repairs
    a JSON object truncated mid-generation (e.g. by the token cap). Also
    normalises case so the model can return "LLM"/"SLM" for ``direction``
    (the schema uses lowercase) and for ``recommendation`` (uppercase).
    """
    candidate = _extract_json_object(raw)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        try:
            data = json.loads(_repair_truncated_json(candidate))
        except json.JSONDecodeError as exc:
            raise AIServiceError(f"AI response is not valid JSON: {exc}") from exc
    if isinstance(data, dict):
        # Normalise the top-level status.
        if isinstance(data.get("status"), str):
            data["status"] = data["status"].strip().lower()
        # The AI sometimes returns the decision fields flat at the top level
        # (e.g. {"status": "decision", "recommendation": "SLM", ...}) instead
        # of nested under a "decision" key. Fold them into a nested block so
        # the schema (which expects a nested decision) validates.
        decision = data.get("decision")
        if not isinstance(decision, dict) and data.get("recommendation") is not None:
            decision = {k: v for k, v in data.items() if k != "status"}
            data["decision"] = decision
        if isinstance(decision, dict):
            if isinstance(decision.get("recommendation"), str):
                decision["recommendation"] = decision["recommendation"].strip().upper()
            for factor in decision.get("factors", []) or []:
                if isinstance(factor, dict) and isinstance(factor.get("direction"), str):
                    factor["direction"] = factor["direction"].strip().lower()
        # Normalise the question block (if present).
        question = data.get("question")
        if isinstance(question, dict):
            if not isinstance(question.get("options"), list):
                question["options"] = []
    try:
        return OrchestratorResponse.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - re-raise as AIServiceError
        raise AIServiceError(f"AI response did not match the schema: {exc}") from exc


# ---------------------------------------------------------------------------
# AI decision path
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = (
    "You are an AI model-selection orchestrator. Your job is to decide "
    "whether a given task or query should be handled by a Small Language "
    "Model (SLM) or a Large Language Model (LLM).\n\n"
    "Definitions:\n"
    "- An SLM is appropriate for specific, narrow, well-defined tasks: "
    "classification, extraction, routing, short summarization, simple Q&A "
    "from a knowledge base, translation, sentiment, intent detection.\n"
    "- An LLM is appropriate for open-ended, complex, multi-step, creative, "
    "or knowledge-heavy tasks: reasoning, planning, analysis, long-form "
    "generation, ambiguous or nuanced requests, and tasks in domains like "
    "legal, medical, or financial.\n\n"
    "You are conversational. If the task is ambiguous, or you are missing "
    "key detail that would change the decision (for example the input size, "
    "the required accuracy, whether the task is a one-off or high-volume, "
    "the domain, or whether the output must be creative), you MUST ask a "
    "single follow-up question instead of guessing. Ask a question only when "
    "the answer would genuinely change the SLM/LLM decision; otherwise make "
    "the decision. Ask at most one question at a time.\n\n"
    "Respond ONLY with a JSON object matching the schema below."
)


def _build_messages(req: OrchestratorRequest) -> list[dict[str, str]]:
    constraints = ", ".join(req.constraints) if req.constraints else "none"
    # Build the conversation: prior turns, then the current prompt.
    convo = list(req.conversation)
    if req.prompt:
        convo.append(OrchestratorMessage(role="user", content=req.prompt))
    convo_text = "\n".join(f"{m.role}: {m.content}" for m in convo)
    user = (
        f"Conversation so far:\n{convo_text}\n\n"
        f"Constraints: {constraints}\n\n"
        "Decide whether the task is clear enough to choose SLM or LLM. "
        "If it is, return a decision. If it is ambiguous or missing key "
        "detail, ask a single follow-up question.\n\n"
        "Return a JSON object with keys: status (\"decision\" or "
        "\"clarify\"). If status is \"decision\", include: recommendation "
        "(SLM|LLM|unknown), confidence (0..1), use_case, rationale, factors "
        "(list of {name, signal, weight, direction, explanation}), "
        "suggested_slm, suggested_llm. If status is \"clarify\", include "
        "question: {question, why, options}. Do not invent benchmark "
        "scores or prices."
    )
    return [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user},
    ]


def decide(req: OrchestratorRequest) -> OrchestratorResponse:
    """Produce an AI-reasoned response for a task.

    Returns either a decision (SLM/LLM) or a clarification question.
    Raises AIServiceError if the AI endpoint is unavailable or the response
    cannot be validated.
    """
    messages = _build_messages(req)
    response, _meta = chat_json(
        messages,
        _validate,
        correlation_id=uuid.uuid4().hex,
        max_tokens=2048,
        repair_prompt=(
            "Your previous response was not valid JSON or did not match the "
            "required schema. Return ONLY a valid JSON object matching the "
            "schema, with no prose outside the JSON."
        ),
    )
    return response
