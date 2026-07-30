"""Phase 9 API tests."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app
from app.models.workflow import TriggerType, WorkflowState
from app.repositories.workflow_repository import WorkflowRepository
from app.security import get_current_user


def test_metrics_evaluation_and_correlation_api(db, users):
    users[1].is_superuser = True
    db.commit()
    workflow = WorkflowRepository.create_workflow(
        db, "WF-API-EVALUATE", TriggerType.EMPLOYEE_REQUEST, users[0].id, None,
        "API evaluation",
    )
    workflow.current_state = WorkflowState.COMPLETED
    workflow.completed_at = workflow.updated_at
    db.commit()

    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: users[1]
    with TestClient(app) as client:
        response = client.post(
            f"/api/v1/evaluations/{workflow.workflow_id}",
            headers={"X-Correlation-ID": "phase9-test"},
        )
        assert response.status_code == 200
        assert response.headers["X-Correlation-ID"] == "phase9-test"
        assert response.json()["success"] is True

        listing = client.get("/api/v1/evaluations")
        assert listing.status_code == 200
        assert listing.json()["total"] == 1

        metrics = client.get("/api/v1/metrics")
        assert metrics.status_code == 200
        assert metrics.json()["workflows"]["total"] == 1

        prometheus = client.get("/metrics")
        assert prometheus.status_code == 200
        assert "darwinboxai_http_requests_total" in prometheus.text
        assert prometheus.headers.get("X-Correlation-ID")
