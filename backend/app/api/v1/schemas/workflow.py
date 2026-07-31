"""Workflow schemas."""
from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.models.workflow import TriggerType, IntentCategory, WorkflowState


class WorkflowCreateRequest(BaseModel):
    """Create workflow request."""

    trigger_type: TriggerType
    employee_id: Optional[int] = None
    request_summary: str = Field(..., min_length=1, max_length=2000)
    request_data: Optional[Dict[str, Any]] = None


class WorkflowTransitionRequest(BaseModel):
    """Workflow state transition request."""

    to_state: WorkflowState
    reason: Optional[str] = None


class WorkflowTransitionResponse(BaseModel):
    """Workflow transition response."""

    workflow_id: str
    state: str
    previous_state: str
    updated_at: datetime
    version: int


class WorkflowTransitionDetail(BaseModel):
    """Workflow transition detail."""

    from_state: str
    to_state: str
    reason: Optional[str]
    triggered_by: Optional[str]
    created_at: datetime


class AgentExecutionDetail(BaseModel):
    agent_name: str
    execution_order: int
    success: bool
    output: Dict[str, Any]
    error_message: Optional[str] = None
    duration_ms: Optional[int] = None
    created_at: datetime


class WorkflowResponse(BaseModel):
    """Workflow response."""

    model_config = {"from_attributes": True}

    workflow_id: str
    id: int
    trigger_type: str
    intent: Optional[str]
    current_state: str
    previous_state: Optional[str]
    requester_id: int
    employee_id: Optional[int]
    request_summary: str
    retry_count: int
    max_retries: int
    error_message: Optional[str]
    paused_at: Optional[datetime]
    paused_reason: Optional[str]
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]
    version: int
    transitions: List[WorkflowTransitionDetail]
    agent_executions: List[AgentExecutionDetail]
    evidence_count: int


class WorkflowListItemResponse(BaseModel):
    """Workflow list item response."""

    model_config = {"from_attributes": True}

    workflow_id: str
    id: int
    trigger_type: str
    intent: Optional[str]
    current_state: str
    requester_id: int
    employee_id: Optional[int]
    request_summary: str
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime]


class WorkflowListResponse(BaseModel):
    """Workflow list response."""

    total: int
    page: int
    page_size: int
    items: List[WorkflowListItemResponse]


class SetIntentRequest(BaseModel):
    """Set workflow intent request."""

    intent: IntentCategory


class WorkflowPauseRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=1000)


class WorkflowActionResponse(BaseModel):
    workflow_id: str
    state: str
    paused_at: Optional[datetime] = None
    paused_reason: Optional[str] = None
    completed_at: Optional[datetime] = None
    retry_count: Optional[int] = None
    max_retries: Optional[int] = None


class WorkflowCancelRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=1000)


class ClarificationCreateRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    requested_from_id: int
    context: Optional[Dict[str, Any]] = None


class ClarificationResponseRequest(BaseModel):
    response: str = Field(..., min_length=1, max_length=5000)


class ClarificationResponse(BaseModel):
    clarification_id: int
    question: Optional[str] = None
    response: Optional[str] = None
    required_by: Optional[datetime] = None
    responded_at: Optional[datetime] = None


class WorkflowRunResponse(BaseModel):
    workflow_id: str
    state: str
    intent: Optional[str]
    agent_outputs: Dict[str, Dict[str, Any]]
    approval: Optional[Dict[str, Any]] = None
    clarification: Optional[Dict[str, Any]] = None
