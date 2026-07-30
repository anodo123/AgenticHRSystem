"""Approval and compliance models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum
from app.db.base import Base


class ApprovalStatus(str, PyEnum):
    """Approval statuses."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class ComplianceDecision(str, PyEnum):
    """Compliance decisions."""

    ALLOW = "ALLOW"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class ApprovalRequest(Base):
    """Approval request model."""

    __tablename__ = "approval_requests"

    id = Column(Integer, primary_key=True, index=True)
    approval_id = Column(String(100), unique=True, nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    proposed_action = Column(Text, nullable=False)
    affected_employee_id = Column(Integer, ForeignKey("employees.id"), nullable=True)
    risk_level = Column(String(50), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    financial_impact = Column(String(50), nullable=False)  # NONE, LOW, MEDIUM, HIGH
    policy_references = Column(JSON, nullable=True)
    evidence_summary = Column(Text, nullable=True)
    required_approver_roles = Column(JSON, nullable=False)  # ["PAYROLL_SPECIALIST", "HR_ADMIN"]
    status = Column(SQLEnum(ApprovalStatus), default=ApprovalStatus.PENDING, nullable=False, index=True)
    submitted_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    resolved_at = Column(DateTime, nullable=True)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    decision = Column(String(50), nullable=True)  # APPROVED, REJECTED
    decision_comments = Column(Text, nullable=True)
    current_level = Column(Integer, default=0, nullable=False)
    total_levels = Column(Integer, default=1, nullable=False)
    delegated_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delegated_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    delegation_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow", back_populates="approvals")
    affected_employee = relationship("Employee")
    approver = relationship("User", foreign_keys=[approver_id])
    delegated_to = relationship("User", foreign_keys=[delegated_to_id])
    delegated_by = relationship("User", foreign_keys=[delegated_by_id])
    decisions = relationship(
        "ApprovalDecisionEntry", back_populates="approval",
        cascade="all, delete-orphan", order_by="ApprovalDecisionEntry.created_at",
    )


class ApprovalDecisionEntry(Base):
    """Immutable decision history for each approval level."""

    __tablename__ = "approval_decision_entries"

    id = Column(Integer, primary_key=True, index=True)
    approval_request_id = Column(
        Integer, ForeignKey("approval_requests.id"), nullable=False, index=True
    )
    level = Column(Integer, nullable=False)
    required_role = Column(String(100), nullable=False)
    approver_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    decision = Column(String(50), nullable=False)
    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    approval = relationship("ApprovalRequest", back_populates="decisions")
    approver = relationship("User")


class ComplianceDecisionRecord(Base):
    """Compliance decision record."""

    __tablename__ = "compliance_decisions"

    id = Column(Integer, primary_key=True, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=False, index=True)
    decision = Column(SQLEnum(ComplianceDecision), nullable=False)
    reason_code = Column(String(100), nullable=False)
    explanation = Column(Text, nullable=False)
    policy_violations = Column(JSON, nullable=True)
    authorization_issues = Column(JSON, nullable=True)
    required_approver_roles = Column(JSON, nullable=True)
    approval_expiry_hours = Column(Integer, nullable=True)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    workflow = relationship("Workflow")
