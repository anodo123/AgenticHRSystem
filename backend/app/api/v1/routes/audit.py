"""Audit log routes."""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.audit import AuditLog
from app.security import has_permission
from pydantic import BaseModel
from datetime import datetime


class AuditLogResponse(BaseModel):
    """Audit log response."""

    model_config = {"from_attributes": True}

    id: int
    event_type: str
    actor_id: Optional[int]
    actor_role: Optional[str]
    workflow_id: Optional[int]
    entity_type: Optional[str]
    entity_id: Optional[int]
    action: Optional[str]
    decision: Optional[str]
    timestamp: datetime


class AuditLogListResponse(BaseModel):
    """Audit log list response."""

    total: int
    page: int
    page_size: int
    items: list[AuditLogResponse]


router = APIRouter(tags=["Audit"])


@router.get(
    "/",
    response_model=AuditLogListResponse,
    dependencies=[Depends(has_permission("view_audit"))],
)
async def list_audit_logs(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    event_type: Optional[str] = None,
    actor_id: Optional[int] = None,
    workflow_id: Optional[int] = None,
):
    """List audit logs."""
    query = db.query(AuditLog)
    
    if event_type:
        query = query.filter(AuditLog.event_type == event_type)
    
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    
    if workflow_id:
        query = query.filter(AuditLog.workflow_id == workflow_id)
    
    total = query.count()
    logs = query.order_by(AuditLog.timestamp.desc()).offset(skip).limit(limit).all()
    
    page = skip // limit + 1 if limit > 0 else 1
    
    return AuditLogListResponse(
        total=total,
        page=page,
        page_size=limit,
        items=[AuditLogResponse.model_validate(log) for log in logs],
    )
