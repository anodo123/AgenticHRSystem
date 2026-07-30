"""API v1 router initialization."""
from fastapi import APIRouter

from app.api.v1.routes import (
    approvals,
    audit,
    auth,
    employees,
    health,
    integrations,
    observability,
    rag,
    tasks,
    workflows,
)

api_router = APIRouter()

# Include routers
api_router.include_router(health.router, prefix="/health")
api_router.include_router(auth.router, prefix="/auth")
api_router.include_router(employees.router, prefix="/employees")
api_router.include_router(audit.router, prefix="/audit")
api_router.include_router(workflows.router, prefix="/workflows")
api_router.include_router(approvals.router, prefix="/approvals")
api_router.include_router(rag.router, prefix="/rag")
api_router.include_router(integrations.router, prefix="/integrations")
api_router.include_router(tasks.router, prefix="/tasks")
api_router.include_router(observability.router)

__all__ = ["api_router"]
