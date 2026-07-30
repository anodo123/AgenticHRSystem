"""Persistence for scheduled tasks and durable task runs."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import case
from sqlalchemy.orm import Session

from app.models.task import ScheduledTask, TaskPriority, TaskRun


class TaskRepository:
    PRIORITY_ORDER = case(
        (ScheduledTask.priority == TaskPriority.CRITICAL, 0),
        (ScheduledTask.priority == TaskPriority.HIGH, 1),
        (ScheduledTask.priority == TaskPriority.MEDIUM, 2),
        else_=3,
    )

    @staticmethod
    def create(db: Session, **values: Any) -> ScheduledTask:
        task = ScheduledTask(**values)
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def get(db: Session, task_id: str) -> ScheduledTask | None:
        return db.query(ScheduledTask).filter(ScheduledTask.task_id == task_id).first()

    @staticmethod
    def list(
        db: Session, skip: int = 0, limit: int = 50, enabled: bool | None = None
    ) -> tuple[int, list[ScheduledTask]]:
        query = db.query(ScheduledTask)
        if enabled is not None:
            query = query.filter(ScheduledTask.is_enabled == enabled)
        total = query.count()
        tasks = query.order_by(
            TaskRepository.PRIORITY_ORDER, ScheduledTask.created_at
        ).offset(skip).limit(limit).all()
        return total, tasks

    @staticmethod
    def due(db: Session, now: datetime | None = None) -> list[ScheduledTask]:
        return db.query(ScheduledTask).filter(
            ScheduledTask.is_enabled.is_(True),
            ScheduledTask.trigger_type == "SCHEDULE",
            ScheduledTask.next_run_at.is_not(None),
            ScheduledTask.next_run_at <= (now or datetime.utcnow()),
        ).order_by(TaskRepository.PRIORITY_ORDER, ScheduledTask.next_run_at).all()

    @staticmethod
    def update_next_run(
        db: Session, task: ScheduledTask, next_run_at: datetime | None
    ) -> None:
        task.last_run_at = datetime.utcnow()
        task.next_run_at = next_run_at
        task.updated_at = datetime.utcnow()
        db.commit()

    @staticmethod
    def set_enabled(db: Session, task: ScheduledTask, enabled: bool) -> ScheduledTask:
        task.is_enabled = enabled
        task.updated_at = datetime.utcnow()
        if not enabled:
            task.next_run_at = None
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    def create_run(
        db: Session,
        task: ScheduledTask,
        run_id: str,
        triggered_by: str,
        triggered_by_user_id: int | None,
    ) -> TaskRun:
        run = TaskRun(
            task_id=task.id,
            run_id=run_id,
            status="PENDING",
            triggered_by=triggered_by,
            triggered_by_user_id=triggered_by_user_id,
        )
        db.add(run)
        db.commit()
        db.refresh(run)
        return run

    @staticmethod
    def runs(
        db: Session, task_pk: int, skip: int = 0, limit: int = 50
    ) -> tuple[int, list[TaskRun]]:
        query = db.query(TaskRun).filter(TaskRun.task_id == task_pk)
        total = query.count()
        return total, query.order_by(TaskRun.created_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def retry_due(db: Session, now: datetime | None = None) -> list[TaskRun]:
        return db.query(TaskRun).join(ScheduledTask).filter(
            TaskRun.status == "RETRY_SCHEDULED",
            TaskRun.next_retry_at <= (now or datetime.utcnow()),
            ScheduledTask.is_enabled.is_(True),
        ).order_by(TaskRepository.PRIORITY_ORDER, TaskRun.next_retry_at).all()
