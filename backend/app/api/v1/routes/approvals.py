"""Approval request routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.schemas.approval import (
    ApprovalCancelRequest,
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalDelegateRequest,
    ApprovalListResponse,
    ApprovalResponse,
)
from app.db.session import get_db
from app.models.user import User
from app.models.approval import ApprovalStatus
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.security import get_current_user
from app.services.approval_service import ApprovalService

router = APIRouter(tags=["Approvals"])


def _result(value):
    success, error, payload = value
    if not success:
        code = 404 if error and "not found" in error.lower() else 400
        if error and (
            "required approver role" in error
            or "requested user" in error
            or "not authorized" in error
            or "Only the requester" in error
        ):
            code = 403
        raise HTTPException(status_code=code, detail=error)
    return payload


@router.post("/", response_model=ApprovalResponse)
async def create_approval(
    request: ApprovalCreateRequest, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = WorkflowRepository.get_workflow(db, request.workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    if workflow.requester_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot create approval for this workflow")
    return _result(ApprovalService.create_request(db, **request.model_dump()))


@router.get("/", response_model=ApprovalListResponse)
async def list_pending_approvals(
    skip: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=100),
    approval_status: ApprovalStatus = ApprovalStatus.PENDING,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    _, approvals = ApprovalRepository.list(db, status=approval_status, limit=10000)
    visible = [
        item for item in approvals if ApprovalService.can_view(item, current_user)
    ]
    page_items = visible[skip:skip + limit]
    return ApprovalListResponse(
        total=len(visible), page=skip // limit + 1, page_size=limit,
        items=[ApprovalResponse(**ApprovalService.serialize(item)) for item in page_items],
    )


@router.get("/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    approval_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    approval = ApprovalRepository.get(db, approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail="Approval request not found")
    if not ApprovalService.can_view(approval, current_user):
        raise HTTPException(status_code=403, detail="Cannot view this approval")
    return ApprovalResponse(**ApprovalService.serialize(approval))


@router.post("/{approval_id}/approve", response_model=ApprovalResponse)
async def approve(
    approval_id: str, request: ApprovalDecisionRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    return _result(ApprovalService.decide(
        db, approval_id=approval_id, approver=current_user,
        approve=True, comments=request.comments,
    ))


@router.post("/{approval_id}/reject", response_model=ApprovalResponse)
async def reject(
    approval_id: str, request: ApprovalDecisionRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    return _result(ApprovalService.decide(
        db, approval_id=approval_id, approver=current_user,
        approve=False, comments=request.comments,
    ))


@router.post("/{approval_id}/delegate", response_model=ApprovalResponse)
async def delegate(
    approval_id: str,
    request: ApprovalDelegateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _result(ApprovalService.delegate(
        db, approval_id=approval_id, delegator=current_user,
        delegated_to_id=request.delegated_to_id, reason=request.reason,
    ))


@router.post("/{approval_id}/cancel", response_model=ApprovalResponse)
async def cancel(
    approval_id: str,
    request: ApprovalCancelRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _result(ApprovalService.cancel(
        db, approval_id=approval_id, actor=current_user, reason=request.reason,
    ))


@router.post("/expired/process")
async def process_expired(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Administrator access required")
    return {"expired_count": ApprovalService.process_expired(db)}
