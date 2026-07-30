"""APScheduler dispatcher for durable priority-ordered tasks."""
import logging

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.task_repository import TaskRepository
from app.services.task_service import TaskService
from app.workers.scheduler_compat import BackgroundScheduler

logger = logging.getLogger(__name__)


class TaskScheduler:
    scheduler: BackgroundScheduler | None = None

    @classmethod
    def start(cls) -> None:
        if not get_settings().scheduler_enabled:
            return
        if cls.scheduler and cls.scheduler.running:
            return
        cls.scheduler = BackgroundScheduler(timezone=get_settings().scheduler_timezone)
        cls.scheduler.add_job(
            cls.dispatch,
            "interval",
            seconds=10,
            id="durable-task-dispatcher",
            replace_existing=True,
            max_instances=1,
            coalesce=True,
        )
        cls.scheduler.start()

    @classmethod
    def shutdown(cls) -> None:
        if cls.scheduler and cls.scheduler.running:
            cls.scheduler.shutdown(wait=False)
        cls.scheduler = None

    @staticmethod
    def dispatch() -> None:
        db = SessionLocal()
        try:
            for run in TaskRepository.retry_due(db):
                TaskService.retry(db, run)
            for task in TaskRepository.due(db):
                TaskService.execute(db, task.task_id, triggered_by="SCHEDULE")
                TaskRepository.update_next_run(
                    db, task, TaskService.next_fire(task.schedule_cron)
                )
        except Exception:
            logger.exception("Scheduled task dispatcher failed")
        finally:
            db.close()
