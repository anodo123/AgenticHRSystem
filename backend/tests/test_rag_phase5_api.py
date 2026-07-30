"""API tests for Phase 5 RAG endpoints."""
from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.security import get_current_user


def client_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_policy_ingest_get_and_search_api(db, users):
    client = client_for(db, users[0])
    try:
        payload = {
            "policy_id": "POL-LEAVE-1",
            "title": "Annual Leave Policy",
            "policy_type": "LEAVE",
            "country": "IN",
            "legal_entity": "ACME",
            "effective_from": (datetime.utcnow() - timedelta(days=1)).isoformat(),
            "content": "Annual leave requires manager approval and available leave balance.",
        }
        created = client.post("/api/v1/rag/policies", json=payload)
        assert created.status_code == 200, created.text
        assert created.json()["chunk_count"] == 1
        fetched = client.get("/api/v1/rag/policies/POL-LEAVE-1")
        assert fetched.status_code == 200
        searched = client.get(
            "/api/v1/rag/policies/search",
            params={"query": "annual leave manager approval", "country": "IN", "min_score": 0.01},
        )
        assert searched.status_code == 200, searched.text
        assert searched.json()["items"][0]["policy_id"] == "POL-LEAVE-1"
    finally:
        app.dependency_overrides.clear()


def test_incident_create_and_search_api(db, users):
    client = client_for(db, users[0])
    try:
        created = client.post("/api/v1/rag/incidents", json={
            "workflow_id": "WF-API",
            "incident_type": "PAYROLL_ANOMALY",
            "summary": "employee 98765 reported duplicate salary payroll",
            "root_cause": "duplicate payroll batch",
            "resolution": "batch reversed",
            "confidence": 0.95,
        })
        assert created.status_code == 200, created.text
        assert "98765" not in created.json()["sanitized_summary"]
        searched = client.get(
            "/api/v1/rag/incidents/search",
            params={"query": "duplicate payroll batch", "min_score": 0.01},
        )
        assert searched.status_code == 200
        assert searched.json()["total"] == 1
    finally:
        app.dependency_overrides.clear()
