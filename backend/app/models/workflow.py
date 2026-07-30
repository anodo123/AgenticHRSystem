"""Workflow and workflow transition models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.db.base import Base


class TriggerType(str, PyEnum):
    """Workflow trigger types."""

    EMPLOYEE_REQUEST = "EMPLOYEE_REQUEST"
    HR_OPERATIONS_REQUEST = "HR_OPERATIONS_REQUEST"
    SYSTEM_EVENT = "SYSTEM_EVENT"
    SCHEDULED_SCAN = "SCHEDULED_SCAN"


class IntentCategory(str, PyEnum):
    """Intent categories."""

    POLICY_QUERY = "POLICY_QUERY"
    PAYROLL_ANOMALY = "PAYROLL_ANOMALY"
    ATTENDANCE_ANOMALY = "ATTENDANCE_ANOMALY"
    LEAVE_ANOMALY = "LEAVE_ANOMALY"
    BENEFITS_ANOMALY = "BENEFITS_ANOMALY"
    LMS_ANOMALY = "LMS_ANOMALY"
    DATA_CORRECTION = "DATA_CORRECTION"
    GENERAL_HR_REQUEST = "GENERAL_HR_REQUEST"
    UNKNOWN = "UNKNOWN"


class WorkflowState(str, PyEnum):
    """Workflow states."""

    RECEIVED = "RECEIVED"
    AUTHENTICATED = "AUTHENTICATED"
    AUTHORIZED = "AUTHORIZED"
    CLASSIFYING = "CLASSIFYING"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    CONTEXT_RETRIEVAL = "CONTEXT_RETRIEVAL"
    DATA_FRESHNESS_CHECK = "DATA_FRESHNESS_CHECK"
    INVESTIGATING = "INVESTIGATING"
    POLICY_RETRIEVAL = "POLICY_RETRIEVAL"
    ACTION_PROPOSED = "ACTION_PROPOSED"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    FAILED = "FAILED"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class Workflow(Base):
    """Workflow model."""

    __tablename__ = "workflows"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(String(50), unique=True, nullable=False, index=True)
    trigger_type = Column(SQLEnum(TriggerType), nullable=False)
    intent = Column(SQLEnum(IntentCategory), nullable=True)
    current_state = Column(SQLEnum(WorkflowState), default=WorkflowState.RECEIVED, nullable=False, index=True)
    previous_state = Column(SQLEnum(WorkflowState), nullable=True)
    requester_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    request_summary = Column(Text, nullable=False)
    request_data = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    error_message = Column(Text, nullable=True)
    paused_at = Column(DateTime, nullable=True)
    paused_reason = Column(Text, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    requester = relationship("User")
    employee = relationship("Employee")
    transitions = relationship("WorkflowTransition", back_populates="workflow", cascade="all, delete-orphan")
    agent_executions = relationship("AgentExecution", back_populates="workflow", cascade="all, delete-orphan")
    evidence = relationship("WorkflowEvidence", back_populates="workflow", cascade="all, delete-orphan")
    clarifications = relationship("ClarificationRequest", back_populates="workflow", cascade="all, delete-orphan")
    approvals = relationship("ApprovalRequest", back_populates="workflow", cascade="all, delete-orphan")


class WorkflowTransition(Base):
    """Workflow state transition record."""

    __tablename__ = "workflow_transitions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    from_state = Column(SQLEnum(WorkflowState), nullable=False)
    to_state = Column(SQLEnum(WorkflowState), nullable=False)
    transition_reason = Column(Text, nullable=True)
    triggered_by = Column(String(100), nullable=True)  # Agent name or system
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="transitions")


class AgentExecution(Base):
    """Agent execution record."""

    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)  # supervisor, policy, anomaly_investigation, action, compliance
    execution_order = Column(Integer, nullable=False)
    input_data = Column(JSON, nullable=True)
    output_data = Column(JSON, nullable=True)
    execution_duration_ms = Column(Integer, nullable=True)
    success = Column(Integer, default=1, nullable=False)  # 1 = success, 0 = failure
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="agent_executions")


class WorkflowEvidence(Base):
    """Evidence collected during workflow execution."""

    __tablename__ = "workflow_evidence"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    evidence_type = Column(String(100), nullable=False)  # data_sample, calculation, policy_reference, etc.
    source = Column(String(100), nullable=False)  # HRIS, PAYROLL, ATTENDANCE, POLICY, etc.
    data = Column(JSON, nullable=False)
    confidence_score = Column(Integer, nullable=True)  # 0-100
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="evidence")


class ClarificationRequest(Base):
    """Clarification request during workflow execution."""

    __tablename__ = "clarification_requests"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    requested_from_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    context = Column(JSON, nullable=True)
    required_by = Column(DateTime, nullable=False)
    response = Column(Text, nullable=True)
    responded_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="clarifications")
    requested_from = relationship("User")
