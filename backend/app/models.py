"""SQLAlchemy 2.x ORM models.

Normalized schema with foreign keys, indexes, and constraints.
JSONB is used only for genuinely variable structured metadata.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Use JSONB on PostgreSQL, JSON elsewhere (e.g. tests).
JSONB = JSON


def _uuid() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


class BaseORM(Base):
    """Base providing id and timestamps for all tables."""

    __abstract__ = True

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------
class Project(BaseORM):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Status: draft, discovery, approved, analyzed, archived
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    # Free-form initial description provided by the user.
    initial_description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    requirements = relationship(
        "Requirement", back_populates="project", cascade="all, delete-orphan"
    )
    components = relationship(
        "Component", back_populates="project", cascade="all, delete-orphan"
    )
    analysis_runs = relationship(
        "AnalysisRun", back_populates="project", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_projects_status", "status"),)


# ---------------------------------------------------------------------------
# Requirements discovery
# ---------------------------------------------------------------------------
class DiscoverySession(BaseORM):
    __tablename__ = "discovery_sessions"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Status: active, completed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    # Structured interaction records (messages) stored as JSONB.
    messages: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)


class Requirement(BaseORM):
    __tablename__ = "requirements"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Stable requirement ID (human-readable, e.g. "REQ-001").
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    # Category: business, functional, data, non_functional, ai, operational
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    # Source: user, inferred, proposed
    source: Mapped[str] = mapped_column(String(32), nullable=False, default="user")
    # Status: confirmed, inferred, proposed, unresolved, rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    # Confidence 0..1 where meaningful.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Criticality: high, medium, low
    criticality: Mapped[str] = mapped_column(String(16), nullable=False, default="medium")
    # Dependencies on other requirement codes.
    dependencies: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Related acceptance criteria.
    acceptance_criteria: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    project = relationship("Project", back_populates="requirements")

    __table_args__ = (
        Index("ix_requirements_project_id", "project_id"),
        Index("ix_requirements_status", "status"),
        Index("ix_requirements_category", "category"),
    )


class RequirementVersion(BaseORM):
    """Approval record for a set of requirements at a point in time."""

    __tablename__ = "requirement_versions"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # Status: proposed, approved, rejected
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    # Snapshot of the requirements at approval time.
    snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        Index("ix_requirement_versions_project_id", "project_id"),
    )


# ---------------------------------------------------------------------------
# Components & architecture
# ---------------------------------------------------------------------------
class Component(BaseORM):
    __tablename__ = "components"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Parent workflow code (nullable).
    parent_workflow: Mapped[str | None] = mapped_column(String(32), nullable=True)
    input_contract: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_contract: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Whether AI is necessary for this component.
    ai_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Recommended approach: deterministic, search, ocr, ml, embeddings, slm,
    # llm, hybrid, human, none
    recommended_approach: Mapped[str] = mapped_column(String(32), nullable=False, default="none")
    # SLM/LLM classification when applicable.
    classification: Mapped[str | None] = mapped_column(String(16), nullable=True)
    decision_rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    risks: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    validation_plan: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Traceability to confirmed requirement codes.
    requirement_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    unresolved_questions: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    project = relationship("Project", back_populates="components")
    dependencies = relationship(
        "ComponentDependency",
        foreign_keys="ComponentDependency.from_component_id",
        back_populates="from_component",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_components_project_id", "project_id"),
        Index("ix_components_ai_required", "ai_required"),
    )


class ComponentDependency(BaseORM):
    __tablename__ = "component_dependencies"

    from_component_id: Mapped[str] = mapped_column(
        ForeignKey("components.id", ondelete="CASCADE"), nullable=False
    )
    to_component_id: Mapped[str] = mapped_column(
        ForeignKey("components.id", ondelete="CASCADE"), nullable=False
    )
    # Relationship type: depends_on, calls, data_flow, etc.
    relation: Mapped[str] = mapped_column(String(32), nullable=False, default="depends_on")

    from_component = relationship(
        "Component", foreign_keys=[from_component_id], back_populates="dependencies"
    )

    __table_args__ = (
        Index("ix_component_dependencies_from", "from_component_id"),
        Index("ix_component_dependencies_to", "to_component_id"),
    )


# ---------------------------------------------------------------------------
# Analysis runs
# ---------------------------------------------------------------------------
class AnalysisRun(BaseORM):
    __tablename__ = "analysis_runs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    # Status: pending, running, completed, failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # The AI response (validated) stored as JSONB.
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Error detail if failed (no secrets).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Requirement version this analysis was based on.
    requirement_version_id: Mapped[str | None] = mapped_column(
        ForeignKey("requirement_versions.id", ondelete="SET NULL"), nullable=True
    )

    project = relationship("Project", back_populates="analysis_runs")

    __table_args__ = (
        Index("ix_analysis_runs_project_id", "project_id"),
        Index("ix_analysis_runs_status", "status"),
    )


# ---------------------------------------------------------------------------
# Orchestrator (SLM vs LLM decision)
# ---------------------------------------------------------------------------
class OrchestratorRun(BaseORM):
    """A single SLM/LLM decision request and its result.

    Independent of projects: the orchestrator is a standalone service that
    classifies a single task/query. It may be invoked synchronously
    (heuristic) or asynchronously (AI reasoning), mirroring the analysis
    async pattern.
    """

    __tablename__ = "orchestrator_runs"

    # Status: pending, running, completed, failed
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending")
    # The decision (validated) stored as JSONB.
    decision: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # The original request (prompt + context + constraints) for traceability.
    request: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Error detail if failed (no secrets).
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        Index("ix_orchestrator_runs_status", "status"),
    )


# ---------------------------------------------------------------------------
# Model registry & evidence
# ---------------------------------------------------------------------------
class ModelRegistry(BaseORM):
    __tablename__ = "model_registry"

    # Canonical model name.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    family: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Total parameter count (raw). None if unknown.
    # BigInteger: parameter counts (e.g. 27B = 27_000_000_000) exceed the
    # 32-bit INTEGER range and must be stored as BIGINT on PostgreSQL.
    total_params: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Active parameter count for MoE models (raw). None if N/A.
    active_params: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # SLM/LLM/unknown classification.
    classification: Mapped[str] = mapped_column(String(16), nullable=False, default="unknown")
    # Reason for the classification (evidence-backed).
    classification_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Supported modalities: text, image, audio, etc.
    modalities: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    context_window: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tool_calling: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    structured_output: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    license: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # Hosting/deployment options: hosted, open_weight, self_hosted
    deployment_options: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Availability status: available, open_weight, conditional, discontinued, unverified
    availability_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified"
    )
    # Official documentation URL.
    doc_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Pricing info when available (JSONB).
    pricing: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Date last verified (ISO date string).
    last_verified: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # Confidence 0..1 and evidence quality.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evidence_quality: Mapped[str] = mapped_column(
        String(32), nullable=False, default="unverified"
    )

    __table_args__ = (
        Index("ix_model_registry_name", "name"),
        Index("ix_model_registry_provider", "provider"),
        Index("ix_model_registry_classification", "classification"),
    )


class ModelSource(BaseORM):
    """A source/evidence record for a model registry entry."""

    __tablename__ = "model_sources"

    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    url: Mapped[str] = mapped_column(String(512), nullable=False)
    # Type: official_docs, model_card, benchmark, api_docs, evaluation
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # What this source supports (e.g. "parameter_count", "benchmark").
    supports: Mapped[str] = mapped_column(String(128), nullable=False)
    # Whether the source is publicly documented / verified.
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    accessed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)

    __table_args__ = (Index("ix_model_sources_model_id", "model_id"),)


class ModelBenchmark(BaseORM):
    """A benchmark result for a model. Only stored when actually measured."""

    __tablename__ = "model_benchmarks"

    model_id: Mapped[str] = mapped_column(
        ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False
    )
    benchmark_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # Task category the benchmark measures.
    task_category: Mapped[str] = mapped_column(String(64), nullable=False)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Source URL for the benchmark result.
    source_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    # Whether the result is measured (True) or estimated (False).
    measured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Limitations of the benchmark.
    limitations: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (Index("ix_model_benchmarks_model_id", "model_id"),)


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------
class Recommendation(BaseORM):
    """A per-task model recommendation (rank 1, 2, or 3)."""

    __tablename__ = "recommendations"

    analysis_run_id: Mapped[str] = mapped_column(
        ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[str] = mapped_column(
        ForeignKey("components.id", ondelete="CASCADE"), nullable=False
    )
    # Rank 1, 2, or 3.
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    model_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_registry.id", ondelete="SET NULL"), nullable=True
    )
    # Exact model name (may reference a registry entry or an AI-proposed name).
    model_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    # Whether this recommendation is verified against the registry.
    verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Why it suits this task.
    rationale: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Evidence supporting the recommendation.
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Strengths and weaknesses.
    strengths: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    weaknesses: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Cost info when available (reported separately, not a ranking criterion).
    cost: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Confidence 0..1.
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    # Information that remains unverified.
    unverified: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # Official source links.
    source_links: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    __table_args__ = (
        Index("ix_recommendations_analysis_run_id", "analysis_run_id"),
        Index("ix_recommendations_component_id", "component_id"),
        Index("ix_recommendations_rank", "rank"),
    )


# ---------------------------------------------------------------------------
# Evaluations
# ---------------------------------------------------------------------------
class EvaluationRun(BaseORM):
    __tablename__ = "evaluation_runs"

    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    component_id: Mapped[str | None] = mapped_column(
        ForeignKey("components.id", ondelete="SET NULL"), nullable=True
    )
    model_id: Mapped[str | None] = mapped_column(
        ForeignKey("model_registry.id", ondelete="SET NULL"), nullable=True
    )
    # Status: planned, running, completed, failed, unavailable
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="planned")
    # Metrics: precision, recall, f1, latency_p50, latency_p95, etc.
    metrics: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    # Dataset version used.
    dataset_version: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Whether the evaluation actually ran (vs. planned).
    executed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Approval required before live evaluation against external endpoints.
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("ix_evaluation_runs_project_id", "project_id"),
        Index("ix_evaluation_runs_status", "status"),
    )
