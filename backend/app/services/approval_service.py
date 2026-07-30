"""Human approval workflow service."""
from datetime import datetime, timedelta
from typing import Any, Optional
import uuid

from sqlalchemy.orm import Session

from app.audit import log_approval_decision, log_event
from app.core.config import get_settings
from app.models.approval import ApprovalRequest, ApprovalStatus
from app.models.user import User
from app.models.workflow import WorkflowState
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.services.workflow_service import WorkflowService


class ApprovalService:
    """Create and decide approval requests tied to persisted workflows."""

    @staticmethod
    def create_request(
        db: Session,
        *,
        workflow_id: str,
        proposed_action: str,
        risk_level: str,
        financial_impact: str,
        required_approver_roles: list[str],
        affected_employee_id: Optional[int] = None,
        policy_references: Optional[list[str]] = None,
        evidence_summary: Optional[str] = None,
        expiry_hours: Optional[int] = None,
    ) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None
        if workflow.current_state != WorkflowState.COMPLIANCE_REVIEW:
            return False, "Approval can only be requested from COMPLIANCE_REVIEW", None
        if ApprovalRepository.get_pending_for_workflow(db, workflow.id):
            return False, "Workflow already has a pending approval", None
        if not required_approver_roles:
            return False, "At least one approver role is required", None

        success, error, _ = WorkflowService.transition_workflow(
            db, workflow_id, WorkflowState.WAITING_FOR_APPROVAL,
            reason="Human approval required", triggered_by="compliance",
        )
        if not success:
            return False, error, None

        hours = expiry_hours or get_settings().approval_expiry_hours
        approval = ApprovalRepository.create(
            db,
            approval_id=f"APR-{uuid.uuid4().hex[:12].upper()}",
            workflow_id=workflow.id,
            proposed_action=proposed_action,
            affected_employee_id=affected_employee_id,
            risk_level=risk_level,
            financial_impact=financial_impact,
            policy_references=policy_references,
            evidence_summary=evidence_summary,
            required_approver_roles=required_approver_roles,
            expires_at=datetime.utcnow() + timedelta(hours=hours),
        )
        WorkflowRepository.pause_workflow(db, workflow_id, "Waiting for human approval")
        log_event(
            db, event_type="approval_requested", workflow_id=workflow.id,
            entity_type="approval", entity_id=approval.id, action="create",
            metadata={"approval_id": approval.approval_id},
        )
        log_event(
            db, event_type="approval_notification_queued", workflow_id=workflow.id,
            entity_type="approval", entity_id=approval.id, action="notify",
            metadata={"required_role": required_approver_roles[0], "level": 0},
        )
        return True, None, ApprovalService.serialize(approval)

    @staticmethod
    def decide(
        db: Session,
        *,
        approval_id: str,
        approver: User,
        approve: bool,
        comments: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
        approval = ApprovalRepository.get(db, approval_id)
        if not approval:
            return False, "Approval request not found", None
        if approval.status != ApprovalStatus.PENDING:
            return False, f"Approval is already {approval.status.value}", None

        workflow = WorkflowRepository.get_workflow_by_pk(db, approval.workflow_id)
        if not workflow or workflow.current_state != WorkflowState.WAITING_FOR_APPROVAL:
            return False, "Workflow is not waiting for approval", None

        if approval.expires_at <= datetime.utcnow():
            ApprovalService._expire(db, approval)
            return False, "Approval request has expired", None

        if not ApprovalService.can_decide(approval, approver):
            return False, "User does not have a required approver role or delegation for the current approval level", None

        status = ApprovalStatus.APPROVED if approve else ApprovalStatus.REJECTED
        ApprovalRepository.record_decision(
            db, approval, approver.id, status.value, comments,
        )
        if approve and approval.current_level + 1 < approval.total_levels:
            ApprovalRepository.advance_level(db, approval)
            log_approval_decision(
                db, approver.id, workflow.id, "LEVEL_APPROVED", comments,
            )
            log_event(
                db, event_type="approval_notification_queued", workflow_id=workflow.id,
                entity_type="approval", entity_id=approval.id, action="notify",
                metadata={
                    "required_role": approval.required_approver_roles[approval.current_level],
                    "level": approval.current_level,
                },
            )
            return True, None, ApprovalService.serialize(approval)

        ApprovalRepository.resolve(
            db, approval, status=status, approver_id=approver.id, comments=comments,
        )
        if workflow.paused_at:
            WorkflowRepository.resume_workflow(db, workflow.workflow_id)
        target = WorkflowState.APPROVED if approve else WorkflowState.REJECTED
        success, error, _ = WorkflowService.transition_workflow(
            db, workflow.workflow_id, target,
            reason=comments or status.value, triggered_by=f"user:{approver.id}",
        )
        if not success:
            return False, error, None
        log_approval_decision(
            db, approver.id, workflow.id, status.value, comments,
        )
        return True, None, ApprovalService.serialize(approval)

    @staticmethod
    def can_decide(approval: ApprovalRequest, user: User) -> bool:
        if user.is_superuser:
            return True
        if approval.delegated_to_id:
            return approval.delegated_to_id == user.id
        required_role = approval.required_approver_roles[approval.current_level]
        return required_role in {role.name for role in user.roles}

    @staticmethod
    def can_view(approval: ApprovalRequest, user: User) -> bool:
        return (
            user.is_superuser
            or approval.workflow.requester_id == user.id
            or ApprovalService.can_decide(approval, user)
            or approval.approver_id == user.id
            or any(item.approver_id == user.id for item in approval.decisions)
        )

    @staticmethod
    def delegate(
        db: Session,
        *,
        approval_id: str,
        delegator: User,
        delegated_to_id: int,
        reason: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
        approval = ApprovalRepository.get(db, approval_id)
        if not approval:
            return False, "Approval request not found", None
        if approval.status != ApprovalStatus.PENDING:
            return False, f"Approval is already {approval.status.value}", None
        if approval.expires_at <= datetime.utcnow():
            ApprovalService._expire(db, approval)
            return False, "Approval request has expired", None
        if not ApprovalService.can_decide(approval, delegator):
            return False, "User does not have a required approver role or delegation for the current approval level", None
        if delegator.id == delegated_to_id:
            return False, "Cannot delegate approval to yourself", None
        target = db.query(User).filter(User.id == delegated_to_id, User.is_active.is_(True)).first()
        if not target:
            return False, "Delegated user not found or inactive", None
        ApprovalRepository.delegate(
            db, approval, delegator.id, target.id, reason,
        )
        log_event(
            db, event_type="approval_delegated", actor_id=delegator.id,
            workflow_id=approval.workflow_id, entity_type="approval",
            entity_id=approval.id, action="delegate",
            metadata={"delegated_to_id": target.id, "reason": reason},
        )
        return True, None, ApprovalService.serialize(approval)

    @staticmethod
    def cancel(
        db: Session,
        *,
        approval_id: str,
        actor: User,
        reason: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[dict[str, Any]]]:
        approval = ApprovalRepository.get(db, approval_id)
        if not approval:
            return False, "Approval request not found", None
        if approval.status != ApprovalStatus.PENDING:
            return False, f"Approval is already {approval.status.value}", None
        workflow = approval.workflow
        if not actor.is_superuser and workflow.requester_id != actor.id:
            return False, "Only the requester or an administrator can cancel approval", None
        ApprovalRepository.resolve(
            db, approval, status=ApprovalStatus.CANCELLED,
            approver_id=None, comments=reason,
        )
        if workflow.paused_at:
            WorkflowRepository.resume_workflow(db, workflow.workflow_id)
        WorkflowService.cancel_workflow(db, workflow.workflow_id, reason or "Approval cancelled")
        log_event(
            db, event_type="approval_cancelled", actor_id=actor.id,
            workflow_id=workflow.id, entity_type="approval",
            entity_id=approval.id, action="cancel", metadata={"reason": reason},
        )
        return True, None, ApprovalService.serialize(approval)

    @staticmethod
    def process_expired(db: Session) -> int:
        approvals = ApprovalRepository.expired_pending(db)
        for approval in approvals:
            ApprovalService._expire(db, approval)
        return len(approvals)

    @staticmethod
    def _expire(db: Session, approval: ApprovalRequest) -> None:
        if approval.status != ApprovalStatus.PENDING:
            return
        workflow = approval.workflow
        ApprovalRepository.resolve(
            db, approval, status=ApprovalStatus.EXPIRED,
            approver_id=None, comments="Approval expired",
        )
        if workflow.paused_at:
            WorkflowRepository.resume_workflow(db, workflow.workflow_id)
        if workflow.current_state == WorkflowState.WAITING_FOR_APPROVAL:
            WorkflowService.transition_workflow(
                db, workflow.workflow_id, WorkflowState.EXPIRED,
                reason="Approval expired", triggered_by="system",
            )
        log_event(
            db, event_type="approval_expired", workflow_id=workflow.id,
            entity_type="approval", entity_id=approval.id, action="expire",
        )

    @staticmethod
    def serialize(approval) -> dict[str, Any]:
        return {
            "approval_id": approval.approval_id,
            "workflow_id": approval.workflow.workflow_id,
            "proposed_action": approval.proposed_action,
            "risk_level": approval.risk_level,
            "financial_impact": approval.financial_impact,
            "required_approver_roles": approval.required_approver_roles,
            "status": approval.status.value,
            "expires_at": approval.expires_at,
            "resolved_at": approval.resolved_at,
            "approver_id": approval.approver_id,
            "decision_comments": approval.decision_comments,
            "current_level": approval.current_level,
            "total_levels": approval.total_levels,
            "current_required_role": (
                approval.required_approver_roles[approval.current_level]
                if approval.status == ApprovalStatus.PENDING
                and approval.current_level < approval.total_levels else None
            ),
            "delegated_to_id": approval.delegated_to_id,
            "delegated_by_id": approval.delegated_by_id,
            "delegation_reason": approval.delegation_reason,
            "decisions": [
                {
                    "level": item.level,
                    "required_role": item.required_role,
                    "approver_id": item.approver_id,
                    "decision": item.decision,
                    "comments": item.comments,
                    "created_at": item.created_at,
                }
                for item in approval.decisions
            ],
        }
