"""Audit logging models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.base import Base


class AuditLog(Base):
    """Append-only audit log."""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # login, api_request, workflow_created, etc.
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(100), nullable=True)
    workflow_id = Column(Integer, ForeignKey("workflows.id"), nullable=True)
    entity_type = Column(String(100), nullable=True)  # workflow, approval, policy, etc.
    entity_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=True)  # create, update, delete, execute
    decision = Column(String(100), nullable=True)  # approve, reject, allow, deny
    previous_hash = Column(String(64), nullable=True)  # For hash chaining
    current_hash = Column(String(64), nullable=True)  # For hash chaining
    event_metadata = Column("metadata", JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    actor = relationship("User")
    workflow = relationship("Workflow")


class IdempotencyRecord(Base):
    """Idempotency key tracking."""

    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    request_method = Column(String(10), nullable=False)
    request_path = Column(String(255), nullable=False)
    request_body = Column(Text, nullable=True)
    response_status = Column(Integer, nullable=False)
    response_body = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
