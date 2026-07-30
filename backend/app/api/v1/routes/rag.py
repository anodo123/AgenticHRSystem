"""Policy RAG and incident memory routes."""
from datetime import datetime
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.api.v1.schemas.rag import (
    IncidentCreateRequest,
    IncidentResponse,
    IncidentSearchResponse,
    PolicyIngestRequest,
    PolicyResponse,
    PolicySearchResponse,
)
from app.db.session import get_db
from app.models.user import User
from app.rag.policy_ingestion import PolicyIngestion
from app.security import get_current_user
from app.services.rag_service import RAGService

router = APIRouter(tags=["Policy RAG"])


@router.post("/policies", response_model=PolicyResponse)
async def ingest_policy(
    request: PolicyIngestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return RAGService.ingest_policy(db, actor_id=current_user.id, **request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/policies/upload", response_model=PolicyResponse)
async def upload_policy(
    metadata: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        values = json.loads(metadata)
        source_format = values.get("source_format") or (file.filename or "").rsplit(".", 1)[-1]
        values["content"] = PolicyIngestion.extract(await file.read(), source_format)
        values["source_format"] = source_format
        values["source_file"] = file.filename
        values["effective_from"] = datetime.fromisoformat(values["effective_from"])
        if values.get("effective_to"):
            values["effective_to"] = datetime.fromisoformat(values["effective_to"])
        request = PolicyIngestRequest(**values)
        return RAGService.ingest_policy(db, actor_id=current_user.id, **request.model_dump())
    except (ValueError, KeyError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/policies/search", response_model=PolicySearchResponse)
async def search_policies(
    query: str = Query(..., min_length=1),
    country: Optional[str] = None,
    legal_entity: Optional[str] = None,
    business_unit: Optional[str] = None,
    employee_type: Optional[str] = None,
    policy_type: Optional[str] = None,
    top_k: int = Query(5, ge=1, le=50),
    min_score: float = Query(0.3, ge=0, le=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = RAGService.search_policies(
        db, query, country=country, legal_entity=legal_entity,
        business_unit=business_unit, employee_type=employee_type,
        policy_type=policy_type, top_k=top_k, min_score=min_score,
    )
    return PolicySearchResponse(query=query, total=len(items), items=items)


@router.get("/policies/{policy_id}", response_model=PolicyResponse)
async def get_policy(
    policy_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = RAGService.get_policy(db, policy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Policy not found")
    return result


@router.post("/incidents", response_model=IncidentResponse)
async def remember_incident(
    request: IncidentCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return RAGService.remember_incident(db, **request.model_dump())


@router.get("/incidents/search", response_model=IncidentSearchResponse)
async def search_incidents(
    query: str = Query(..., min_length=1),
    incident_type: Optional[str] = None,
    country: Optional[str] = None,
    business_unit: Optional[str] = None,
    top_k: int = Query(3, ge=1, le=50),
    min_score: float = Query(0.4, ge=0, le=1),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    items = RAGService.search_incidents(
        db, query, incident_type=incident_type, country=country,
        business_unit=business_unit, top_k=top_k, min_score=min_score,
    )
    return IncidentSearchResponse(query=query, total=len(items), items=items)
