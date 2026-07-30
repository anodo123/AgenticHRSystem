"""Task scheduling and execution routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.schemas.task import (
    TaskCreateRequest,
    TaskEnableRequest,
    TaskListResponse,
    TaskResponse,
    TaskRunListResponse,
    TaskRunResponse,
)
from app.db.session import get_db
from app.models.user import User
from app.repositories.task_repository import TaskRepository
from app.security import get_current_user
from app.services.task_service import TaskService

router = APIRouter(tags=["Task Scheduling"])


def can_manage(user: User) -> bool:
    roles = {role.name for role in user.roles}
    permissions = {
        permission.name for role in user.roles for permission in role.permissions
    }
    return bool(
        user.is_superuser
        or roles.intersection({"HR_ADMIN", "SYSTEM_ADMIN"})
        or "manage_tasks" in permissions
    )


def require_manage(user: User) -> None:
    if not can_manage(user):
        raise HTTPException(status_code=403, detail="Task management permission required")


@router.post("/", response_model=TaskResponse)
async def create_task(
    request: TaskCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manage(current_user)
    try:
        task = TaskService.create_task(
            db,
            owner_id=current_user.id,
            owner_name=current_user.full_name,
            **request.model_dump(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaskResponse(**TaskService.serialize_task(task))


@router.get("/", response_model=TaskListResponse)
async def list_tasks(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    enabled: bool | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manage(current_user)
    total, tasks = TaskRepository.list(db, skip, limit, enabled)
    return TaskListResponse(
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        items=[TaskResponse(**TaskService.serialize_task(task)) for task in tasks],
    )


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manage(current_user)
    task = TaskRepository.get(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    return TaskResponse(**TaskService.serialize_task(task))


@router.patch("/{task_id}/enabled", response_model=TaskResponse)
async def set_task_enabled(
    task_id: str,
    request: TaskEnableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manage(current_user)
    task = TaskRepository.get(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    TaskRepository.set_enabled(db, task, request.is_enabled)
    if request.is_enabled and task.trigger_type == "SCHEDULE":
        task.next_run_at = TaskService.next_fire(task.schedule_cron)
        db.commit()
    return TaskResponse(**TaskService.serialize_task(task))


@router.post("/{task_id}/run", response_model=TaskRunResponse)
async def run_task(
    task_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manage(current_user)
    success, error, result = TaskService.execute(
        db,
        task_id,
        triggered_by="MANUAL",
        triggered_by_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(
            status_code=404 if error and "not found" in error else 400,
            detail=error,
        )
    return TaskRunResponse(**result)


@router.get("/{task_id}/runs", response_model=TaskRunListResponse)
async def list_task_runs(
    task_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_manage(current_user)
    task = TaskRepository.get(db, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Scheduled task not found")
    total, runs = TaskRepository.runs(db, task.id, skip, limit)
    return TaskRunListResponse(
        total=total,
        page=skip // limit + 1,
        page_size=limit,
        items=[TaskRunResponse(**TaskService.serialize_run(run)) for run in runs],
    )
