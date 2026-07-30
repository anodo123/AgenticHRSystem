"""Observability API schemas."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel


class EvaluationResponse(BaseModel):
    model_config = {"from_attributes": True}

    evaluation_id: str
    workflow_id: int
    success: bool
    final_state: str
    duration_ms: Optional[int]
    agent_success_rate: float
    compliance_decision: Optional[str]
    approval_required: bool
    evidence_count: int
    retry_count: int
    scores: dict[str, Any]
    evaluated_at: datetime


class EvaluationListResponse(BaseModel):
    total: int
    items: list[EvaluationResponse]
