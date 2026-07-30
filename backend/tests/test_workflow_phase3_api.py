"""Phase 3 API integration tests."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.workflow import WorkflowState
from app.repositories.workflow_repository import WorkflowRepository
from app.security import get_current_user


def client_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_pause_resume_cancel_endpoints(db, users):
    client = client_for(db, users[0])
    try:
        created = client.post("/api/v1/workflows/", json={
            "trigger_type": "EMPLOYEE_REQUEST",
            "request_summary": "API workflow",
        })
        assert created.status_code == 200
        workflow_id = created.json()["workflow_id"]

        paused = client.post(
            f"/api/v1/workflows/{workflow_id}/pause",
            json={"reason": "manual review"},
        )
        assert paused.status_code == 200
        assert paused.json()["paused_reason"] == "manual review"
        resumed = client.post(f"/api/v1/workflows/{workflow_id}/resume")
        assert resumed.status_code == 200 and resumed.json()["paused_at"] is None
        cancelled = client.post(
            f"/api/v1/workflows/{workflow_id}/cancel", json={"reason": "withdrawn"},
        )
        assert cancelled.status_code == 200
        assert cancelled.json()["state"] == "CANCELLED"
    finally:
        app.dependency_overrides.clear()


def test_approval_endpoints_are_connected(db, users):
    requester, approver, _ = users
    client = client_for(db, requester)
    try:
        workflow_id = client.post("/api/v1/workflows/", json={
            "trigger_type": "HR_OPERATIONS_REQUEST",
            "request_summary": "Payroll correction",
        }).json()["workflow_id"]
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        workflow.current_state = WorkflowState.COMPLIANCE_REVIEW
        db.commit()

        created = client.post("/api/v1/approvals/", json={
            "workflow_id": workflow_id,
            "proposed_action": "Correct payroll",
            "risk_level": "HIGH",
            "financial_impact": "MEDIUM",
            "required_approver_roles": ["HR_ADMIN"],
        })
        assert created.status_code == 200, created.text
        approval_id = created.json()["approval_id"]

        app.dependency_overrides[get_current_user] = lambda: approver
        approved = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            json={"comments": "Looks correct"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        assert WorkflowRepository.get_workflow(db, workflow_id).current_state == WorkflowState.APPROVED
    finally:
        app.dependency_overrides.clear()


def test_run_endpoint_executes_agents(db, users):
    client = client_for(db, users[0])
    try:
        workflow_id = client.post("/api/v1/workflows/", json={
            "trigger_type": "EMPLOYEE_REQUEST",
            "request_summary": "Payroll discrepancy",
            "request_data": {
                "observed_value": 90, "expected_value": 100, "risk_level": "LOW",
            },
        }).json()["workflow_id"]
        response = client.post(f"/api/v1/workflows/{workflow_id}/run")
        assert response.status_code == 200, response.text
        assert response.json()["state"] == "COMPLETED"
        assert len(response.json()["agent_outputs"]) == 5
    finally:
        app.dependency_overrides.clear()
