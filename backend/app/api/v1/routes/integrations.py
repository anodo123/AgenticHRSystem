"""Mock HR integration routes."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.adapters.factory import AdapterFactory
from app.adapters.freshness_gate import FreshnessGate
from app.api.v1.schemas.integration import (
    AdapterMutationRequest,
    AdapterMutationResponse,
    AdapterReadResponse,
)
from app.db.session import get_db
from app.models.user import User
from app.security import get_current_user

router = APIRouter(tags=["HR Integrations"])


@router.get("/health")
async def integration_health(current_user: User = Depends(get_current_user)):
    return AdapterFactory.health()


@router.get("/{system}/employees/{employee_id}", response_model=AdapterReadResponse)
async def read_employee_data(
    system: str,
    employee_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = AdapterFactory.get(system).read(db, employee_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    freshness = FreshnessGate.evaluate(result)
    if not result.success:
        raise HTTPException(status_code=404, detail=result.error)
    return AdapterReadResponse(
        system=result.system, success=True, data=result.data,
        fetched_at=result.fetched_at.isoformat(), fresh=freshness.fresh,
        age_seconds=freshness.age_seconds,
    )


@router.post("/{system}/employees/{employee_id}/dry-run", response_model=AdapterMutationResponse)
async def dry_run_mutation(
    system: str,
    employee_id: int,
    request: AdapterMutationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        result = AdapterFactory.get(system).dry_run(db, employee_id, request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return AdapterMutationResponse(
        system=result.system, success=True, data=result.data, dry_run=True,
    )
