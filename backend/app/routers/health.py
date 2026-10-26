"""Health check endpoints for the application and database."""
from __future__ import annotations

from fastapi import APIRouter

from app.config import settings
from app.db import check_db
from app.services.ai_service import AIUnavailableError, check_ai

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    """Application health. Reports configuration status without secrets."""
    return {
        "status": "ok",
        "ai_configured": settings.ai_configured,
        "db_configured": settings.db_configured,
        "classification_threshold_billions": settings.classification_threshold_billions,
    }


@router.get("/health/db")
def db_health() -> dict:
    """Database health. Returns a clear error if the DB is unreachable."""
    try:
        ok = check_db()
        return {"status": "ok" if ok else "unreachable", "database": "reachable"}
    except Exception as exc:  # noqa: BLE001
        # Do not expose raw SQL errors or credentials.
        return {"status": "unreachable", "database": "unreachable", "detail": "database_unreachable"}


@router.get("/health/ai")
def ai_health() -> dict:
    """AI endpoint health. Returns a clear error if unavailable."""
    try:
        ok = check_ai()
        return {"status": "ok" if ok else "unavailable", "ai": "reachable"}
    except AIUnavailableError as exc:
        return {"status": "unavailable", "ai": "unavailable", "detail": str(exc)}
