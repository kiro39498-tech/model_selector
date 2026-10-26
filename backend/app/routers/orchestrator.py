"""Orchestrator endpoints: decide whether a task should use an SLM or an LLM.

This is the core service of the application. It is AI-driven and
conversational: given a task/query (and the conversation so far), the AI
either returns a decision (SLM or LLM) or asks a follow-up question when the
task is ambiguous.

The client maintains the conversation and sends it back on each turn.

Endpoints:
- POST /orchestrator/decide        -> start a decision (202). The AI work
  runs in the background; poll GET /orchestrator/decide/{run_id} for the
  result. This mirrors the analysis async pattern so a slow reasoning-model
  call does not hold an HTTP request (or a DB connection) open and get cut
  by a proxy timeout.
- GET  /orchestrator/decide/{run_id} -> poll a run for its result.
- GET  /orchestrator/decide        -> list recent runs.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, get_session_factory
from app.models import OrchestratorRun
from app.schemas import (
    OrchestratorRequest,
    OrchestratorResultOut,
    OrchestratorRunOut,
)
from app.services.ai_service import AIServiceError
from app.services.orchestrator import decide

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/orchestrator", tags=["orchestrator"])


# ---------------------------------------------------------------------------
# Background execution
# ---------------------------------------------------------------------------
def _mark_failed(run_id: str, error: str) -> None:
    """Mark a run as failed in a fresh, short-lived session."""
    try:
        session = get_session_factory()()
        try:
            run = session.get(OrchestratorRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error = error
                session.commit()
        finally:
            session.close()
    except Exception:  # noqa: BLE001 - never let a background task raise
        pass


def _run_decision_background(run_id: str, req: OrchestratorRequest) -> None:
    """Execute the AI decision in the background (a worker thread).

    Does NOT hold a database connection across the slow AI call. It performs
    the AI call, then opens a fresh session to persist the result.
    """
    try:
        response = decide(req)
    except AIServiceError as exc:
        _mark_failed(run_id, str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        _mark_failed(run_id, f"decision_failed: {type(exc).__name__}")
        return

    try:
        session = get_session_factory()()
        try:
            run = session.get(OrchestratorRun, run_id)
            if run is None:
                return
            run.status = "completed"
            # Store the full response (decision or clarification question).
            run.decision = response.model_dump()
            session.commit()
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        _mark_failed(run_id, f"decision_persist_failed: {type(exc).__name__}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/decide",
    response_model=OrchestratorRunOut,
    status_code=202,
    summary="Decide SLM vs LLM for a task (AI, conversational)",
    description=(
        "Start an AI-reasoned SLM/LLM decision and return immediately (202). "
        "The AI may return a decision, or ask a follow-up question if the "
        "task is ambiguous. Poll GET /orchestrator/decide/{run_id} for the "
        "result. When the response is a clarification question, send the "
        "user's answer back (with the full conversation) to continue. This "
        "avoids holding an HTTP request open for the duration of a slow "
        "reasoning-model call."
    ),
)
def decide_task(
    req: OrchestratorRequest,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> OrchestratorRunOut:
    """Start an AI-reasoned decision and return immediately (202)."""
    run = OrchestratorRun(
        status="running",
        request=req.model_dump(),
        correlation_id=uuid.uuid4().hex,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background.add_task(_run_decision_background, run.id, req)

    return OrchestratorRunOut(
        id=run.id,
        status=run.status,
        correlation_id=run.correlation_id,
        error=run.error,
        created_at=run.created_at.isoformat() if run.created_at else "",
    )


@router.get(
    "/decide/{run_id}",
    response_model=OrchestratorResultOut,
    summary="Get a decision result",
)
def get_decision_run(
    run_id: str,
    db: Session = Depends(get_db),
) -> OrchestratorResultOut:
    """Poll a decision run for its result (decision or clarification)."""
    run = db.get(OrchestratorRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="decision_run_not_found")
    response = None
    if run.decision is not None:
        try:
            from app.schemas import OrchestratorResponse

            response = OrchestratorResponse.model_validate(run.decision)
        except Exception:  # noqa: BLE001
            response = None
    return OrchestratorResultOut(
        run=OrchestratorRunOut(
            id=run.id,
            status=run.status,
            correlation_id=run.correlation_id,
            error=run.error,
            created_at=run.created_at.isoformat() if run.created_at else "",
        ),
        response=response,
    )


@router.get(
    "/decide",
    response_model=list[OrchestratorRunOut],
    summary="List decision runs",
)
def list_decision_runs(
    db: Session = Depends(get_db),
) -> list[OrchestratorRunOut]:
    """List recent decision runs (most recent first)."""
    rows = db.execute(
        select(OrchestratorRun).order_by(OrchestratorRun.created_at.desc()).limit(50)
    ).scalars()
    return [
        OrchestratorRunOut(
            id=r.id,
            status=r.status,
            correlation_id=r.correlation_id,
            error=r.error,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]
