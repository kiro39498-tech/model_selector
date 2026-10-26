"""Model registry endpoints.

The registry is the source-backed ground truth. AI reasoning operates over it,
but verified registry data is never overridden by the AI's natural-language
explanation.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ModelRegistry
from app.schemas import ModelRegistryOut

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _to_out(m: ModelRegistry) -> ModelRegistryOut:
    return ModelRegistryOut(
        id=m.id,
        name=m.name,
        provider=m.provider,
        version=m.version,
        family=m.family,
        total_params=m.total_params,
        active_params=m.active_params,
        classification=m.classification,
        classification_reason=m.classification_reason,
        modalities=m.modalities or [],
        context_window=m.context_window,
        tool_calling=m.tool_calling,
        structured_output=m.structured_output,
        license=m.license,
        deployment_options=m.deployment_options or [],
        availability_status=m.availability_status,
        doc_url=m.doc_url,
        pricing=m.pricing,
        last_verified=m.last_verified,
        confidence=m.confidence,
        evidence_quality=m.evidence_quality,
    )


@router.get("", response_model=list[ModelRegistryOut])
def list_models(
    classification: str | None = None,
    db: Session = Depends(get_db),
) -> list[ModelRegistryOut]:
    stmt = select(ModelRegistry)
    if classification:
        stmt = stmt.where(ModelRegistry.classification == classification)
    rows = db.execute(stmt.order_by(ModelRegistry.provider, ModelRegistry.name)).scalars()
    return [_to_out(m) for m in rows]
