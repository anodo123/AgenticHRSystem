"""Employee and HR data models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Numeric, Text, Enum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.db.base import Base


class EmploymentStatus(str, PyEnum):
    """Employment status enum."""

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ON_LEAVE = "ON_LEAVE"
    TERMINATED = "TERMINATED"
    SUSPENDED = "SUSPENDED"


class EmployeeType(str, PyEnum):
    """Employee type enum."""

    FULL_TIME = "FULL_TIME"
    PART_TIME = "PART_TIME"
    CONTRACT = "CONTRACT"
    TEMPORARY = "TEMPORARY"
    INTERN = "INTERN"


class Employee(Base):
    """Employee model."""

    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_number = Column(String(50), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=True)
    department = Column(String(100), nullable=False)
    business_unit = Column(String(100), nullable=True)
    legal_entity = Column(String(100), nullable=False, default="Global")
    country = Column(String(50), nullable=False, default="US")
    manager_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    role = Column(String(100), nullable=False)
    employment_status = Column(Enum(EmploymentStatus), default=EmploymentStatus.ACTIVE, nullable=False)
    employee_type = Column(Enum(EmployeeType), default=EmployeeType.FULL_TIME, nullable=False)
    hire_date = Column(DateTime, nullable=False)
    termination_date = Column(DateTime, nullable=True)
    salary = Column(Numeric(15, 2), nullable=True)
    currency = Column(String(3), default="USD", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    data_sync_timestamp = Column(DateTime, nullable=True)  # For freshness tracking

    user = relationship("User", back_populates="employee", uselist=False)
    manager = relationship("Employee", remote_side=[id], backref="direct_reports")
    attendance_records = relationship("AttendanceRecord", back_populates="employee")
    leave_requests = relationship("LeaveRequest", back_populates="employee")
    payroll_records = relationship("PayrollRecord", back_populates="employee")


class AttendanceRecord(Base):
    """Attendance record model."""

    __tablename__ = "attendance_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    date = Column(DateTime, nullable=False, index=True)
    clock_in = Column(DateTime, nullable=True)
    clock_out = Column(DateTime, nullable=True)
    hours_worked = Column(Numeric(5, 2), nullable=True)
    status = Column(String(50), nullable=False, default="PRESENT")  # PRESENT, ABSENT, LATE, PARTIAL
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="attendance_records")


class LeaveRequest(Base):
    """Leave request model."""

    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    leave_type = Column(String(50), nullable=False)  # ANNUAL, SICK, PERSONAL, BEREAVEMENT
    start_date = Column(DateTime, nullable=False, index=True)
    end_date = Column(DateTime, nullable=False)
    days_requested = Column(Numeric(5, 2), nullable=False)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, APPROVED, REJECTED, CANCELLED
    reason = Column(Text, nullable=True)
    manager_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="leave_requests")


class PayrollRecord(Base):
    """Payroll record model."""

    __tablename__ = "payroll_records"

    id = Column(Integer, primary_key=True, index=True)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=False, index=True)
    payroll_period = Column(String(50), nullable=False, index=True)  # e.g., "2024-01"
    gross_salary = Column(Numeric(15, 2), nullable=False)
    overtime_amount = Column(Numeric(15, 2), default=0, nullable=False)
    deductions = Column(Numeric(15, 2), default=0, nullable=False)
    net_salary = Column(Numeric(15, 2), nullable=False)
    status = Column(String(50), nullable=False, default="DRAFT")  # DRAFT, PROCESSED, PAID, REVERSED
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    employee = relationship("Employee", back_populates="payroll_records")
