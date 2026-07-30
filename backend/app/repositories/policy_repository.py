"""Persistence operations for policies, chunks, and incidents."""
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session, joinedload

from app.models.rag import Incident, Policy, PolicyChunk


class PolicyRepository:
    @staticmethod
    def get(db: Session, policy_id: str) -> Policy | None:
        return db.query(Policy).options(joinedload(Policy.chunks)).filter(
            Policy.policy_id == policy_id
        ).first()

    @staticmethod
    def create_policy(db: Session, **values: Any) -> Policy:
        policy = Policy(**values)
        db.add(policy)
        db.commit()
        db.refresh(policy)
        return policy

    @staticmethod
    def replace_chunks(db: Session, policy: Policy, chunks: list[dict[str, Any]]) -> None:
        db.query(PolicyChunk).filter(PolicyChunk.policy_id == policy.id).delete()
        for values in chunks:
            db.add(PolicyChunk(policy_id=policy.id, **values))
        db.commit()
        db.refresh(policy)

    @staticmethod
    def searchable_chunks(
        db: Session,
        *,
        country: str | None = None,
        legal_entity: str | None = None,
        business_unit: str | None = None,
        employee_type: str | None = None,
        policy_type: str | None = None,
        as_of: datetime | None = None,
    ) -> list[PolicyChunk]:
        as_of = as_of or datetime.utcnow()
        query = db.query(PolicyChunk).join(Policy).options(joinedload(PolicyChunk.policy)).filter(
            Policy.status == "ACTIVE",
            Policy.effective_from <= as_of,
            (Policy.effective_to.is_(None) | (Policy.effective_to >= as_of)),
        )
        if country:
            query = query.filter(Policy.country == country)
        if legal_entity:
            query = query.filter(Policy.legal_entity == legal_entity)
        if business_unit:
            query = query.filter(
                (Policy.business_unit.is_(None)) | (Policy.business_unit == business_unit)
            )
        if employee_type:
            query = query.filter(
                (Policy.employee_type.is_(None))
                | (Policy.employee_type == "ALL")
                | (Policy.employee_type == employee_type)
            )
        if policy_type:
            query = query.filter(Policy.policy_type == policy_type)
        return query.all()

    @staticmethod
    def create_incident(db: Session, **values: Any) -> Incident:
        incident = Incident(**values)
        db.add(incident)
        db.commit()
        db.refresh(incident)
        return incident

    @staticmethod
    def incidents(
        db: Session,
        *,
        incident_type: str | None = None,
        country: str | None = None,
        business_unit: str | None = None,
    ) -> list[Incident]:
        query = db.query(Incident)
        if incident_type:
            query = query.filter(Incident.incident_type == incident_type)
        if country:
            query = query.filter(Incident.country == country)
        if business_unit:
            query = query.filter(Incident.business_unit == business_unit)
        return query.all()
