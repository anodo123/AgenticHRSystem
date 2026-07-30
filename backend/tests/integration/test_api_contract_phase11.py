"""Cross-cutting API contract and security integration tests."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app


def test_openapi_exposes_all_operational_domains():
    paths = create_app().openapi()["paths"]
    required = {
        "/api/v1/auth/login", "/api/v1/workflows/", "/api/v1/approvals/",
        "/api/v1/rag/policies/search", "/api/v1/integrations/health",
        "/api/v1/tasks/", "/api/v1/metrics", "/api/v1/evaluations",
    }
    assert required.issubset(paths)


def test_protected_domains_reject_anonymous_requests(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    with TestClient(app) as client:
        for path in (
            "/api/v1/workflows/", "/api/v1/approvals/",
            "/api/v1/employees/", "/api/v1/tasks/",
        ):
            response = client.get(path)
            assert response.status_code in {401, 403}, (path, response.text)
            assert response.headers.get("X-Correlation-ID")
    app.dependency_overrides.clear()
