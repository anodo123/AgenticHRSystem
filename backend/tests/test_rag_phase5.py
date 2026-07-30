"""Unit and integration tests for policy RAG and incident memory."""
from datetime import datetime, timedelta

from app.models.rag import EmbeddingCache
from app.rag.embedding_service import EmbeddingService
from app.rag.policy_ingestion import PolicyIngestion
from app.services.rag_service import RAGService


def ingest(db, policy_id="POL-OT-1", country="IN", content=None):
    return RAGService.ingest_policy(
        db,
        policy_id=policy_id,
        title="Overtime Approval Policy",
        policy_type="OVERTIME",
        country=country,
        legal_entity="ACME",
        content=content or (
            "Overtime work requires manager approval before payroll processing. "
            "Approved overtime is paid in the next salary cycle."
        ),
        effective_from=datetime.utcnow() - timedelta(days=1),
    )


def test_embedding_is_deterministic_normalized_and_cached(db):
    first = EmbeddingService.embed_cached(db, "manager overtime approval")
    second = EmbeddingService.embed_cached(db, "manager overtime approval")
    assert first == second
    assert len(first) == 128
    assert db.query(EmbeddingCache).count() == 1
    assert EmbeddingService.cosine_similarity(first, second) == 1.0


def test_ingestion_chunks_and_metadata_filtered_search(db):
    policy = ingest(db)
    assert policy["chunk_count"] == 1
    results = RAGService.search_policies(
        db, "overtime manager approval", country="IN",
        legal_entity="ACME", min_score=0.01,
    )
    assert results
    assert results[0]["policy_id"] == "POL-OT-1"
    assert results[0]["excerpt"]
    assert not RAGService.search_policies(
        db, "overtime manager approval", country="US", min_score=0,
    )


def test_inactive_and_future_policies_are_not_searchable(db):
    RAGService.ingest_policy(
        db,
        policy_id="POL-FUTURE",
        title="Future Leave Policy",
        policy_type="LEAVE",
        country="IN",
        legal_entity="ACME",
        content="Future leave eligibility and approval.",
        effective_from=datetime.utcnow() + timedelta(days=10),
    )
    assert not RAGService.search_policies(
        db, "future leave eligibility", country="IN", min_score=0,
    )


def test_incident_memory_sanitizes_and_retrieves(db):
    remembered = RAGService.remember_incident(
        db,
        workflow_id="WF-1",
        incident_type="PAYROLL_ANOMALY",
        summary="employee 12345 emailed jane@example.com about duplicate payroll",
        root_cause="Duplicate payroll import",
        resolution="Removed duplicate entry",
        outcome="RESOLVED",
        confidence=0.9,
    )
    assert "jane@example.com" not in remembered["sanitized_summary"]
    assert "12345" not in remembered["sanitized_summary"]
    matches = RAGService.search_incidents(
        db, "duplicate payroll import", incident_type="PAYROLL_ANOMALY",
        min_score=0.01,
    )
    assert matches and matches[0]["incident_id"] == remembered["incident_id"]


def test_text_extraction_chunk_validation_and_duplicate_policy(db):
    assert PolicyIngestion.extract(b"# Leave\\nAnnual leave rules", "md").startswith("# Leave")
    chunks = PolicyIngestion.chunk("one two three four five", size=3, overlap=1)
    assert [item["content"] for item in chunks] == ["one two three", "three four five"]
    ingest(db)
    try:
        ingest(db)
        raise AssertionError("duplicate policy should fail")
    except ValueError as exc:
        assert "already exists" in str(exc)
