"""Phase 8 task API and scheduler lifecycle tests."""
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app
from app.security import get_current_user
from app.workers.task_scheduler import TaskScheduler


def client_for(db, user):
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    return TestClient(app)


def test_task_create_list_run_history_and_disable_api(db, users):
    client = client_for(db, users[1])
    try:
        created = client.post("/api/v1/tasks/", json={
            "name": "Manual HR scan",
            "trigger_type": "MANUAL",
            "priority": "HIGH",
            "target_scope": "NONE",
            "workflow_type": "GENERAL_HR_REQUEST",
            "task_payload": {"compliance_decision": "ALLOW"},
            "retry_config": {"max_retries": 1, "base_seconds": 1},
        })
        assert created.status_code == 200, created.text
        task_id = created.json()["task_id"]
        listed = client.get("/api/v1/tasks/")
        assert listed.status_code == 200 and listed.json()["total"] == 1
        run = client.post(f"/api/v1/tasks/{task_id}/run")
        assert run.status_code == 200, run.text
        assert run.json()["status"] == "SUCCESS"
        history = client.get(f"/api/v1/tasks/{task_id}/runs")
        assert history.status_code == 200
        assert history.json()["items"][0]["run_id"] == run.json()["run_id"]
        disabled = client.patch(
            f"/api/v1/tasks/{task_id}/enabled", json={"is_enabled": False},
        )
        assert disabled.status_code == 200
        assert not disabled.json()["is_enabled"]
    finally:
        app.dependency_overrides.clear()


def test_non_manager_cannot_manage_tasks(db, users):
    client = client_for(db, users[0])
    try:
        assert client.get("/api/v1/tasks/").status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_scheduler_lifecycle():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
        assert TaskScheduler.scheduler is not None
        assert TaskScheduler.scheduler.running
    assert TaskScheduler.scheduler is None
