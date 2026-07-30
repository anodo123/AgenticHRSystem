"""
DARWINBOXAI - Self-Healing HR Operations Platform
FastAPI Main Application
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
import logging
from time import perf_counter
from uuid import uuid4
from contextlib import asynccontextmanager
from sqlalchemy import text

from app.core.config import get_settings
from app.observability.logging import (
    configure_logging,
    reset_correlation_id,
    set_correlation_id,
)
from app.observability.metrics import MetricsCollector
from app.observability.rate_limit import RateLimiter

settings = get_settings()

# Configure structured logging
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
rate_limiter = RateLimiter(settings.rate_limit_requests_per_minute)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop the in-process durable task dispatcher."""
    from app.workers.task_scheduler import TaskScheduler

    TaskScheduler.start()
    try:
        yield
    finally:
        TaskScheduler.shutdown()


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title="DARWINBOXAI",
        description="Self-Healing HR Operations Platform with Agentic Workflows",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add request logging middleware
    @app.middleware("http")
    async def log_requests(request: Request, call_next):
        correlation_id = request.headers.get(settings.correlation_id_header) or str(uuid4())
        correlation_id = correlation_id[:128]
        token = set_correlation_id(correlation_id)
        started = perf_counter()
        excluded = {"/health", "/ready", "/metrics", "/api/docs", "/api/openapi.json"}
        try:
            if settings.rate_limiting_enabled and request.url.path not in excluded:
                client = request.client.host if request.client else "unknown"
                allowed, retry_after = rate_limiter.allow(client)
                if not allowed:
                    response = JSONResponse(
                        status_code=429,
                        content={"detail": "Rate limit exceeded"},
                        headers={"Retry-After": str(retry_after)},
                    )
                else:
                    response = await call_next(request)
            else:
                response = await call_next(request)
            duration_ms = (perf_counter() - started) * 1000
            response.headers[settings.correlation_id_header] = correlation_id
            MetricsCollector.observe_request(
                request.method, request.url.path, response.status_code, duration_ms
            )
            logger.info(
                "request_completed",
                extra={
                    "event_type": "api_request",
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round(duration_ms, 3),
                },
            )
            return response
        finally:
            reset_correlation_id(token)

    # Health check endpoints
    @app.get("/health", tags=["System"])
    async def health():
        """Health check endpoint."""
        return {"status": "ok", "service": "DARWINBOXAI"}

    @app.get("/ready", tags=["System"])
    async def ready():
        """Readiness check endpoint."""
        if not settings.openai_api_key:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "error": "OPENAI_API_KEY_not_configured"},
            )
        # Check database connection
        try:
            from app.db.session import SessionLocal
            db = SessionLocal()
            db.execute(text("SELECT 1"))
            db.close()
            return {"status": "ready", "database": "connected"}
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "error": "database_unavailable"}
            )

    @app.get("/metrics", tags=["System"])
    async def metrics():
        """Prometheus-style metrics endpoint."""
        return PlainTextResponse(
            MetricsCollector.prometheus(),
            media_type="text/plain; version=0.0.4",
        )

    # Include API routes
    from app.api.v1 import api_router
    app.include_router(api_router, prefix=settings.api_v1_str)

    return app


# Create application instance
app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=get_settings().app_debug,
    )
