"""Persisted workflow evaluation results."""
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import relationship

from app.db.base import Base


class WorkflowEvaluation(Base):
    __tablename__ = "workflow_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(String(100), unique=True, nullable=False, index=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), unique=True, nullable=False, index=True)
    success = Column(Boolean, nullable=False)
    final_state = Column(String(50), nullable=False, index=True)
    duration_ms = Column(Integer, nullable=True)
    agent_success_rate = Column(Float, nullable=False)
    compliance_decision = Column(String(50), nullable=True, index=True)
    approval_required = Column(Boolean, default=False, nullable=False)
    evidence_count = Column(Integer, default=0, nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    scores = Column(JSON, nullable=False)
    evaluated_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    workflow = relationship("Workflow")
