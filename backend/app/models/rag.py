"""Policy and RAG-related models."""
from datetime import datetime
import json

from sqlalchemy import Column, Integer, String, DateTime, Text, JSON, Float, ForeignKey
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import relationship
from app.db.base import Base


class PortableVector(TypeDecorator):
    """Use pgvector on PostgreSQL and JSON text on lightweight databases."""

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(128))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        parsed = json.loads(value) if isinstance(value, str) else value
        return parsed if dialect.name == "postgresql" else json.dumps(parsed)

    def process_result_value(self, value, dialect):
        if value is None or isinstance(value, str):
            return value
        return json.dumps(list(value))


class Policy(Base):
    """Policy document model."""

    __tablename__ = "policies"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    policy_type = Column(String(100), nullable=False)  # leave, overtime, payroll, attendance, etc.
    country = Column(String(50), nullable=False, index=True)
    legal_entity = Column(String(100), nullable=False, index=True)
    business_unit = Column(String(100), nullable=True, index=True)
    employee_type = Column(String(50), nullable=True)  # ALL, FULL_TIME, PART_TIME, etc.
    version = Column(String(20), nullable=False, default="1.0")
    effective_from = Column(DateTime, nullable=False, index=True)
    effective_to = Column(DateTime, nullable=True, index=True)
    confidentiality = Column(String(50), default="PUBLIC")  # PUBLIC, CONFIDENTIAL, RESTRICTED
    source_file = Column(String(255), nullable=True)
    source_format = Column(String(20), nullable=True)  # pdf, docx, txt, markdown
    checksum = Column(String(64), nullable=True)
    status = Column(String(50), default="ACTIVE")  # ACTIVE, ARCHIVED, DRAFT
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    chunks = relationship("PolicyChunk", back_populates="policy", cascade="all, delete-orphan")


class PolicyChunk(Base):
    """Policy chunk for RAG retrieval."""

    __tablename__ = "policy_chunks"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("policies.id"), nullable=False, index=True)
    chunk_id = Column(String(100), unique=True, nullable=False, index=True)
    section_title = Column(String(255), nullable=True)
    content = Column(Text, nullable=False)
    sequence_number = Column(Integer, nullable=False)
    embedding = Column(PortableVector(), nullable=True)
    token_count = Column(Integer, nullable=True)
    chunk_metadata = Column("metadata", JSON, nullable=True)
    checksum = Column(String(64), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    policy = relationship("Policy", back_populates="chunks")


class Incident(Base):
    """Incident memory for advisory context."""

    __tablename__ = "incidents"

    id = Column(Integer, primary_key=True, index=True)
    incident_id = Column(String(100), unique=True, nullable=False, index=True)
    workflow_id = Column(String(100), nullable=False)  # Reference to original workflow
    incident_type = Column(String(100), nullable=False)  # PAYROLL_ANOMALY, ATTENDANCE_ANOMALY, etc.
    sanitized_summary = Column(Text, nullable=False)  # No PII
    symptoms = Column(JSON, nullable=True)
    root_cause = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)
    affected_systems = Column(JSON, nullable=True)  # ["HRIS", "PAYROLL"]
    country = Column(String(50), nullable=True)
    business_unit = Column(String(100), nullable=True)
    outcome = Column(String(100), nullable=True)  # RESOLVED, ESCALATED, MANUAL_INTERVENTION
    confidence = Column(Float, nullable=True)  # 0-1 score
    embedding = Column(PortableVector(), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class EmbeddingCache(Base):
    """Cache for embeddings to avoid recomputation."""

    __tablename__ = "embedding_cache"

    id = Column(Integer, primary_key=True, index=True)
    content_hash = Column(String(64), unique=True, nullable=False, index=True)
    content = Column(Text, nullable=False)
    embedding = Column(Text, nullable=False)  # JSON array
    embedding_model = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
