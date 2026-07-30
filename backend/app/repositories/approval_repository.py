"""Approval request persistence."""
from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.approval import ApprovalDecisionEntry, ApprovalRequest, ApprovalStatus


class ApprovalRepository:
    """Repository for approval request operations."""

    @staticmethod
    def create(
        db: Session,
        *,
        approval_id: str,
        workflow_id: int,
        proposed_action: str,
        risk_level: str,
        financial_impact: str,
        required_approver_roles: list[str],
        expires_at: datetime,
        affected_employee_id: Optional[int] = None,
        policy_references: Optional[list[str]] = None,
        evidence_summary: Optional[str] = None,
    ) -> ApprovalRequest:
        approval = ApprovalRequest(
            approval_id=approval_id,
            workflow_id=workflow_id,
            proposed_action=proposed_action,
            affected_employee_id=affected_employee_id,
            risk_level=risk_level,
            financial_impact=financial_impact,
            policy_references=policy_references,
            evidence_summary=evidence_summary,
            required_approver_roles=required_approver_roles,
            total_levels=len(required_approver_roles),
            expires_at=expires_at,
        )
        db.add(approval)
        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def get(db: Session, approval_id: str) -> Optional[ApprovalRequest]:
        return db.query(ApprovalRequest).filter(
            ApprovalRequest.approval_id == approval_id
        ).first()

    @staticmethod
    def get_pending_for_workflow(
        db: Session, workflow_id: int
    ) -> Optional[ApprovalRequest]:
        return db.query(ApprovalRequest).filter(
            ApprovalRequest.workflow_id == workflow_id,
            ApprovalRequest.status == ApprovalStatus.PENDING,
        ).first()

    @staticmethod
    def list_pending(
        db: Session, skip: int = 0, limit: int = 50
    ) -> tuple[int, List[ApprovalRequest]]:
        query = db.query(ApprovalRequest).filter(
            ApprovalRequest.status == ApprovalStatus.PENDING
        )
        approvals = query.order_by(ApprovalRequest.submitted_at).offset(skip).limit(limit).all()
        return query.count(), approvals

    @staticmethod
    def list(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        status: ApprovalStatus | None = None,
    ) -> tuple[int, List[ApprovalRequest]]:
        query = db.query(ApprovalRequest)
        if status:
            query = query.filter(ApprovalRequest.status == status)
        total = query.count()
        return total, query.order_by(ApprovalRequest.submitted_at.desc()).offset(skip).limit(limit).all()

    @staticmethod
    def expired_pending(db: Session, now: datetime | None = None) -> List[ApprovalRequest]:
        return db.query(ApprovalRequest).filter(
            ApprovalRequest.status == ApprovalStatus.PENDING,
            ApprovalRequest.expires_at <= (now or datetime.utcnow()),
        ).all()

    @staticmethod
    def record_decision(
        db: Session,
        approval: ApprovalRequest,
        approver_id: int,
        decision: str,
        comments: Optional[str],
    ) -> ApprovalDecisionEntry:
        entry = ApprovalDecisionEntry(
            approval_request_id=approval.id,
            level=approval.current_level,
            required_role=approval.required_approver_roles[approval.current_level],
            approver_id=approver_id,
            decision=decision,
            comments=comments,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return entry

    @staticmethod
    def advance_level(db: Session, approval: ApprovalRequest) -> ApprovalRequest:
        approval.current_level += 1
        approval.delegated_to_id = None
        approval.delegated_by_id = None
        approval.delegation_reason = None
        approval.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def delegate(
        db: Session,
        approval: ApprovalRequest,
        delegated_by_id: int,
        delegated_to_id: int,
        reason: Optional[str],
    ) -> ApprovalRequest:
        approval.delegated_by_id = delegated_by_id
        approval.delegated_to_id = delegated_to_id
        approval.delegation_reason = reason
        approval.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(approval)
        return approval

    @staticmethod
    def resolve(
        db: Session,
        approval: ApprovalRequest,
        *,
        status: ApprovalStatus,
        approver_id: Optional[int],
        comments: Optional[str],
    ) -> ApprovalRequest:
        approval.status = status
        approval.decision = status.value
        approval.approver_id = approver_id
        approval.decision_comments = comments
        approval.resolved_at = datetime.utcnow()
        approval.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(approval)
        return approval
