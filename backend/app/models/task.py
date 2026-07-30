"""Task scheduling models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.db.base import Base


class TaskPriority(str, PyEnum):
    """Task priority levels."""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ScheduledTask(Base):
    """Scheduled task configuration."""

    __tablename__ = "scheduled_tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    trigger_type = Column(String(50), nullable=False)  # SCHEDULE, MANUAL, EVENT
    priority = Column(SQLEnum(TaskPriority), default=TaskPriority.MEDIUM, nullable=False)
    is_enabled = Column(Boolean, default=True, nullable=False, index=True)
    schedule_cron = Column(String(100), nullable=True)  # Cron expression
    target_scope = Column(String(100), nullable=True)  # ALL_EMPLOYEES, DEPARTMENT, COUNTRY, etc.
    target_scope_value = Column(String(255), nullable=True)
    workflow_type = Column(String(100), nullable=False)  # POLICY_QUERY, PAYROLL_ANOMALY, etc.
    task_payload = Column(JSON, nullable=True)
    retry_config = Column(JSON, nullable=True)  # {"max_retries": 3, "backoff": "exponential"}
    timeout_seconds = Column(Integer, nullable=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    owner_name = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_run_at = Column(DateTime, nullable=True)
    next_run_at = Column(DateTime, nullable=True)

    runs = relationship("TaskRun", back_populates="task", cascade="all, delete-orphan")


class TaskRun(Base):
    """Task execution record."""

    __tablename__ = "task_runs"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("scheduled_tasks.id"), nullable=False, index=True)
    run_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), nullable=False, default="PENDING")  # PENDING, RUNNING, SUCCESS, FAILED
    triggered_by = Column(String(50), nullable=False)  # SCHEDULE, MANUAL, EVENT
    triggered_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    results = Column(JSON, nullable=True)  # Workflows created, anomalies detected, etc.
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    task = relationship("ScheduledTask", back_populates="runs")
