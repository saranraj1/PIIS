"""FastAPI application factory and lifecycle orchestration for PIIS."""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timezone
import logging
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from piis.api.middleware import RequestCorrelationMiddleware
from piis.api.routers import audit, incidents, integrations, network, settings, system
from piis.api import ui
from piis.integrations import (
    JiraServiceManagementAdapter,
    OSSAlarmAdapter,
    PrometheusAdapter,
    ServiceNowAdapter,
)
from piis.observability.logging import get_correlation_id, setup_structured_logging

logger = logging.getLogger("piis.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown orchestration."""
    setup_structured_logging()
    logger.info("Initializing PIIS API service...")

    # Wire up standard pipeline and adapters
    pipeline = incidents.get_pipeline()
    workflow = incidents.get_workflow()
    pipeline.register_adapter(ServiceNowAdapter())
    pipeline.register_adapter(JiraServiceManagementAdapter())
    pipeline.register_adapter(PrometheusAdapter())
    pipeline.register_adapter(OSSAlarmAdapter(vendor_hint="NOKIA"))

    logger.info("Registered standard adapters: ServiceNow, Jira, Prometheus, OSS/NMS")

    # Bootstrap baseline demonstration data so all workspaces and endpoints have active context
    from piis.api.bootstrap import bootstrap_demonstration_data
    try:
        bootstrap_demonstration_data(pipeline=pipeline, workflow=workflow)
    except Exception as exc:
        logger.warning(f"Demonstration data bootstrap failed: {exc}")

    yield
    logger.info("Gracefully shutting down PIIS API service...")


def create_app() -> FastAPI:
    """Create and configure the production FastAPI application."""
    app = FastAPI(
        title="PIIS — Production Incident Intelligence System (Telecom Edition)",
        description=(
            "Enterprise-integrable telecom incident triage, anomaly correlation, "
            "evidence retrieval, and human-in-the-loop decision-support platform."
        ),
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # Middleware
    app.add_middleware(RequestCorrelationMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Exception Handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        content = {
            "error": "HTTP_ERROR",
            "detail": exc.detail,
            "correlation_id": get_correlation_id(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if exc.headers and "X-PIIS-Error-Code" in exc.headers:
            content["code"] = exc.headers["X-PIIS-Error-Code"]
        return JSONResponse(
            status_code=exc.status_code,
            content=content,
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={
                "error": "REQUEST_VALIDATION_FAILED",
                "detail": str(exc),
                "correlation_id": get_correlation_id(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled exception on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": "An unexpected internal error occurred.",
                "correlation_id": get_correlation_id(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    # Routers
    app.include_router(system.router)
    app.include_router(incidents.router)
    app.include_router(integrations.router)
    app.include_router(audit.router)
    app.include_router(network.router)
    app.include_router(settings.router)
    app.include_router(ui.router)

    return app


app = create_app()
