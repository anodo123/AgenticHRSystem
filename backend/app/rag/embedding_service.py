"""Deterministic local embeddings with database caching."""
import hashlib
import json
import math
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.rag import EmbeddingCache


class EmbeddingService:
    """Generate stable hashed-token embeddings without external network calls."""

    dimension = 128

    @classmethod
    def embed(cls, text: str) -> list[float]:
        vector = [0.0] * cls.dimension
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode()).digest()
            index = int.from_bytes(digest[:4], "big") % cls.dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector))
        return [value / norm for value in vector] if norm else vector

    @classmethod
    def embed_cached(cls, db: Session, text: str) -> list[float]:
        content_hash = hashlib.sha256(text.encode()).hexdigest()
        cached = db.query(EmbeddingCache).filter(
            EmbeddingCache.content_hash == content_hash
        ).first()
        if cached:
            return json.loads(cached.embedding)
        vector = cls.embed(text)
        db.add(EmbeddingCache(
            content_hash=content_hash,
            content=text,
            embedding=json.dumps(vector),
            embedding_model=f"{get_settings().embedding_provider}:hashed-token-v1",
        ))
        db.commit()
        return vector

    @staticmethod
    def cosine_similarity(left: list[float], right: list[float]) -> float:
        if not left or len(left) != len(right):
            return 0.0
        return max(0.0, min(1.0, sum(a * b for a, b in zip(left, right))))
