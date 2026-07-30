"""Sanitized incident memory storage and similarity retrieval."""
import json
import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.rag.embedding_service import EmbeddingService
from app.repositories.policy_repository import PolicyRepository


class IncidentMemory:
    @staticmethod
    def sanitize(text: str) -> str:
        text = re.sub(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b", "[REDACTED_EMAIL]", text)
        text = re.sub(r"\b(?:employee|emp)[\s:#-]*\d+\b", "[REDACTED_EMPLOYEE]", text, flags=re.I)
        return re.sub(r"\b\d{8,}\b", "[REDACTED_ID]", text)

    @classmethod
    def remember(
        cls,
        db: Session,
        *,
        workflow_id: str,
        incident_type: str,
        summary: str,
        symptoms: list | dict | None = None,
        root_cause: str | None = None,
        resolution: str | None = None,
        affected_systems: list[str] | None = None,
        country: str | None = None,
        business_unit: str | None = None,
        outcome: str | None = None,
        confidence: float | None = None,
    ):
        sanitized = cls.sanitize(summary)
        searchable = " ".join(filter(None, [sanitized, root_cause, resolution]))
        vector = EmbeddingService.embed_cached(db, searchable)
        return PolicyRepository.create_incident(
            db,
            incident_id=f"INC-{uuid.uuid4().hex[:12].upper()}",
            workflow_id=workflow_id,
            incident_type=incident_type,
            sanitized_summary=sanitized,
            symptoms=symptoms,
            root_cause=cls.sanitize(root_cause) if root_cause else None,
            resolution=cls.sanitize(resolution) if resolution else None,
            affected_systems=affected_systems,
            country=country,
            business_unit=business_unit,
            outcome=outcome,
            confidence=confidence,
            embedding=json.dumps(vector),
        )

    @staticmethod
    def search(
        db: Session,
        query: str,
        *,
        top_k: int | None = None,
        min_score: float | None = None,
        **filters,
    ) -> list[dict]:
        settings = get_settings()
        top_k = top_k or settings.incident_top_k
        min_score = settings.incident_min_score if min_score is None else min_score
        query_vector = EmbeddingService.embed_cached(db, query)
        matches = []
        for incident in PolicyRepository.incidents(db, **filters):
            score = EmbeddingService.cosine_similarity(
                query_vector, json.loads(incident.embedding or "[]")
            )
            if score >= min_score:
                matches.append({
                    "incident_id": incident.incident_id,
                    "workflow_id": incident.workflow_id,
                    "incident_type": incident.incident_type,
                    "sanitized_summary": incident.sanitized_summary,
                    "root_cause": incident.root_cause,
                    "resolution": incident.resolution,
                    "outcome": incident.outcome,
                    "score": round(score, 6),
                })
        matches.sort(key=lambda item: (-item["score"], item["incident_id"]))
        return matches[:top_k]
