"""Project CRUD endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Project
from app.schemas import ProjectCreate, ProjectOut

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _to_out(p: Project) -> ProjectOut:
    return ProjectOut(
        id=p.id,
        name=p.name,
        description=p.description,
        status=p.status,
        initial_description=p.initial_description,
        created_at=p.created_at.isoformat() if p.created_at else "",
    )


@router.post("", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db)) -> ProjectOut:
    project = Project(
        name=payload.name,
        description=payload.description,
        initial_description=payload.initial_description,
        status="discovery",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return _to_out(project)


@router.get("", response_model=list[ProjectOut])
def list_projects(db: Session = Depends(get_db)) -> list[ProjectOut]:
    rows = db.execute(select(Project).order_by(Project.created_at.desc())).scalars()
    return [_to_out(p) for p in rows]


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(project_id: str, db: Session = Depends(get_db)) -> ProjectOut:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return _to_out(project)
