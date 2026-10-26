"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-20
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # projects
    op.create_table(
        "projects",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("initial_description", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_projects_status", "projects", ["status"])

    # discovery_sessions
    op.create_table(
        "discovery_sessions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_discovery_sessions_project_id", "discovery_sessions", ["project_id"])

    # requirements
    op.create_table(
        "requirements",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("criticality", sa.String(length=16), nullable=False),
        sa.Column("dependencies", sa.JSON(), nullable=False),
        sa.Column("acceptance_criteria", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_requirements_project_id", "requirements", ["project_id"])
    op.create_index("ix_requirements_status", "requirements", ["status"])
    op.create_index("ix_requirements_category", "requirements", ["category"])

    # requirement_versions
    op.create_table(
        "requirement_versions",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_requirement_versions_project_id", "requirement_versions", ["project_id"])

    # components
    op.create_table(
        "components",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.Text(), nullable=False),
        sa.Column("parent_workflow", sa.String(length=32), nullable=True),
        sa.Column("input_contract", sa.JSON(), nullable=False),
        sa.Column("output_contract", sa.JSON(), nullable=False),
        sa.Column("ai_required", sa.Boolean(), nullable=False),
        sa.Column("recommended_approach", sa.String(length=32), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=True),
        sa.Column("decision_rationale", sa.Text(), nullable=False),
        sa.Column("risks", sa.JSON(), nullable=False),
        sa.Column("validation_plan", sa.JSON(), nullable=False),
        sa.Column("requirement_ids", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("unresolved_questions", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_components_project_id", "components", ["project_id"])
    op.create_index("ix_components_ai_required", "components", ["ai_required"])

    # component_dependencies
    op.create_table(
        "component_dependencies",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("from_component_id", sa.String(length=32), sa.ForeignKey("components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("to_component_id", sa.String(length=32), sa.ForeignKey("components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_component_dependencies_from", "component_dependencies", ["from_component_id"])
    op.create_index("ix_component_dependencies_to", "component_dependencies", ["to_component_id"])

    # analysis_runs
    op.create_table(
        "analysis_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("correlation_id", sa.String(length=64), nullable=True),
        sa.Column("requirement_version_id", sa.String(length=32), sa.ForeignKey("requirement_versions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_analysis_runs_project_id", "analysis_runs", ["project_id"])
    op.create_index("ix_analysis_runs_status", "analysis_runs", ["status"])

    # model_registry
    op.create_table(
        "model_registry",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=64), nullable=True),
        sa.Column("family", sa.String(length=128), nullable=True),
        sa.Column("total_params", sa.Integer(), nullable=True),
        sa.Column("active_params", sa.Integer(), nullable=True),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("classification_reason", sa.Text(), nullable=False),
        sa.Column("modalities", sa.JSON(), nullable=False),
        sa.Column("context_window", sa.Integer(), nullable=True),
        sa.Column("tool_calling", sa.Boolean(), nullable=True),
        sa.Column("structured_output", sa.Boolean(), nullable=True),
        sa.Column("license", sa.String(length=128), nullable=True),
        sa.Column("deployment_options", sa.JSON(), nullable=False),
        sa.Column("availability_status", sa.String(length=32), nullable=False),
        sa.Column("doc_url", sa.String(length=512), nullable=True),
        sa.Column("pricing", sa.JSON(), nullable=True),
        sa.Column("last_verified", sa.String(length=32), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("evidence_quality", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_model_registry_name", "model_registry", ["name"])
    op.create_index("ix_model_registry_provider", "model_registry", ["provider"])
    op.create_index("ix_model_registry_classification", "model_registry", ["classification"])

    # model_sources
    op.create_table(
        "model_sources",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("model_id", sa.String(length=32), sa.ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("url", sa.String(length=512), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("supports", sa.String(length=128), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("accessed_at", sa.String(length=32), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_model_sources_model_id", "model_sources", ["model_id"])

    # model_benchmarks
    op.create_table(
        "model_benchmarks",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("model_id", sa.String(length=32), sa.ForeignKey("model_registry.id", ondelete="CASCADE"), nullable=False),
        sa.Column("benchmark_name", sa.String(length=128), nullable=False),
        sa.Column("task_category", sa.String(length=64), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("source_url", sa.String(length=512), nullable=True),
        sa.Column("measured", sa.Boolean(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_model_benchmarks_model_id", "model_benchmarks", ["model_id"])

    # recommendations
    op.create_table(
        "recommendations",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("analysis_run_id", sa.String(length=32), sa.ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_id", sa.String(length=32), sa.ForeignKey("components.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("model_id", sa.String(length=32), sa.ForeignKey("model_registry.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("verified", sa.Boolean(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("strengths", sa.JSON(), nullable=False),
        sa.Column("weaknesses", sa.JSON(), nullable=False),
        sa.Column("cost", sa.JSON(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("unverified", sa.JSON(), nullable=False),
        sa.Column("source_links", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_recommendations_analysis_run_id", "recommendations", ["analysis_run_id"])
    op.create_index("ix_recommendations_component_id", "recommendations", ["component_id"])
    op.create_index("ix_recommendations_rank", "recommendations", ["rank"])

    # evaluation_runs
    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column("project_id", sa.String(length=32), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("component_id", sa.String(length=32), sa.ForeignKey("components.id", ondelete="SET NULL"), nullable=True),
        sa.Column("model_id", sa.String(length=32), sa.ForeignKey("model_registry.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("metrics", sa.JSON(), nullable=False),
        sa.Column("dataset_version", sa.String(length=64), nullable=True),
        sa.Column("executed", sa.Boolean(), nullable=False),
        sa.Column("approved", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_evaluation_runs_project_id", "evaluation_runs", ["project_id"])
    op.create_index("ix_evaluation_runs_status", "evaluation_runs", ["status"])


def downgrade() -> None:
    op.drop_table("evaluation_runs")
    op.drop_table("recommendations")
    op.drop_table("model_benchmarks")
    op.drop_table("model_sources")
    op.drop_table("model_registry")
    op.drop_table("analysis_runs")
    op.drop_table("component_dependencies")
    op.drop_table("components")
    op.drop_table("requirement_versions")
    op.drop_table("requirements")
    op.drop_table("discovery_sessions")
    op.drop_table("projects")
