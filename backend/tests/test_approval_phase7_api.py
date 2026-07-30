"""Phase 7 approval API tests."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.models.user import Role, User
from app.security import get_current_user
from app.services.approval_service import ApprovalService
from tests.test_approval_phase7 import ready


def client_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_approval_inbox_detail_delegation_and_decision_routes(db, users):
    requester, hr_admin, outsider = users
    manager_role = Role(name="MANAGER")
    manager = User(
        username="api_manager", email="api_manager@example.com",
        full_name="API Manager", hashed_password="unused", roles=[manager_role],
    )
    delegate = User(
        username="api_delegate", email="api_delegate@example.com",
        full_name="API Delegate", hashed_password="unused",
    )
    db.add_all([manager, delegate])
    db.commit()
    approval = ApprovalService.create_request(
        db,
        workflow_id=ready(db, requester.id),
        proposed_action="API approval",
        risk_level="HIGH",
        financial_impact="MEDIUM",
        required_approver_roles=["MANAGER", "HR_ADMIN"],
    )[2]
    client = client_for(db, manager)
    try:
        inbox = client.get("/api/v1/approvals/")
        assert inbox.status_code == 200
        assert inbox.json()["total"] == 1
        detail = client.get(f"/api/v1/approvals/{approval['approval_id']}")
        assert detail.status_code == 200
        delegated = client.post(
            f"/api/v1/approvals/{approval['approval_id']}/delegate",
            json={"delegated_to_id": delegate.id, "reason": "coverage"},
        )
        assert delegated.status_code == 200, delegated.text

        app.dependency_overrides[get_current_user] = lambda: delegate
        first = client.post(
            f"/api/v1/approvals/{approval['approval_id']}/approve",
            json={"comments": "delegated approval"},
        )
        assert first.status_code == 200, first.text
        assert first.json()["current_required_role"] == "HR_ADMIN"

        app.dependency_overrides[get_current_user] = lambda: outsider
        forbidden = client.get(f"/api/v1/approvals/{approval['approval_id']}")
        assert forbidden.status_code == 403

        app.dependency_overrides[get_current_user] = lambda: hr_admin
        final = client.post(
            f"/api/v1/approvals/{approval['approval_id']}/approve",
            json={"comments": "final approval"},
        )
        assert final.status_code == 200, final.text
        assert final.json()["status"] == "APPROVED"
        assert len(final.json()["decisions"]) == 2
    finally:
        app.dependency_overrides.clear()
