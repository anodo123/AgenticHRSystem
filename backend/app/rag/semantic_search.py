"""Metadata-filtered semantic policy retrieval."""
import json

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.rag.embedding_service import EmbeddingService
from app.repositories.policy_repository import PolicyRepository


class SemanticSearch:
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
        top_k = top_k or settings.policy_top_k
        min_score = settings.policy_min_score if min_score is None else min_score
        query_vector = EmbeddingService.embed_cached(db, query)
        matches = []
        for chunk in PolicyRepository.searchable_chunks(db, **filters):
            vector = json.loads(chunk.embedding) if chunk.embedding else []
            score = EmbeddingService.cosine_similarity(query_vector, vector)
            if score >= min_score:
                matches.append({
                    "policy_id": chunk.policy.policy_id,
                    "title": chunk.policy.title,
                    "policy_type": chunk.policy.policy_type,
                    "version": chunk.policy.version,
                    "chunk_id": chunk.chunk_id,
                    "section": chunk.section_title,
                    "excerpt": chunk.content,
                    "score": round(score, 6),
                    "country": chunk.policy.country,
                    "legal_entity": chunk.policy.legal_entity,
                    "effective_from": chunk.policy.effective_from,
                })
        matches.sort(key=lambda item: (-item["score"], item["policy_id"], item["chunk_id"]))
        return matches[:top_k]
