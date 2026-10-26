"""FastAPI application entrypoint.

Provides:
- Application health and database health checks.
- Structured error handling (no raw exception traces or secrets to clients).
- Request correlation IDs.
- CORS configuration.
- Versioned API routes under /api/v1.
"""
from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.db import check_db
from app.services.ai_service import AIServiceError, AIUnavailableError, check_ai

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="AI Application Architect",
        version="0.1.0",
        description=(
            "Design a complete software application and determine the best AI "
            "model for each task within it.\n\n"
            "The **Orchestrator** is the core service: given a task or query, "
            "it decides whether that task should be handled by a Small "
            "Language Model (SLM) or a Large Language Model (LLM). SLMs suit "
            "specific, narrow, well-defined tasks (classification, "
            "extraction, routing, short summarization, simple Q&A); LLMs "
            "suit open-ended, complex, multi-step, creative, or "
            "knowledge-heavy tasks (reasoning, planning, analysis, "
            "long-form generation).\n\n"
            "The orchestrator is **AI-driven and conversational**: if a task "
            "is ambiguous or missing key detail, it asks a follow-up question "
            "instead of guessing, then decides once it has enough context.\n\n"
            "Key endpoints:\n"
            "- `POST /api/v1/orchestrator/decide` — start an AI decision "
            "(async; returns 202, poll for the result). The result is either "
            "a decision or a clarification question.\n"
            "- `GET /api/v1/orchestrator/decide/{run_id}` — poll a run for "
            "its result.\n"
            "- `GET /api/v1/orchestrator/decide` — list recent runs."
        ),
    )

    # CORS — configurable; "*" only for local development.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def correlation_id_middleware(request: Request, call_next):
        cid = request.headers.get("x-correlation-id") or uuid.uuid4().hex
        response = await call_next(request)
        response.headers["x-correlation-id"] = cid
        return response

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail if isinstance(exc.detail, str) else "error",
                "correlation_id": request.headers.get("x-correlation-id", ""),
            },
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception(request: Request, exc: RequestValidationError):
        # Return a clean, bounded validation error (no secrets).
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation_error",
                "detail": exc.errors(),
                "correlation_id": request.headers.get("x-correlation-id", ""),
            },
        )

    @app.exception_handler(AIServiceError)
    async def _ai_exception(request: Request, exc: AIServiceError):
        # Clear, understandable error; never expose credentials or traces.
        return JSONResponse(
            status_code=503,
            content={
                "error": "ai_service_unavailable",
                "detail": str(exc),
                "correlation_id": request.headers.get("x-correlation-id", ""),
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception(request: Request, exc: Exception):
        # Log server-side; return a generic error to the client.
        logger.exception("Unhandled error (correlation_id=%s)", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "detail": "An unexpected error occurred.",
                "correlation_id": request.headers.get("x-correlation-id", ""),
            },
        )

    _register_routes(app)
    return app


def _register_routes(app: FastAPI) -> None:
    from app.routers import (
        analysis,
        evaluations,
        health,
        models,
        orchestrator,
        projects,
        requirements,
    )

    app.include_router(health.router)
    app.include_router(projects.router)
    app.include_router(requirements.router)
    app.include_router(analysis.router)
    app.include_router(models.router)
    app.include_router(evaluations.router)
    app.include_router(orchestrator.router)


app = create_app()
