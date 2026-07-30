"""Workflow routes."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.security import get_current_user
from app.models.workflow import WorkflowState
from app.services.workflow_service import WorkflowService
from app.repositories.workflow_repository import WorkflowRepository
from app.api.v1.schemas.workflow import (
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowListResponse,
    WorkflowListItemResponse,
    WorkflowTransitionRequest,
    WorkflowTransitionResponse,
    SetIntentRequest,
    WorkflowPauseRequest,
    WorkflowActionResponse,
    WorkflowCancelRequest,
    ClarificationCreateRequest,
    ClarificationResponseRequest,
    ClarificationResponse,
    WorkflowRunResponse,
)
from typing import Optional
from app.services.agent_orchestration import AgentOrchestrationService

router = APIRouter(tags=["Workflows"])


def _require_workflow_access(workflow, current_user: User) -> None:
    if workflow.requester_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Cannot modify this workflow")


def _service_result(result):
    success, error, payload = result
    if not success:
        code = status.HTTP_404_NOT_FOUND if error and "not found" in error.lower() else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=error)
    return payload


@router.post("/", response_model=dict)
async def create_workflow(
    request: WorkflowCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new workflow."""
    result = WorkflowService.create_workflow(
        db=db,
        trigger_type=request.trigger_type,
        requester_id=current_user.id,
        employee_id=request.employee_id,
        request_summary=request.request_summary,
        request_data=request.request_data,
    )
    return result


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    state: Optional[str] = None,
    requester_id: Optional[int] = None,
):
    """List workflows."""
    # Parse state enum if provided
    workflow_state = None
    if state:
        try:
            workflow_state = WorkflowState[state.upper()]
        except KeyError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid state: {state}",
            )

    # If filtering by requester, verify permission
    if requester_id and requester_id != current_user.id:
        # Check if user has permission to view others' workflows
        if not current_user.is_superuser:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Cannot view other users' workflows",
            )

    total, workflows = WorkflowRepository.list_workflows(
        db=db,
        skip=skip,
        limit=limit,
        state=workflow_state,
        requester_id=requester_id or current_user.id,
    )

    page = skip // limit + 1 if limit > 0 else 1

    return WorkflowListResponse(
        total=total,
        page=page,
        page_size=limit,
        items=[
            WorkflowListItemResponse.model_validate(wf)
            for wf in workflows
        ],
    )


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get workflow details."""
    details = WorkflowService.get_workflow_details(db, workflow_id)

    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    # Check authorization
    if details["requester_id"] != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this workflow",
        )

    return WorkflowResponse(**details)


@router.post("/{workflow_id}/transition", response_model=WorkflowTransitionResponse)
async def transition_workflow(
    workflow_id: str,
    request: WorkflowTransitionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Transition workflow to new state."""
    # Get workflow to check authorization
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.requester_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify this workflow",
        )

    # Perform transition
    success, error_msg, result = WorkflowService.transition_workflow(
        db=db,
        workflow_id=workflow_id,
        to_state=request.to_state,
        reason=request.reason,
        triggered_by="user",
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg,
        )

    return WorkflowTransitionResponse(**result)


@router.post("/{workflow_id}/intent", response_model=dict)
async def set_workflow_intent(
    workflow_id: str,
    request: SetIntentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Set workflow intent."""
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.requester_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify this workflow",
        )

    result = WorkflowService.set_intent(db, workflow_id, request.intent)
    return result


@router.get("/{workflow_id}/timeline", response_model=dict)
async def get_workflow_timeline(
    workflow_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get workflow execution timeline."""
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workflow not found",
        )

    if workflow.requester_id != current_user.id and not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view this workflow",
        )

    transitions = WorkflowRepository.get_workflow_transitions(db, workflow.id)
    evidence = WorkflowRepository.get_workflow_evidence(db, workflow.id)

    return {
        "workflow_id": workflow.workflow_id,
        "state": workflow.current_state.value,
        "created_at": workflow.created_at,
        "updated_at": workflow.updated_at,
        "completed_at": workflow.completed_at,
        "transitions": [
            {
                "from_state": t.from_state.value,
                "to_state": t.to_state.value,
                "reason": t.transition_reason,
                "triggered_by": t.triggered_by,
                "created_at": t.created_at,
            }
            for t in transitions
        ],
        "evidence": [
            {
                "evidence_type": e.evidence_type,
                "source": e.source,
                "confidence_score": e.confidence_score,
                "created_at": e.created_at,
            }
            for e in evidence
        ],
    }


@router.post("/{workflow_id}/pause", response_model=WorkflowActionResponse)
async def pause_workflow(
    workflow_id: str, request: WorkflowPauseRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _require_workflow_access(workflow, current_user)
    return _service_result(WorkflowService.pause_workflow(db, workflow_id, request.reason))


@router.post("/{workflow_id}/resume", response_model=WorkflowActionResponse)
async def resume_workflow(
    workflow_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _require_workflow_access(workflow, current_user)
    return _service_result(WorkflowService.resume_workflow(db, workflow_id))


@router.post("/{workflow_id}/cancel", response_model=WorkflowActionResponse)
async def cancel_workflow(
    workflow_id: str, request: WorkflowCancelRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _require_workflow_access(workflow, current_user)
    return _service_result(WorkflowService.cancel_workflow(db, workflow_id, request.reason))


@router.post("/{workflow_id}/retry", response_model=WorkflowActionResponse)
async def retry_workflow(
    workflow_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _require_workflow_access(workflow, current_user)
    return _service_result(WorkflowService.retry_workflow(db, workflow_id))


@router.post("/{workflow_id}/run", response_model=WorkflowRunResponse)
async def run_workflow(
    workflow_id: str, db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Run or continue the persisted five-agent workflow."""
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _require_workflow_access(workflow, current_user)
    return _service_result(AgentOrchestrationService.run(db, workflow_id))


@router.post("/{workflow_id}/clarifications", response_model=ClarificationResponse)
async def request_clarification(
    workflow_id: str, request: ClarificationCreateRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow not found")
    _require_workflow_access(workflow, current_user)
    return _service_result(WorkflowService.request_clarification(
        db, workflow_id, request.question, request.requested_from_id, request.context,
    ))


@router.post("/clarifications/{clarification_id}/response", response_model=ClarificationResponse)
async def respond_to_clarification(
    clarification_id: int, request: ClarificationResponseRequest,
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    return _service_result(WorkflowService.respond_to_clarification(
        db, clarification_id, request.response, current_user.id,
    ))
