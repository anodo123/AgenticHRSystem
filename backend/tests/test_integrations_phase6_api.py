"""Phase 6 integration API tests."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.security import get_current_user
from tests.test_adapters_phase6 import employee_records


def client_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_health_read_and_dry_run_routes(db, users):
    employee, payroll, _, _ = employee_records(db)
    client = client_for(db, users[0])
    try:
        health = client.get("/api/v1/integrations/health")
        assert health.status_code == 200
        assert health.json()["PAYROLL"]["status"] == "healthy"
        read = client.get(f"/api/v1/integrations/PAYROLL/employees/{employee.id}")
        assert read.status_code == 200, read.text
        assert read.json()["data"]["latest"]["net_salary"] == 9000
        preview = client.post(
            f"/api/v1/integrations/PAYROLL/employees/{employee.id}/dry-run",
            json={"record_id": payroll.id, "updates": {"net_salary": 9500}},
        )
        assert preview.status_code == 200, preview.text
        assert preview.json()["dry_run"]
    finally:
        app.dependency_overrides.clear()
