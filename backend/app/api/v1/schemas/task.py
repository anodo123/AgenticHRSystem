"""Task scheduling API schemas."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.task import TaskPriority


class TaskCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    trigger_type: str = Field(..., pattern="^(SCHEDULE|MANUAL|EVENT)$")
    priority: TaskPriority = TaskPriority.MEDIUM
    is_enabled: bool = True
    schedule_cron: Optional[str] = None
    target_scope: Optional[str] = Field(
        default=None,
        pattern="^(NONE|ALL_EMPLOYEES|DEPARTMENT|COUNTRY|EMPLOYEE)$",
    )
    target_scope_value: Optional[str] = None
    workflow_type: str
    task_payload: Optional[dict[str, Any]] = None
    retry_config: Optional[dict[str, Any]] = None
    timeout_seconds: Optional[int] = Field(default=3600, ge=1, le=86400)


class TaskResponse(BaseModel):
    task_id: str
    name: str
    description: Optional[str]
    trigger_type: str
    priority: str
    is_enabled: bool
    schedule_cron: Optional[str]
    target_scope: Optional[str]
    target_scope_value: Optional[str]
    workflow_type: str
    task_payload: Optional[dict[str, Any]]
    retry_config: Optional[dict[str, Any]]
    timeout_seconds: Optional[int]
    owner_id: Optional[int]
    owner_name: Optional[str]
    last_run_at: Optional[datetime]
    next_run_at: Optional[datetime]
    created_at: datetime


class TaskListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TaskResponse]


class TaskRunResponse(BaseModel):
    run_id: str
    task_id: str
    status: str
    triggered_by: str
    triggered_by_user_id: Optional[int]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    results: Optional[dict[str, Any]]
    error_message: Optional[str]
    retry_count: int
    next_retry_at: Optional[datetime]
    created_at: datetime


class TaskRunListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TaskRunResponse]


class TaskEnableRequest(BaseModel):
    is_enabled: bool
