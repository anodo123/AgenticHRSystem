"""Employee routes."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.models.employee import Employee
from app.security import get_current_user, has_permission
from app.api.v1.schemas.employee import (
    EmployeeCreate,
    EmployeeUpdate,
    EmployeeResponse,
    EmployeeListResponse,
)

router = APIRouter(tags=["Employees"])


@router.get(
    "/",
    response_model=EmployeeListResponse,
    dependencies=[Depends(get_current_user)],
)
async def list_employees(
    db: Session = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    department: Optional[str] = None,
    employment_status: Optional[str] = None,
):
    """List employees with pagination."""
    query = db.query(Employee)
    
    if department:
        query = query.filter(Employee.department == department)
    
    if employment_status:
        query = query.filter(Employee.employment_status == employment_status)
    
    total = query.count()
    employees = query.offset(skip).limit(limit).all()
    
    page = skip // limit + 1 if limit > 0 else 1
    
    return EmployeeListResponse(
        total=total,
        page=page,
        page_size=limit,
        items=[EmployeeResponse.model_validate(emp) for emp in employees],
    )


@router.get("/{employee_id}", response_model=EmployeeResponse)
async def get_employee(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get employee by ID."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    return EmployeeResponse.model_validate(employee)


@router.post(
    "/",
    response_model=EmployeeResponse,
    dependencies=[Depends(has_permission("modify_employee_data"))],
)
async def create_employee(
    request: EmployeeCreate,
    db: Session = Depends(get_db),
):
    """Create new employee."""
    # Check if employee number already exists
    existing = db.query(Employee).filter(
        Employee.employee_number == request.employee_number
    ).first()
    
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Employee number already exists",
        )
    
    # Check if email already exists
    existing_email = db.query(Employee).filter(
        Employee.email == request.email
    ).first()
    
    if existing_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    employee = Employee(
        employee_number=request.employee_number,
        first_name=request.first_name,
        last_name=request.last_name,
        email=request.email,
        phone=request.phone,
        department=request.department,
        business_unit=request.business_unit,
        role=request.role,
        manager_id=request.manager_id,
        hire_date=request.hire_date,
        employment_status=request.employment_status,
        employee_type=request.employee_type,
        legal_entity="Global",
        country="US",
    )
    
    db.add(employee)
    db.commit()
    db.refresh(employee)
    
    return EmployeeResponse.model_validate(employee)


@router.patch(
    "/{employee_id}",
    response_model=EmployeeResponse,
    dependencies=[Depends(has_permission("modify_employee_data"))],
)
async def update_employee(
    employee_id: int,
    request: EmployeeUpdate,
    db: Session = Depends(get_db),
):
    """Update employee."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    # Update only provided fields
    update_data = request.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(employee, field, value)
    
    db.commit()
    db.refresh(employee)
    
    return EmployeeResponse.model_validate(employee)


@router.get("/{employee_id}/manager", response_model=EmployeeResponse)
async def get_employee_manager(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get employee's manager."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    if not employee.manager_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee has no manager assigned",
        )
    
    manager = db.query(Employee).filter(Employee.id == employee.manager_id).first()
    
    if not manager:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Manager not found",
        )
    
    return EmployeeResponse.model_validate(manager)


@router.get("/{employee_id}/direct-reports", response_model=list[EmployeeResponse])
async def get_employee_direct_reports(
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get employee's direct reports."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )
    
    direct_reports = db.query(Employee).filter(
        Employee.manager_id == employee_id
    ).all()
    
    return [EmployeeResponse.model_validate(emp) for emp in direct_reports]
