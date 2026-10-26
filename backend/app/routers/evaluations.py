"""Evaluation planning and (gated) execution endpoints.

Evaluation planning is separated from execution. Live evaluation against
external endpoints requires explicit configuration and approval. We do NOT
automatically send confidential user documents to external model providers.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import EvaluationRun, Project

router = APIRouter(prefix="/api/v1/projects/{project_id}/evaluations", tags=["evaluations"])


class EvaluationPlanIn(BaseModel):
    component_id: str | None = None
    model_id: str | None = None
    # Metrics to measure, e.g. precision, recall, f1, latency_p50, latency_p95.
    metrics: list[str] = []
    dataset_version: str | None = None


class EvaluationRunOut(BaseModel):
    id: str
    project_id: str
    component_id: str | None = None
    model_id: str | None = None
    status: str
    metrics: dict
    dataset_version: str | None = None
    executed: bool
    approved: bool
    created_at: str


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return project


def _to_out(e: EvaluationRun) -> EvaluationRunOut:
    return EvaluationRunOut(
        id=e.id,
        project_id=e.project_id,
        component_id=e.component_id,
        model_id=e.model_id,
        status=e.status,
        metrics=e.metrics or {},
        dataset_version=e.dataset_version,
        executed=e.executed,
        approved=e.approved,
        created_at=e.created_at.isoformat() if e.created_at else "",
    )


@router.get("", response_model=list[EvaluationRunOut])
def list_evaluations(project_id: str, db: Session = Depends(get_db)) -> list[EvaluationRunOut]:
    _get_project(db, project_id)
    rows = db.execute(
        select(EvaluationRun).where(EvaluationRun.project_id == project_id)
    ).scalars()
    return [_to_out(e) for e in rows]


@router.post("", response_model=EvaluationRunOut, status_code=201)
def plan_evaluation(
    project_id: str,
    payload: EvaluationPlanIn,
    db: Session = Depends(get_db),
) -> EvaluationRunOut:
    """Create a planned evaluation.

    Planning does NOT execute anything. Execution requires explicit approval
    and an approved provider/endpoint.
    """
    _get_project(db, project_id)
    run = EvaluationRun(
        project_id=project_id,
        component_id=payload.component_id,
        model_id=payload.model_id,
        status="planned",
        metrics={m: None for m in payload.metrics},
        dataset_version=payload.dataset_version,
        executed=False,
        approved=False,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _to_out(run)


@router.post("/{run_id}/approve", response_model=EvaluationRunOut)
def approve_evaluation(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> EvaluationRunOut:
    """Approve a planned evaluation for execution.

    NOTE: Live execution is intentionally not implemented in this slice.
    Approving marks the run as approved; actual execution against an external
    endpoint requires a separately configured, approved provider and is gated
    behind explicit configuration. We do not fabricate results.
    """
    _get_project(db, project_id)
    run = db.get(EvaluationRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="evaluation_run_not_found")
    run.approved = True
    db.commit()
    db.refresh(run)
    return _to_out(run)
