"""Approval API schemas."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ApprovalCreateRequest(BaseModel):
    workflow_id: str
    proposed_action: str = Field(..., min_length=1, max_length=5000)
    affected_employee_id: Optional[int] = None
    risk_level: str = Field(..., pattern="^(LOW|MEDIUM|HIGH|CRITICAL)$")
    financial_impact: str = Field(..., pattern="^(NONE|LOW|MEDIUM|HIGH)$")
    policy_references: Optional[list[str]] = None
    evidence_summary: Optional[str] = None
    required_approver_roles: list[str] = Field(..., min_length=1)
    expiry_hours: Optional[int] = Field(default=None, ge=1, le=720)


class ApprovalDecisionRequest(BaseModel):
    comments: Optional[str] = Field(default=None, max_length=2000)


class ApprovalDelegateRequest(BaseModel):
    delegated_to_id: int
    reason: Optional[str] = Field(default=None, max_length=2000)


class ApprovalCancelRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=2000)


class ApprovalResponse(BaseModel):
    approval_id: str
    workflow_id: str
    proposed_action: str
    risk_level: str
    financial_impact: str
    required_approver_roles: list[str]
    status: str
    expires_at: datetime
    resolved_at: Optional[datetime]
    approver_id: Optional[int]
    decision_comments: Optional[str]
    current_level: int
    total_levels: int
    current_required_role: Optional[str]
    delegated_to_id: Optional[int]
    delegated_by_id: Optional[int]
    delegation_reason: Optional[str]
    decisions: list[dict]


class ApprovalListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ApprovalResponse]
