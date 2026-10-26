"""Pydantic schemas for request/response validation.

The frontend must not depend on arbitrary unvalidated model-generated JSON.
All AI responses are validated against these schemas server-side.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    initial_description: str = Field(min_length=1)


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str
    status: str
    initial_description: str
    created_at: str


# ---------------------------------------------------------------------------
# Requirements
# ---------------------------------------------------------------------------
class RequirementIn(BaseModel):
    code: str
    description: str
    category: str
    source: str = "user"
    status: str = "proposed"
    confidence: float | None = None
    criticality: str = "medium"
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class RequirementOut(BaseModel):
    id: str
    code: str
    description: str
    category: str
    source: str
    status: str
    confidence: float | None = None
    criticality: str
    dependencies: list[str] = Field(default_factory=list)
    acceptance_criteria: list[str] = Field(default_factory=list)


class RequirementStatusUpdate(BaseModel):
    """Update a single requirement's status (e.g. confirm/reject).

    This lets a user resolve a high-criticality requirement so the approval
    gate can open, without having to approve the whole set at once.
    """

    status: str = Field(
        default="confirmed",
        description="One of: confirmed, rejected, proposed, unresolved, inferred.",
    )


class DiscoveryMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class DiscoveryRequest(BaseModel):
    message: str = Field(min_length=1)


class DiscoveryResponse(BaseModel):
    # The AI's next follow-up question(s).
    questions: list[str] = Field(default_factory=list)
    # Requirements extracted/updated from this turn.
    requirements: list[RequirementIn] = Field(default_factory=list)
    # Categories still needing information.
    outstanding_categories: list[str] = Field(default_factory=list)
    # Ambiguities detected.
    ambiguities: list[str] = Field(default_factory=list)


class CompletenessAssessment(BaseModel):
    # Per-category completeness (0..1).
    by_category: dict[str, float] = Field(default_factory=dict)
    # Overall completeness is NOT a single percentage; we report by category.
    critical_unresolved: list[str] = Field(default_factory=list)
    # What is still missing, explained.
    missing: list[str] = Field(default_factory=list)
    ready_for_approval: bool = False


# ---------------------------------------------------------------------------
# Model registry
# ---------------------------------------------------------------------------
class ModelRegistryOut(BaseModel):
    id: str
    name: str
    provider: str
    version: str | None = None
    family: str | None = None
    total_params: int | None = None
    active_params: int | None = None
    classification: str
    classification_reason: str
    modalities: list[str] = Field(default_factory=list)
    context_window: int | None = None
    tool_calling: bool | None = None
    structured_output: bool | None = None
    license: str | None = None
    deployment_options: list[str] = Field(default_factory=list)
    availability_status: str
    doc_url: str | None = None
    pricing: dict[str, Any] | None = None
    last_verified: str | None = None
    confidence: float | None = None
    evidence_quality: str


# ---------------------------------------------------------------------------
# Analysis (AI response contract)
# ---------------------------------------------------------------------------
# A reasoning model often emits prose where a structured type is expected
# (e.g. "8B" for total_params, "high" for confidence, or a sentence for a
# list field). These coercion helpers normalise such values before Pydantic
# type validation, so a valid-but-prose response still validates.
_CONFIDENCE_WORDS = {
    "very high": 0.95,
    "high": 0.9,
    "medium": 0.6,
    "moderate": 0.6,
    "low": 0.3,
    "very low": 0.1,
}


def _coerce_params(v: Any) -> Any:
    """Coerce total_params from e.g. "8B"/"150B" to an int (or None)."""
    if isinstance(v, str):
        s = v.strip().lower().replace(" ", "")
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            pass
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([bkmt]?)", s)
        if m:
            num = float(m.group(1))
            mult = {"": 1, "b": 1e9, "k": 1e3, "m": 1e6, "t": 1e12}[m.group(2)]
            return int(num * mult)
        return None
    return v


def _coerce_confidence(v: Any) -> Any:
    """Coerce confidence from e.g. "high" to a float (or None)."""
    if isinstance(v, str):
        s = v.strip().lower()
        if s in _CONFIDENCE_WORDS:
            return _CONFIDENCE_WORDS[s]
        try:
            return float(s)
        except ValueError:
            return None
    return v


def _scalar_to_str(v: Any) -> str:
    """Render a non-string value as a readable string.

    A reasoning model may return a dict (e.g. {'id': 'R1', 'description': ...})
    where a string is expected; prefer a human-readable field, else stringify.
    """
    if isinstance(v, dict):
        for key in ("description", "text", "summary", "value", "name"):
            if key in v and isinstance(v[key], str):
                return v[key].strip()
        return str(v)
    return str(v)


def _coerce_to_list(v: Any) -> Any:
    """Coerce a non-list value into a list of strings.

    A reasoning model may return a prose string, a bool, a dict, or another
    scalar where a list is expected; normalise it into a list of strings.
    """
    if isinstance(v, list):
        return [_scalar_to_str(x) for x in v]
    if isinstance(v, str):
        text = v.strip()
        return [text] if text else []
    if v is None:
        return []
    # Any other scalar (e.g. bool, int, float, dict) -> single-element list.
    return [_scalar_to_str(v)]


def _coerce_validation_plan(v: Any) -> Any:
    """Coerce validation_plan into a dict.

    A reasoning model may return prose (str) or a list of steps instead of a
    dict; normalise both into a dict so the schema validates.
    """
    if isinstance(v, str):
        text = v.strip()
        return {"summary": text} if text else {}
    if isinstance(v, list):
        return {"steps": [str(x) for x in v]} if v else {}
    return v


class ModelRecommendation(BaseModel):
    model_config = ConfigDict(extra="ignore")

    rank: int
    model_name: str
    provider: str
    total_params: int | None = None
    classification: str | None = None
    deployment_option: str | None = None
    rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)
    cost: dict[str, Any] | None = None
    confidence: float | None = None
    unverified: list[str] = Field(default_factory=list)
    source_links: list[str] = Field(default_factory=list)
    verified: bool = False

    @field_validator("total_params", mode="before")
    @classmethod
    def _coerce_total_params(cls, v: Any) -> Any:
        return _coerce_params(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> Any:
        return _coerce_confidence(v)

    @field_validator("cost", mode="before")
    @classmethod
    def _coerce_cost(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"note": v.strip()} if v.strip() else None
        return v

    @field_validator("evidence", "strengths", "weaknesses", "unverified", mode="before")
    @classmethod
    def _coerce_to_list(cls, v: Any) -> Any:
        return _coerce_to_list(v)


class ComponentAnalysis(BaseModel):
    model_config = ConfigDict(extra="ignore")

    component_id: str
    name: str
    purpose: str = ""
    input_contract: dict[str, Any] = Field(default_factory=dict)
    output_contract: dict[str, Any] = Field(default_factory=dict)
    dependencies: list[str] = Field(default_factory=list)
    ai_required: bool = False
    recommended_approach: str = "none"
    classification: str | None = None
    model_recommendations: list[ModelRecommendation] = Field(default_factory=list)
    decision_rationale: str = ""
    evidence: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_plan: dict[str, Any] = Field(default_factory=dict)
    requirement_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None
    unresolved_questions: list[str] = Field(default_factory=list)

    @field_validator("validation_plan", mode="before")
    @classmethod
    def _coerce_validation_plan(cls, v: Any) -> Any:
        return _coerce_validation_plan(v)

    @field_validator("confidence", mode="before")
    @classmethod
    def _coerce_confidence(cls, v: Any) -> Any:
        return _coerce_confidence(v)

    @field_validator("evidence", "alternatives", "risks", mode="before")
    @classmethod
    def _coerce_to_list(cls, v: Any) -> Any:
        return _coerce_to_list(v)


class HybridStrategy(BaseModel):
    model_config = ConfigDict(extra="ignore")

    component_id: str
    strategy: str
    initial_model: str | None = None
    escalation_conditions: list[str] = Field(default_factory=list)
    validation_checks: list[str] = Field(default_factory=list)
    fallback: str = ""
    expected_quality_effect: str = ""
    expected_latency_effect: str = ""
    evaluation: str = ""


class AnalysisResponse(BaseModel):
    """Versioned AI analysis response contract."""

    model_config = ConfigDict(extra="ignore")

    schema_version: str = "1.0"
    application_summary: str = ""
    confirmed_requirements: list[str] = Field(default_factory=list)
    remaining_uncertainties: list[str] = Field(default_factory=list)
    components: list[ComponentAnalysis] = Field(default_factory=list)
    workflows: list[dict[str, Any]] = Field(default_factory=list)
    hybrid_strategies: list[HybridStrategy] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    validation_plan: dict[str, Any] = Field(default_factory=dict)
    consistency_checks: list[str] = Field(default_factory=list)
    implementation_roadmap: list[str] = Field(default_factory=list)

    @field_validator("validation_plan", mode="before")
    @classmethod
    def _coerce_validation_plan(cls, v: Any) -> Any:
        return _coerce_validation_plan(v)

    @field_validator(
        "confirmed_requirements",
        "remaining_uncertainties",
        "consistency_checks",
        "implementation_roadmap",
        "risks",
        mode="before",
    )
    @classmethod
    def _coerce_list(cls, v: Any) -> Any:
        # A reasoning model may return prose, a dict, or a bool where a list of
        # strings is expected; normalise into a list of strings.
        return _coerce_to_list(v)


class RequirementVersionOut(BaseModel):
    id: str
    project_id: str
    version: int
    status: str
    approved_at: str | None = None
    created_at: str


class AnalysisRunOut(BaseModel):
    id: str
    project_id: str
    status: str
    correlation_id: str | None = None
    error: str | None = None
    created_at: str


class AnalysisResultOut(BaseModel):
    run: AnalysisRunOut
    result: AnalysisResponse | None = None


# ---------------------------------------------------------------------------
# Orchestrator (SLM vs LLM decision)
# ---------------------------------------------------------------------------
class OrchestratorMessage(BaseModel):
    """A single turn in the orchestrator conversation."""

    role: Literal["user", "assistant"]
    content: str


class OrchestratorRequest(BaseModel):
    """A task/query to classify as SLM- or LLM-appropriate.

    The orchestrator is AI-driven and conversational: if the task is
    ambiguous or missing key detail, it asks a follow-up question instead of
    deciding. The client maintains the conversation and sends it back on
    each turn so the AI can reason over the full context.
    """

    prompt: str = Field(min_length=1, max_length=8000)
    # Prior conversation turns (the client maintains the conversation).
    conversation: list[OrchestratorMessage] = Field(default_factory=list)
    # Optional constraints the caller cares about (e.g. "low latency",
    # "on-prem only", "high accuracy"). Free-form; the AI interprets them.
    constraints: list[str] = Field(default_factory=list)


class DecisionFactor(BaseModel):
    """A single factor the orchestrator weighed, with its direction."""

    name: str
    # The observed signal for this factor (e.g. "task is specific and narrow").
    signal: str
    # 0..1 importance of this factor for the decision.
    weight: float = 0.0
    # Which side this factor pushes toward.
    direction: Literal["slm", "llm", "neutral"] = "neutral"
    explanation: str = ""


class OrchestratorDecision(BaseModel):
    """The orchestrator's decision for a single task (AI-reasoned)."""

    model_config = ConfigDict(extra="ignore")

    # The recommendation.
    recommendation: Literal["SLM", "LLM", "unknown"] = "unknown"
    # 0..1 confidence in the recommendation.
    confidence: float = 0.0
    # The detected use-case category (e.g. "classification", "reasoning").
    use_case: str = "general"
    # A short, human-readable rationale.
    rationale: str = ""
    # The factors weighed, in order of importance.
    factors: list[DecisionFactor] = Field(default_factory=list)
    # Suggested concrete models (from the registry) for each side.
    suggested_slm: str | None = None
    suggested_llm: str | None = None


class ClarificationQuestion(BaseModel):
    """A follow-up question the orchestrator asks when the task is unclear."""

    # The question to ask the user.
    question: str = Field(min_length=1)
    # Why this question matters for the SLM/LLM decision.
    why: str = ""
    # Optional suggested answers to help the user respond quickly.
    options: list[str] = Field(default_factory=list)


class OrchestratorResponse(BaseModel):
    """The orchestrator's response to a task: either a decision or a
    follow-up question (never both)."""

    model_config = ConfigDict(extra="ignore")

    # "decision" = the task is clear enough to decide; "clarify" = the
    # orchestrator needs more detail before deciding.
    status: Literal["decision", "clarify"] = "clarify"
    # Present when status == "decision".
    decision: OrchestratorDecision | None = None
    # Present when status == "clarify".
    question: ClarificationQuestion | None = None


class OrchestratorRunOut(BaseModel):
    id: str
    status: str
    correlation_id: str | None = None
    error: str | None = None
    created_at: str


class OrchestratorResultOut(BaseModel):
    run: OrchestratorRunOut
    # The orchestrator's response (decision or clarification question).
    response: OrchestratorResponse | None = None
