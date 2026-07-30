"""Operational metrics and workflow evaluation endpoints."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.schemas.observability import EvaluationListResponse, EvaluationResponse
from app.db.session import get_db
from app.evaluation import WorkflowEvaluator
from app.repositories.evaluation_repository import EvaluationRepository
from app.security import has_permission
from app.services.observability_service import ObservabilityService

router = APIRouter(tags=["Observability"])
audit_access = [Depends(has_permission("view_audit"))]


@router.get("/metrics", dependencies=audit_access)
async def metrics(db: Session = Depends(get_db)):
    return ObservabilityService.snapshot(db)


@router.get("/evaluations", response_model=EvaluationListResponse, dependencies=audit_access)
async def evaluations(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    final_state: Optional[str] = None,
    success: Optional[bool] = None,
):
    total, items = EvaluationRepository.list(
        db, skip=skip, limit=limit, final_state=final_state, success=success
    )
    return EvaluationListResponse(total=total, items=items)


@router.post("/evaluations/refresh", dependencies=audit_access)
async def refresh_evaluations(db: Session = Depends(get_db)):
    items = WorkflowEvaluator.refresh_terminal(db)
    return {"evaluated": len(items)}


@router.post(
    "/evaluations/{workflow_id}",
    response_model=EvaluationResponse,
    dependencies=audit_access,
)
async def evaluate_workflow(workflow_id: str, db: Session = Depends(get_db)):
    evaluation = WorkflowEvaluator.evaluate(db, workflow_id)
    if not evaluation:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return evaluation
