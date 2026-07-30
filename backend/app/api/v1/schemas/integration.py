"""HR integration API schemas."""
from typing import Any

from pydantic import BaseModel, Field


class AdapterReadResponse(BaseModel):
    system: str
    success: bool
    data: dict[str, Any]
    fetched_at: str
    fresh: bool
    age_seconds: float


class AdapterMutationRequest(BaseModel):
    record_id: int | None = None
    course_id: str | None = None
    updates: dict[str, Any] = Field(default_factory=dict)


class AdapterMutationResponse(BaseModel):
    system: str
    success: bool
    data: dict[str, Any]
    dry_run: bool
