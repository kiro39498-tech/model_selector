"""Requirements discovery, completeness, and approval endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import DiscoverySession, Project, Requirement, RequirementVersion
from app.schemas import (
    CompletenessAssessment,
    DiscoveryRequest,
    DiscoveryResponse,
    RequirementIn,
    RequirementOut,
    RequirementStatusUpdate,
    RequirementVersionOut,
)
from app.services.ai_service import AIServiceError
from app.services.discovery import run_discovery

router = APIRouter(prefix="/api/v1/projects/{project_id}/requirements", tags=["requirements"])

CATEGORIES = [
    "business",
    "functional",
    "data",
    "non_functional",
    "ai",
    "operational",
]


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return project


def _to_out(r: Requirement) -> RequirementOut:
    return RequirementOut(
        id=r.id,
        code=r.code,
        description=r.description,
        category=r.category,
        source=r.source,
        status=r.status,
        confidence=r.confidence,
        criticality=r.criticality,
        dependencies=r.dependencies or [],
        acceptance_criteria=r.acceptance_criteria or [],
    )


@router.get("", response_model=list[RequirementOut])
def list_requirements(project_id: str, db: Session = Depends(get_db)) -> list[RequirementOut]:
    _get_project(db, project_id)
    rows = db.execute(
        select(Requirement).where(Requirement.project_id == project_id).order_by(Requirement.code)
    ).scalars()
    return [_to_out(r) for r in rows]


@router.post("", response_model=RequirementOut, status_code=201)
def add_requirement(
    project_id: str,
    payload: RequirementIn,
    db: Session = Depends(get_db),
) -> RequirementOut:
    _get_project(db, project_id)
    req = Requirement(
        project_id=project_id,
        code=payload.code,
        description=payload.description,
        category=payload.category,
        source=payload.source,
        status=payload.status,
        confidence=payload.confidence,
        criticality=payload.criticality,
        dependencies=payload.dependencies,
        acceptance_criteria=payload.acceptance_criteria,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return _to_out(req)


_VALID_STATUSES = {"confirmed", "rejected", "proposed", "unresolved", "inferred"}


@router.patch("/{code}", response_model=RequirementOut)
def update_requirement_status(
    project_id: str,
    code: str,
    payload: RequirementStatusUpdate,
    db: Session = Depends(get_db),
) -> RequirementOut:
    """Update a single requirement's status (e.g. confirm or reject).

    This resolves the approval deadlock: a high-criticality requirement can be
    confirmed individually so the approval gate can open, without approving the
    whole set at once.
    """
    _get_project(db, project_id)
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"invalid_status: {payload.status}",
        )
    req = db.execute(
        select(Requirement).where(
            Requirement.project_id == project_id, Requirement.code == code
        )
    ).scalars().first()
    if req is None:
        raise HTTPException(status_code=404, detail="requirement_not_found")
    req.status = payload.status
    db.commit()
    db.refresh(req)
    return _to_out(req)


@router.post("/discovery", response_model=DiscoveryResponse)
def discovery(
    project_id: str,
    payload: DiscoveryRequest,
    db: Session = Depends(get_db),
) -> DiscoveryResponse:
    """Conversational requirements discovery.

    Uses the AI endpoint to generate follow-up questions and extract
    requirements from the user's text. Output is validated with Pydantic.
    Verified (user-stated) vs. inferred requirements are clearly distinguished.
    """
    project = _get_project(db, project_id)

    # Load or create the discovery session for this project.
    session = db.execute(
        select(DiscoverySession).where(DiscoverySession.project_id == project_id)
    ).scalars().first()
    if session is None:
        session = DiscoverySession(project_id=project_id, status="active", messages=[])
        db.add(session)

    # Append the user's message to the session history.
    session.messages = list(session.messages or [])
    session.messages.append({"role": "user", "content": payload.message})

    # Materialize the query result into a list so it can be iterated multiple
    # times (a ScalarResult is a lazy iterator that is exhausted after one pass).
    existing = list(
        db.execute(
            select(Requirement).where(Requirement.project_id == project_id)
        ).scalars()
    )
    existing_dicts = [
        {
            "code": r.code,
            "category": r.category,
            "description": r.description,
            "status": r.status,
        }
        for r in existing
    ]

    try:
        result = run_discovery(
            initial_description=project.initial_description,
            history=session.messages,
            existing_requirements=existing_dicts,
        )
    except AIServiceError as exc:
        # Clear, understandable error; never expose credentials or traces.
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Persist extracted requirements (deduped by code).
    existing_codes = {r.code for r in existing}
    for req in result.requirements:
        if req.code in existing_codes:
            continue
        db.add(
            Requirement(
                project_id=project_id,
                code=req.code,
                description=req.description,
                category=req.category,
                source=req.source,
                status=req.status,
                confidence=req.confidence,
                criticality=req.criticality,
                dependencies=req.dependencies,
                acceptance_criteria=req.acceptance_criteria,
            )
        )
        existing_codes.add(req.code)

    db.commit()
    return result


@router.get("/completeness", response_model=CompletenessAssessment)
def completeness(project_id: str, db: Session = Depends(get_db)) -> CompletenessAssessment:
    """Assess requirement completeness by category and criticality.

    Completeness is defined by category and criticality, not a single
    percentage. We report what is still missing.
    """
    _get_project(db, project_id)
    # Materialize into a list so it can be iterated multiple times.
    rows = list(
        db.execute(
            select(Requirement).where(Requirement.project_id == project_id)
        ).scalars()
    )

    by_category: dict[str, float] = {}
    for cat in CATEGORIES:
        cat_reqs = [r for r in rows if r.category == cat]
        confirmed = [r for r in cat_reqs if r.status == "confirmed"]
        by_category[cat] = round(len(confirmed) / len(cat_reqs), 2) if cat_reqs else 0.0

    critical_unresolved = [
        r.code
        for r in rows
        if r.criticality == "high" and r.status in ("proposed", "unresolved", "inferred")
    ]
    missing = [
        f"{cat}: no confirmed requirements"
        for cat, score in by_category.items()
        if score == 0.0
    ]
    ready = all(score >= 0.5 for score in by_category.values()) and not critical_unresolved

    return CompletenessAssessment(
        by_category=by_category,
        critical_unresolved=critical_unresolved,
        missing=missing,
        ready_for_approval=ready,
    )


@router.post("/approve", response_model=RequirementVersionOut)
def approve_requirements(project_id: str, db: Session = Depends(get_db)) -> RequirementVersionOut:
    """Approve the current requirements, creating a version snapshot.

    Final analysis is not allowed until critical requirements are resolved and
    approved. This endpoint enforces that gate.
    """
    project = _get_project(db, project_id)
    # Materialize into a list so it can be iterated multiple times.
    rows = list(
        db.execute(
            select(Requirement).where(Requirement.project_id == project_id)
        ).scalars()
    )

    critical_unresolved = [
        r.code
        for r in rows
        if r.criticality == "high" and r.status in ("proposed", "unresolved", "inferred")
    ]
    if critical_unresolved:
        raise HTTPException(
            status_code=409,
            detail=f"cannot_approve: critical requirements unresolved: {critical_unresolved}",
        )

    # Mark all non-rejected requirements as confirmed.
    for r in rows:
        if r.status != "rejected":
            r.status = "confirmed"

    version = RequirementVersion(
        project_id=project_id,
        version=_next_version(db, project_id),
        status="approved",
        snapshot={
            "requirements": [
                {
                    "code": r.code,
                    "description": r.description,
                    "category": r.category,
                    "status": r.status,
                }
                for r in rows
            ]
        },
    )
    db.add(version)
    project.status = "approved"
    db.commit()
    db.refresh(version)
    return RequirementVersionOut(
        id=version.id,
        project_id=version.project_id,
        version=version.version,
        status=version.status,
        approved_at=version.approved_at.isoformat() if version.approved_at else None,
        created_at=version.created_at.isoformat() if version.created_at else "",
    )


def _next_version(db: Session, project_id: str) -> int:
    rows = db.execute(
        select(RequirementVersion).where(RequirementVersion.project_id == project_id)
    ).scalars()
    return max((v.version for v in rows), default=0) + 1
