"""Policy RAG and incident memory API schemas."""
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class PolicyIngestRequest(BaseModel):
    policy_id: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    policy_type: str
    country: str
    legal_entity: str
    business_unit: Optional[str] = None
    employee_type: Optional[str] = "ALL"
    version: str = "1.0"
    effective_from: datetime
    effective_to: Optional[datetime] = None
    confidentiality: str = "PUBLIC"
    source_file: Optional[str] = None
    source_format: str = "txt"
    status: str = "ACTIVE"
    content: str = Field(..., min_length=1)


class PolicyResponse(BaseModel):
    policy_id: str
    title: str
    description: Optional[str]
    policy_type: str
    country: str
    legal_entity: str
    business_unit: Optional[str]
    employee_type: Optional[str]
    version: str
    effective_from: datetime
    effective_to: Optional[datetime]
    confidentiality: str
    status: str
    checksum: Optional[str]
    chunk_count: int
    created_at: datetime


class PolicySearchResponse(BaseModel):
    query: str
    total: int
    items: list[dict[str, Any]]


class IncidentCreateRequest(BaseModel):
    workflow_id: str
    incident_type: str
    summary: str = Field(..., min_length=1)
    symptoms: Optional[list | dict] = None
    root_cause: Optional[str] = None
    resolution: Optional[str] = None
    affected_systems: Optional[list[str]] = None
    country: Optional[str] = None
    business_unit: Optional[str] = None
    outcome: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class IncidentResponse(BaseModel):
    incident_id: str
    workflow_id: str
    incident_type: str
    sanitized_summary: str
    outcome: Optional[str]
    confidence: Optional[float]
    created_at: datetime


class IncidentSearchResponse(BaseModel):
    query: str
    total: int
    items: list[dict[str, Any]]
