"""End-to-end journeys through real authentication and API dependencies."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import create_app
from app.models.user import Role, User
from app.security import hash_password


def client_for(db):
    app = create_app()
    app.dependency_overrides[get_db] = lambda: db
    return app, TestClient(app)


def login(client, username):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": username, "password": "secure123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_authenticated_workflow_completes_and_is_evaluated(db):
    user = User(
        username="journey_user", email="journey@example.com",
        full_name="Journey User", hashed_password=hash_password("secure123"),
        is_superuser=True,
    )
    db.add(user)
    db.commit()
    app, client = client_for(db)
    try:
        headers = login(client, user.username)
        created = client.post("/api/v1/workflows/", headers=headers, json={
            "trigger_type": "EMPLOYEE_REQUEST",
            "request_summary": "Investigate a low-risk payroll discrepancy",
            "request_data": {
                "observed_value": 90, "expected_value": 100, "risk_level": "LOW",
                "policies": [{"policy_id": "PAY-1", "title": "Payroll corrections"}],
            },
        })
        assert created.status_code == 200, created.text
        workflow_id = created.json()["workflow_id"]
        run = client.post(f"/api/v1/workflows/{workflow_id}/run", headers=headers)
        assert run.status_code == 200, run.text
        assert run.json()["state"] == "COMPLETED"
        assert len(run.json()["agent_outputs"]) == 5

        detail = client.get(f"/api/v1/workflows/{workflow_id}", headers=headers)
        assert detail.json()["evidence_count"] >= 2
        assert detail.json()["transitions"][-1]["to_state"] == "COMPLETED"
        evaluation = client.post(f"/api/v1/evaluations/{workflow_id}", headers=headers)
        assert evaluation.status_code == 200, evaluation.text
        assert evaluation.json()["success"] is True
        assert evaluation.json()["agent_success_rate"] == 1
    finally:
        client.close()
        app.dependency_overrides.clear()


def test_approval_journey_enforces_role_and_completes(db):
    requester = User(
        username="approval_requester", email="requester.journey@example.com",
        full_name="Approval Requester", hashed_password=hash_password("secure123"),
    )
    approver = User(
        username="approval_admin", email="admin.journey@example.com",
        full_name="Approval Admin", hashed_password=hash_password("secure123"),
        roles=[Role(name="HR_ADMIN")],
    )
    db.add_all([requester, approver])
    db.commit()
    app, client = client_for(db)
    try:
        requester_headers = login(client, requester.username)
        approver_headers = login(client, approver.username)
        created = client.post("/api/v1/workflows/", headers=requester_headers, json={
            "trigger_type": "EMPLOYEE_REQUEST",
            "request_summary": "Review a high-risk payroll correction",
            "request_data": {
                "observed_value": 80, "expected_value": 100, "risk_level": "HIGH",
            },
        })
        assert created.status_code == 200
        workflow_id = created.json()["workflow_id"]
        run = client.post(
            f"/api/v1/workflows/{workflow_id}/run", headers=requester_headers,
        )
        assert run.status_code == 200, run.text
        assert run.json()["state"] == "WAITING_FOR_APPROVAL"
        approval_id = run.json()["approval"]["approval_id"]

        forbidden = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=requester_headers, json={"comments": "self approve"},
        )
        assert forbidden.status_code == 403
        approved = client.post(
            f"/api/v1/approvals/{approval_id}/approve",
            headers=approver_headers, json={"comments": "validated"},
        )
        assert approved.status_code == 200, approved.text
        assert approved.json()["status"] == "APPROVED"
        completed = client.post(
            f"/api/v1/workflows/{workflow_id}/run", headers=requester_headers,
        )
        assert completed.status_code == 200, completed.text
        assert completed.json()["state"] == "COMPLETED"
    finally:
        client.close()
        app.dependency_overrides.clear()
