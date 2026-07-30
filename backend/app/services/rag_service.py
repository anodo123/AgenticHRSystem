"""Unified application service for policy RAG and incident memory."""
from typing import Any

from sqlalchemy.orm import Session

from app.audit import log_event
from app.rag.incident_memory import IncidentMemory
from app.rag.policy_ingestion import PolicyIngestion
from app.rag.semantic_search import SemanticSearch
from app.repositories.policy_repository import PolicyRepository


class RAGService:
    @staticmethod
    def ingest_policy(db: Session, actor_id: int | None = None, **values) -> dict[str, Any]:
        policy = PolicyIngestion.ingest(db, **values)
        log_event(
            db, event_type="policy_ingested", actor_id=actor_id,
            entity_type="policy", entity_id=policy.id, action="ingest",
            metadata={"policy_id": policy.policy_id, "chunks": len(policy.chunks)},
        )
        return RAGService.policy_details(policy)

    @staticmethod
    def get_policy(db: Session, policy_id: str) -> dict[str, Any] | None:
        policy = PolicyRepository.get(db, policy_id)
        return RAGService.policy_details(policy) if policy else None

    @staticmethod
    def search_policies(db: Session, query: str, **filters) -> list[dict]:
        return SemanticSearch.search(db, query, **filters)

    @staticmethod
    def remember_incident(db: Session, **values) -> dict[str, Any]:
        incident = IncidentMemory.remember(db, **values)
        log_event(
            db, event_type="incident_remembered",
            entity_type="incident", entity_id=incident.id, action="create",
            metadata={"incident_id": incident.incident_id, "workflow_id": incident.workflow_id},
        )
        return {
            "incident_id": incident.incident_id,
            "workflow_id": incident.workflow_id,
            "incident_type": incident.incident_type,
            "sanitized_summary": incident.sanitized_summary,
            "outcome": incident.outcome,
            "confidence": incident.confidence,
            "created_at": incident.created_at,
        }

    @staticmethod
    def search_incidents(db: Session, query: str, **filters) -> list[dict]:
        return IncidentMemory.search(db, query, **filters)

    @staticmethod
    def policy_details(policy) -> dict[str, Any]:
        return {
            "policy_id": policy.policy_id,
            "title": policy.title,
            "description": policy.description,
            "policy_type": policy.policy_type,
            "country": policy.country,
            "legal_entity": policy.legal_entity,
            "business_unit": policy.business_unit,
            "employee_type": policy.employee_type,
            "version": policy.version,
            "effective_from": policy.effective_from,
            "effective_to": policy.effective_to,
            "confidentiality": policy.confidentiality,
            "status": policy.status,
            "checksum": policy.checksum,
            "chunk_count": len(policy.chunks),
            "created_at": policy.created_at,
        }
