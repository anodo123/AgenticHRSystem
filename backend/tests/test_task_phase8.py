"""Phase 8 task scheduling, priority, execution, and retry tests."""
from datetime import datetime, timedelta

from app.models.audit import AuditLog
from app.models.task import TaskPriority
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService


def create_task(db, owner, **overrides):
    values = {
        "name": "Policy scan",
        "description": "Run scheduled policy scan",
        "trigger_type": "MANUAL",
        "priority": TaskPriority.MEDIUM,
        "is_enabled": True,
        "schedule_cron": None,
        "target_scope": "NONE",
        "target_scope_value": None,
        "workflow_type": "POLICY_QUERY",
        "task_payload": {"compliance_decision": "ALLOW"},
        "retry_config": {"max_retries": 2, "base_seconds": 2},
        "timeout_seconds": 60,
    }
    values.update(overrides)
    return TaskService.create_task(
        db, owner_id=owner.id, owner_name=owner.full_name, **values
    )


def test_cron_validation_and_next_run(db, users):
    task = create_task(
        db,
        users[1],
        trigger_type="SCHEDULE",
        schedule_cron="*/15 * * * *",
    )
    assert task.next_run_at is not None
    assert task.next_run_at > datetime.utcnow()
    try:
        create_task(
            db, users[1], trigger_type="SCHEDULE", schedule_cron="bad cron",
        )
        raise AssertionError("invalid cron must fail")
    except ValueError:
        pass


def test_due_tasks_are_priority_ordered(db, users):
    low = create_task(
        db, users[1], name="Low", trigger_type="SCHEDULE",
        schedule_cron="* * * * *", priority=TaskPriority.LOW,
    )
    critical = create_task(
        db, users[1], name="Critical", trigger_type="SCHEDULE",
        schedule_cron="* * * * *", priority=TaskPriority.CRITICAL,
    )
    low.next_run_at = datetime.utcnow() - timedelta(seconds=1)
    critical.next_run_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert [task.task_id for task in TaskRepository.due(db)] == [
        critical.task_id, low.task_id,
    ]


def test_manual_task_creates_and_completes_workflow(db, users):
    task = create_task(db, users[1])
    success, error, result = TaskService.execute(
        db, task.task_id, triggered_by="MANUAL",
        triggered_by_user_id=users[1].id,
    )
    assert success, error
    assert result["status"] == "SUCCESS"
    assert result["results"]["workflows"][0]["state"] == "COMPLETED"
    assert result["results"]["workflows"][0]["success"]
    assert db.query(AuditLog).filter(AuditLog.event_type == "task_run_updated").count() == 1


def test_failed_task_uses_exponential_backoff_then_exhausts(db, users):
    task = create_task(
        db,
        users[1],
        task_payload={"compliance_decision": "INVALID"},
        retry_config={"max_retries": 1, "base_seconds": 2, "backoff": "exponential"},
    )
    success, error, result = TaskService.execute(
        db, task.task_id, triggered_by="MANUAL",
    )
    assert not success
    assert result["status"] == "RETRY_SCHEDULED"
    assert result["retry_count"] == 1
    assert 0 < (result["next_retry_at"] - datetime.utcnow()).total_seconds() <= 2
    run = task.runs[0]
    run.next_retry_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    success, error, result = TaskService.retry(db, run)
    assert not success
    assert result["status"] == "FAILED"
    assert result["completed_at"] is not None


def test_disabled_task_cannot_execute(db, users):
    task = create_task(db, users[1], is_enabled=False)
    success, error, result = TaskService.execute(
        db, task.task_id, triggered_by="MANUAL",
    )
    assert not success and "disabled" in error
    assert result is None
