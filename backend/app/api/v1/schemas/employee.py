"""Employee schemas."""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional
from app.models.employee import EmploymentStatus, EmployeeType


class EmployeeCreate(BaseModel):
    """Create employee request."""

    employee_number: str = Field(..., min_length=1, max_length=50)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    department: str = Field(..., max_length=100)
    business_unit: Optional[str] = None
    role: str = Field(..., max_length=100)
    manager_id: Optional[int] = None
    hire_date: datetime
    employment_status: EmploymentStatus = EmploymentStatus.ACTIVE
    employee_type: EmployeeType = EmployeeType.FULL_TIME


class EmployeeUpdate(BaseModel):
    """Update employee request."""

    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    department: Optional[str] = None
    business_unit: Optional[str] = None
    role: Optional[str] = None
    manager_id: Optional[int] = None
    employment_status: Optional[EmploymentStatus] = None
    employee_type: Optional[EmployeeType] = None


class EmployeeResponse(BaseModel):
    """Employee response."""

    model_config = {"from_attributes": True}

    id: int
    employee_number: str
    first_name: str
    last_name: str
    email: str
    phone: Optional[str]
    department: str
    business_unit: Optional[str]
    legal_entity: str
    country: str
    role: str
    manager_id: Optional[int]
    employment_status: EmploymentStatus
    employee_type: EmployeeType
    hire_date: datetime
    termination_date: Optional[datetime]
    created_at: datetime
    updated_at: datetime


class EmployeeListResponse(BaseModel):
    """Employee list response."""

    total: int
    page: int
    page_size: int
    items: list[EmployeeResponse]
