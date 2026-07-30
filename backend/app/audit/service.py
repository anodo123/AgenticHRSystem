"""Audit logging service."""
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional, Any, Dict
import hashlib
import json

from app.models.audit import AuditLog


def hash_dict(data: Dict[str, Any]) -> str:
    """Hash a dictionary to string."""
    json_str = json.dumps(data, sort_keys=True, default=str)
    return hashlib.sha256(json_str.encode()).hexdigest()


def log_event(
    db: Session,
    event_type: str,
    actor_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    workflow_id: Optional[int] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[int] = None,
    action: Optional[str] = None,
    decision: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    previous_state: Optional[Dict[str, Any]] = None,
    current_state: Optional[Dict[str, Any]] = None,
) -> AuditLog:
    """Log audit event."""
    # Get previous hash from last record of same entity
    previous_hash = None
    if entity_type and entity_id:
        last_record = (
            db.query(AuditLog)
            .filter(
                AuditLog.entity_type == entity_type,
                AuditLog.entity_id == entity_id,
            )
            .order_by(AuditLog.timestamp.desc())
            .first()
        )
        if last_record:
            previous_hash = last_record.current_hash
    
    # Calculate current hash
    state_data = current_state or {}
    current_hash = hash_dict(state_data)
    
    audit_log = AuditLog(
        event_type=event_type,
        actor_id=actor_id,
        actor_role=actor_role,
        workflow_id=workflow_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        decision=decision,
        event_metadata=metadata,
        previous_hash=previous_hash,
        current_hash=current_hash,
        timestamp=datetime.utcnow(),
    )
    
    db.add(audit_log)
    db.commit()
    
    return audit_log


def log_login(
    db: Session,
    user_id: int,
    success: bool = True,
) -> AuditLog:
    """Log user login."""
    return log_event(
        db=db,
        event_type="login",
        actor_id=user_id,
        action="login",
        metadata={"success": success},
    )


def log_api_request(
    db: Session,
    actor_id: int,
    method: str,
    path: str,
    status_code: int,
) -> AuditLog:
    """Log API request."""
    return log_event(
        db=db,
        event_type="api_request",
        actor_id=actor_id,
        action=f"{method} {path}",
        metadata={"method": method, "path": path, "status_code": status_code},
    )


def log_workflow_created(
    db: Session,
    actor_id: int,
    workflow_id: int,
    intent: str,
) -> AuditLog:
    """Log workflow creation."""
    return log_event(
        db=db,
        event_type="workflow_created",
        actor_id=actor_id,
        workflow_id=workflow_id,
        entity_type="workflow",
        entity_id=workflow_id,
        action="create",
        metadata={"intent": intent},
    )


def log_state_transition(
    db: Session,
    workflow_id: int,
    from_state: str,
    to_state: str,
    reason: Optional[str] = None,
) -> AuditLog:
    """Log workflow state transition."""
    return log_event(
        db=db,
        event_type="state_transition",
        workflow_id=workflow_id,
        entity_type="workflow",
        entity_id=workflow_id,
        action=f"{from_state} -> {to_state}",
        metadata={"from_state": from_state, "to_state": to_state, "reason": reason},
    )


def log_approval_decision(
    db: Session,
    approver_id: int,
    workflow_id: int,
    decision: str,
    reason: Optional[str] = None,
) -> AuditLog:
    """Log approval decision."""
    return log_event(
        db=db,
        event_type="approval_decision",
        actor_id=approver_id,
        workflow_id=workflow_id,
        entity_type="approval",
        action="decide",
        decision=decision,
        metadata={"reason": reason},
    )


def log_action_execution(
    db: Session,
    actor_id: int,
    workflow_id: int,
    action_type: str,
    before_state: Dict[str, Any],
    after_state: Dict[str, Any],
    success: bool = True,
) -> AuditLog:
    """Log action execution."""
    return log_event(
        db=db,
        event_type="action_execution",
        actor_id=actor_id,
        workflow_id=workflow_id,
        entity_type="action",
        action=action_type,
        metadata={"success": success},
        previous_state=before_state,
        current_state=after_state,
    )
