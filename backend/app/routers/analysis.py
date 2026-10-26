"""Architecture analysis endpoints.

Uses the configured Qwen endpoint as the architecture reasoning engine.
The AI response is validated against a versioned Pydantic schema. If validation
fails, a bounded repair is attempted. Failed responses are preserved for
diagnostics (excluding sensitive information).
"""
from __future__ import annotations

import json
import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db, get_session_factory
from app.models import AnalysisRun, Project, Requirement
from app.schemas import AnalysisResponse, AnalysisResultOut, AnalysisRunOut
from app.services.ai_service import AIServiceError, chat_json

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/analysis", tags=["analysis"])

# Cap the analysis output to keep generation time bounded. The prompt is kept
# The prompt is compact and the schema is enforced server-side. The cap must be
# large enough for a full blueprint (a complete JSON can exceed 4k tokens when
# the model emits verbose rationale/evidence). Because the AI call is streamed,
# a larger cap only adds generation time, not a connection-timeout risk.
_ANALYSIS_MAX_TOKENS = 16384

SYSTEM_PROMPT = (
    "You are a senior solution architect and AI/ML engineer. "
    "You analyze a software application's approved requirements and produce a "
    "structured architecture blueprint. "
    "You must NOT fabricate model names, parameter counts, benchmark results, "
    "prices, or citations. Distinguish verified facts from estimates and "
    "hypotheses. For each task that requires a generative AI model, provide up "
    "to three ranked recommendations based on task suitability and demonstrated "
    "quality, NOT lowest price. Report cost separately. "
    "A model with fewer than 150 billion parameters is classified as an SLM; "
    "150 billion or more is an LLM. Unknown parameter counts are 'unknown'. "
    "Respond ONLY with a JSON object matching the provided schema."
)


def _get_project(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="project_not_found")
    return project


def _build_messages(project_id: str, db: Session) -> list[dict[str, str]]:
    """Build the analysis prompt from approved requirements and the registry."""
    requirements = db.execute(
        select(Requirement).where(Requirement.project_id == project_id)
    ).scalars()

    req_text = "\n".join(
        f"- [{r.code}] ({r.category}) {r.description}" for r in requirements
    )
    # Keep the prompt compact to reduce generation time. The full schema is
    # enforced server-side by Pydantic; the prompt only needs to convey the
    # shape and the no-fabrication rule.
    user_content = (
        f"Approved requirements:\n{req_text or '(none)'}\n\n"
        "Return a JSON object with keys: application_summary, "
        "confirmed_requirements, remaining_uncertainties, components, risks, "
        "validation_plan, consistency_checks, implementation_roadmap. "
        "Each component: component_id, name, purpose, ai_required, "
        "recommended_approach, classification, model_recommendations, "
        "decision_rationale, evidence, alternatives, risks, requirement_ids, "
        "confidence, unresolved_questions. "
        "Each model_recommendation: rank, model_name, provider, total_params, "
        "classification, deployment_option, rationale, evidence, strengths, "
        "weaknesses, confidence, unverified, source_links, verified. "
        "Only set verified=true for models confirmable from the registry. "
        "Do not invent benchmark scores, prices, or citations. "
        "Be concise; omit optional fields when not applicable."
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def _extract_json_object(text: str) -> str:
    """Extract the outermost JSON object from possibly prose-wrapped text.

    A reasoning model may emit prose before/after the JSON, or wrap it in
    markdown fences. This returns the substring from the first '{' to the
    matching last '}'.
    """
    # Strip markdown code fences if present.
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
    # Close an unterminated string.
    if in_string:
        out.append('"')
    # Close any open brackets/braces.
    for opener in reversed(stack):
        out.append("}" if opener == "{" else "]")
    return "".join(out)


def _validate(raw: str) -> AnalysisResponse:
    """Validate raw AI text as an AnalysisResponse.

    Tolerates a JSON object wrapped in markdown fences or prose, and repairs
    a JSON object truncated mid-generation (e.g. by the token cap).
    """
    candidate = _extract_json_object(raw)
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        # Attempt to repair a truncated object before giving up.
        try:
            data = json.loads(_repair_truncated_json(candidate))
        except json.JSONDecodeError as exc:
            raise AIServiceError(f"AI response is not valid JSON: {exc}") from exc
    try:
        return AnalysisResponse.model_validate(data)
    except Exception as exc:  # noqa: BLE001 - save raw for diagnostics
        try:
            with open("_analysis_validation_error.txt", "w", encoding="utf-8") as f:
                f.write(f"ERROR: {exc}\n\nRAW:\n{raw}")
        except Exception:  # noqa: BLE001
            pass
        raise


def _mark_failed(run_id: str, error: str) -> None:
    """Mark a run as failed in a fresh, short-lived session."""
    try:
        session = get_session_factory()()
        try:
            run = session.get(AnalysisRun, run_id)
            if run is not None:
                run.status = "failed"
                run.error = error
                session.commit()
        finally:
            session.close()
    except Exception:  # noqa: BLE001 - never let a background task raise
        pass


def _run_analysis_background(project_id: str, run_id: str) -> None:
    """Execute the analysis in the background (a worker thread).

    Crucially, this does NOT hold a database connection across the slow AI
    call. It opens a session only to build the prompt, closes it, performs the
    AI call, then opens a fresh session to persist the result. This avoids the
    Neon connection being closed unexpectedly during a long-running request.
    """
    # 1. Build the prompt in a short-lived session.
    try:
        session = get_session_factory()()
        try:
            messages = _build_messages(project_id, session)
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        _mark_failed(run_id, f"analysis_setup_failed: {type(exc).__name__}")
        return

    # 2. Perform the AI call with NO database connection held.
    try:
        result, _meta = chat_json(
            messages,
            _validate,
            correlation_id=run_id,
            max_tokens=_ANALYSIS_MAX_TOKENS,
            repair_prompt=(
                "Your previous response was not valid JSON or did not match the "
                "required schema. Return ONLY a valid JSON object matching the "
                "schema, with no prose outside the JSON."
            ),
        )
    except AIServiceError as exc:
        _mark_failed(run_id, str(exc))
        return
    except Exception as exc:  # noqa: BLE001
        _mark_failed(run_id, f"analysis_failed: {type(exc).__name__}")
        return

    # 3. Persist the result in a fresh session.
    try:
        session = get_session_factory()()
        try:
            run = session.get(AnalysisRun, run_id)
            if run is None:
                return
            run.status = "completed"
            run.result = result.model_dump()
            session.commit()
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        _mark_failed(run_id, f"analysis_persist_failed: {type(exc).__name__}")


@router.post("", response_model=AnalysisRunOut, status_code=202)
def run_analysis(
    project_id: str,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> AnalysisRunOut:
    """Start architecture analysis and return immediately (202).

    The heavy AI work runs in the background; the client polls
    GET /analysis/{run_id} for the result. This avoids holding an HTTP
    request (and a database connection) open for the duration of a slow
    reasoning-model call, which previously caused client/proxy timeouts and
    Neon connection drops.
    """
    project = _get_project(db, project_id)
    if project.status != "approved":
        raise HTTPException(
            status_code=409,
            detail="analysis_requires_approved_requirements",
        )

    run = AnalysisRun(
        project_id=project_id,
        status="running",
        correlation_id=uuid.uuid4().hex,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    background.add_task(_run_analysis_background, project_id, run.id)

    return AnalysisRunOut(
        id=run.id,
        project_id=run.project_id,
        status=run.status,
        correlation_id=run.correlation_id,
        error=run.error,
        created_at=run.created_at.isoformat() if run.created_at else "",
    )


@router.get("", response_model=list[AnalysisRunOut])
def list_runs(project_id: str, db: Session = Depends(get_db)) -> list[AnalysisRunOut]:
    _get_project(db, project_id)
    rows = db.execute(
        select(AnalysisRun).where(AnalysisRun.project_id == project_id).order_by(
            AnalysisRun.created_at.desc()
        )
    ).scalars()
    return [
        AnalysisRunOut(
            id=r.id,
            project_id=r.project_id,
            status=r.status,
            correlation_id=r.correlation_id,
            error=r.error,
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.get("/{run_id}", response_model=AnalysisResultOut)
def get_run(
    project_id: str,
    run_id: str,
    db: Session = Depends(get_db),
) -> AnalysisResultOut:
    _get_project(db, project_id)
    run = db.get(AnalysisRun, run_id)
    if run is None or run.project_id != project_id:
        raise HTTPException(status_code=404, detail="analysis_run_not_found")
    result = None
    if run.result is not None:
        try:
            result = AnalysisResponse.model_validate(run.result)
        except Exception:  # noqa: BLE001
            result = None
    return AnalysisResultOut(
        run=AnalysisRunOut(
            id=run.id,
            project_id=run.project_id,
            status=run.status,
            correlation_id=run.correlation_id,
            error=run.error,
            created_at=run.created_at.isoformat() if run.created_at else "",
        ),
        result=result,
    )
