"""Scheduled task configuration and durable execution."""
from datetime import datetime, timedelta
from time import perf_counter
from typing import Any
import uuid

from sqlalchemy.orm import Session

from app.audit import log_event
from app.models.employee import Employee
from app.models.task import ScheduledTask, TaskRun
from app.observability.metrics import MetricsCollector
from app.models.workflow import IntentCategory, TriggerType, WorkflowState
from app.repositories.task_repository import TaskRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.services.agent_orchestration import AgentOrchestrationService
from app.services.workflow_service import WorkflowService
from app.workers.scheduler_compat import CronTrigger


class TaskService:
    @staticmethod
    def validate_cron(expression: str | None, trigger_type: str) -> None:
        if trigger_type == "SCHEDULE":
            if not expression:
                raise ValueError("Scheduled tasks require a cron expression")
            CronTrigger.from_crontab(expression)
        elif expression:
            raise ValueError("Cron expression is only valid for SCHEDULE tasks")

    @staticmethod
    def next_fire(expression: str | None, now: datetime | None = None) -> datetime | None:
        if not expression:
            return None
        now = now or datetime.utcnow()
        value = CronTrigger.from_crontab(expression).get_next_fire_time(None, now)
        return value.replace(tzinfo=None) if value else None

    @classmethod
    def create_task(
        cls, db: Session, *, owner_id: int, owner_name: str, **values
    ) -> ScheduledTask:
        trigger_type = values["trigger_type"].upper()
        cls.validate_cron(values.get("schedule_cron"), trigger_type)
        workflow_type = values["workflow_type"].upper()
        IntentCategory(workflow_type)
        retry_config = values.get("retry_config") or {}
        max_retries = int(retry_config.get("max_retries", 3))
        base_seconds = int(retry_config.get("base_seconds", 30))
        if max_retries < 0 or max_retries > 20 or base_seconds < 1:
            raise ValueError("Invalid retry configuration")
        values.update(
            task_id=f"TASK-{uuid.uuid4().hex[:12].upper()}",
            trigger_type=trigger_type,
            workflow_type=workflow_type,
            retry_config={
                "max_retries": max_retries,
                "backoff": retry_config.get("backoff", "exponential"),
                "base_seconds": base_seconds,
            },
            owner_id=owner_id,
            owner_name=owner_name,
        )
        values["next_run_at"] = (
            cls.next_fire(values.get("schedule_cron"))
            if trigger_type == "SCHEDULE" and values.get("is_enabled", True)
            else None
        )
        task = TaskRepository.create(db, **values)
        log_event(
            db,
            event_type="scheduled_task_created",
            actor_id=owner_id,
            entity_type="scheduled_task",
            entity_id=task.id,
            action="create",
            metadata={"task_id": task.task_id, "priority": task.priority.value},
        )
        return task

    @staticmethod
    def targets(db: Session, task: ScheduledTask) -> list[int | None]:
        scope = (task.target_scope or "NONE").upper()
        query = db.query(Employee)
        if scope == "ALL_EMPLOYEES":
            return [item.id for item in query.all()]
        if scope == "DEPARTMENT":
            return [
                item.id
                for item in query.filter(
                    Employee.department == task.target_scope_value
                ).all()
            ]
        if scope == "COUNTRY":
            return [
                item.id
                for item in query.filter(Employee.country == task.target_scope_value).all()
            ]
        if scope == "EMPLOYEE":
            employee = query.filter(Employee.id == int(task.target_scope_value)).first()
            return [employee.id] if employee else []
        return [None]

    @classmethod
    def execute(
        cls,
        db: Session,
        task_id: str,
        *,
        triggered_by: str,
        triggered_by_user_id: int | None = None,
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        task = TaskRepository.get(db, task_id)
        if not task:
            return False, "Scheduled task not found", None
        if not task.is_enabled:
            return False, "Scheduled task is disabled", None
        run = TaskRepository.create_run(
            db,
            task,
            f"RUN-{uuid.uuid4().hex[:12].upper()}",
            triggered_by,
            triggered_by_user_id,
        )
        return cls._attempt(db, task, run, create_workflows=True)

    @classmethod
    def retry(cls, db: Session, run: TaskRun):
        return cls._attempt(db, run.task, run, create_workflows=False)

    @classmethod
    def _attempt(
        cls, db: Session, task: ScheduledTask, run: TaskRun, *, create_workflows: bool
    ):
        started = perf_counter()
        run.status = "RUNNING"
        run.started_at = datetime.utcnow()
        run.next_retry_at = None
        db.commit()
        try:
            existing = (run.results or {}).get("workflows", [])
            results = []
            if create_workflows:
                targets = cls.targets(db, task)
                if not targets:
                    raise RuntimeError("Scheduled task target scope matched no employees")
                for employee_id in targets:
                    workflow = WorkflowService.create_workflow(
                        db,
                        TriggerType.SCHEDULED_SCAN,
                        task.owner_id,
                        employee_id,
                        task.description or task.name,
                        {
                            **(task.task_payload or {}),
                            "intent": task.workflow_type,
                            "scheduled_task_id": task.task_id,
                            "task_run_id": run.run_id,
                        },
                    )
                    results.append(
                        {"workflow_id": workflow["workflow_id"], "success": None}
                    )
            else:
                results = existing

            failures = []
            for item in results:
                if (
                    task.timeout_seconds
                    and perf_counter() - started > task.timeout_seconds
                ):
                    item.update(success=False, error="Task execution timed out")
                    failures.append(item)
                    continue
                workflow = WorkflowRepository.get_workflow(db, item["workflow_id"])
                if workflow.current_state == WorkflowState.FAILED:
                    retried, error, _ = WorkflowService.retry_workflow(
                        db, workflow.workflow_id
                    )
                    if not retried:
                        item.update(success=False, error=error)
                        failures.append(item)
                        continue
                success, error, outcome = AgentOrchestrationService.run(
                    db, workflow.workflow_id
                )
                item.update(
                    success=success,
                    error=error,
                    state=(
                        outcome["state"] if outcome else workflow.current_state.value
                    ),
                )
                if (
                    task.timeout_seconds
                    and perf_counter() - started > task.timeout_seconds
                ):
                    item.update(success=False, error="Task execution timed out")
                    success = False
                if not success:
                    failures.append(item)

            run.results = {"workflows": results}
            if failures:
                return cls._schedule_retry_or_fail(db, task, run, failures, started)
            run.status = "SUCCESS"
            run.completed_at = datetime.utcnow()
            run.duration_ms = int((perf_counter() - started) * 1000)
            task.last_run_at = datetime.utcnow()
            db.commit()
            cls._audit_run(db, task, run)
            return True, None, cls.serialize_run(run)
        except Exception as exc:
            run.error_message = str(exc)
            return cls._schedule_retry_or_fail(db, task, run, [], started)

    @classmethod
    def _schedule_retry_or_fail(cls, db, task, run, failures, started):
        config = task.retry_config or {}
        max_retries = int(config.get("max_retries", 3))
        if run.retry_count < max_retries:
            base = int(config.get("base_seconds", 30))
            delay = (
                base * (2**run.retry_count)
                if config.get("backoff") == "exponential"
                else base
            )
            run.retry_count += 1
            run.status = "RETRY_SCHEDULED"
            run.next_retry_at = datetime.utcnow() + timedelta(seconds=delay)
            run.error_message = (
                f"{len(failures)} workflow(s) failed"
                if failures
                else run.error_message
            )
        else:
            run.status = "FAILED"
            run.completed_at = datetime.utcnow()
        run.duration_ms = int((perf_counter() - started) * 1000)
        db.commit()
        cls._audit_run(db, task, run)
        error = run.error_message or "Task execution failed"
        return False, error, cls.serialize_run(run)

    @staticmethod
    def _audit_run(db: Session, task: ScheduledTask, run: TaskRun) -> None:
        MetricsCollector.observe_task(run.status)
        log_event(
            db,
            event_type="task_run_updated",
            actor_id=run.triggered_by_user_id,
            entity_type="task_run",
            entity_id=run.id,
            action=run.status.lower(),
            metadata={
                "task_id": task.task_id,
                "run_id": run.run_id,
                "status": run.status,
                "retry_count": run.retry_count,
            },
        )

    @staticmethod
    def serialize_task(task: ScheduledTask) -> dict[str, Any]:
        return {
            "task_id": task.task_id,
            "name": task.name,
            "description": task.description,
            "trigger_type": task.trigger_type,
            "priority": task.priority.value,
            "is_enabled": task.is_enabled,
            "schedule_cron": task.schedule_cron,
            "target_scope": task.target_scope,
            "target_scope_value": task.target_scope_value,
            "workflow_type": task.workflow_type,
            "task_payload": task.task_payload,
            "retry_config": task.retry_config,
            "timeout_seconds": task.timeout_seconds,
            "owner_id": task.owner_id,
            "owner_name": task.owner_name,
            "last_run_at": task.last_run_at,
            "next_run_at": task.next_run_at,
            "created_at": task.created_at,
        }

    @staticmethod
    def serialize_run(run: TaskRun) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "task_id": run.task.task_id,
            "status": run.status,
            "triggered_by": run.triggered_by,
            "triggered_by_user_id": run.triggered_by_user_id,
            "started_at": run.started_at,
            "completed_at": run.completed_at,
            "duration_ms": run.duration_ms,
            "results": run.results,
            "error_message": run.error_message,
            "retry_count": run.retry_count,
            "next_retry_at": run.next_retry_at,
            "created_at": run.created_at,
        }
