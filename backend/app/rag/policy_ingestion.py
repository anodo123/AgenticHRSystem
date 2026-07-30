"""Policy document extraction, chunking, and persistence."""
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import re
import uuid

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.rag.embedding_service import EmbeddingService
from app.repositories.policy_repository import PolicyRepository


class PolicyIngestion:
    @staticmethod
    def extract(content: bytes, source_format: str) -> str:
        source_format = source_format.lower().lstrip(".")
        if source_format in {"txt", "text", "md", "markdown"}:
            return content.decode("utf-8")
        if source_format == "pdf":
            from PyPDF2 import PdfReader
            return "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(content)).pages)
        if source_format == "docx":
            from docx import Document
            return "\n".join(paragraph.text for paragraph in Document(BytesIO(content)).paragraphs)
        raise ValueError(f"Unsupported policy format: {source_format}")

    @staticmethod
    def chunk(text: str, size: int | None = None, overlap: int | None = None) -> list[dict]:
        settings = get_settings()
        size = size or settings.policy_chunk_size
        overlap = settings.policy_chunk_overlap if overlap is None else overlap
        if size < 1 or overlap < 0 or overlap >= size:
            raise ValueError("Chunk size must be positive and overlap smaller than size")
        words = text.split()
        chunks = []
        start = 0
        while start < len(words):
            end = min(start + size, len(words))
            content = " ".join(words[start:end])
            heading = None
            match = re.match(r"^#{1,6}\s+(.+)", content)
            if match:
                heading = match.group(1).split(" #", 1)[0]
            chunks.append({
                "content": content,
                "section_title": heading,
                "token_count": len(words[start:end]),
            })
            if end == len(words):
                break
            start = end - overlap
        return chunks

    @classmethod
    def ingest(
        cls,
        db: Session,
        *,
        policy_id: str,
        title: str,
        policy_type: str,
        country: str,
        legal_entity: str,
        content: str,
        effective_from: datetime,
        effective_to: datetime | None = None,
        description: str | None = None,
        business_unit: str | None = None,
        employee_type: str | None = "ALL",
        version: str = "1.0",
        confidentiality: str = "PUBLIC",
        source_file: str | None = None,
        source_format: str = "txt",
        status: str = "ACTIVE",
    ):
        if not content.strip():
            raise ValueError("Policy content cannot be empty")
        if PolicyRepository.get(db, policy_id):
            raise ValueError(f"Policy already exists: {policy_id}")
        checksum = sha256(content.encode()).hexdigest()
        policy = PolicyRepository.create_policy(
            db,
            policy_id=policy_id,
            title=title,
            description=description,
            policy_type=policy_type.upper(),
            country=country.upper(),
            legal_entity=legal_entity,
            business_unit=business_unit,
            employee_type=employee_type,
            version=version,
            effective_from=effective_from,
            effective_to=effective_to,
            confidentiality=confidentiality,
            source_file=source_file,
            source_format=source_format,
            checksum=checksum,
            status=status,
        )
        chunks = []
        for index, item in enumerate(cls.chunk(content)):
            vector = EmbeddingService.embed_cached(db, item["content"])
            chunks.append({
                "chunk_id": f"CHK-{uuid.uuid4().hex[:16].upper()}",
                "section_title": item["section_title"],
                "content": item["content"],
                "sequence_number": index,
                "embedding": json.dumps(vector),
                "token_count": item["token_count"],
                "chunk_metadata": {"policy_version": version},
                "checksum": sha256(item["content"].encode()).hexdigest(),
            })
        PolicyRepository.replace_chunks(db, policy, chunks)
        return PolicyRepository.get(db, policy_id)
