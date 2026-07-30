"""Phase 7 multi-level approval, delegation, expiry, and cancellation tests."""
from datetime import datetime, timedelta

from app.models.approval import ApprovalDecisionEntry, ApprovalStatus
from app.models.audit import AuditLog
from app.models.user import Role, User
from app.models.workflow import TriggerType, WorkflowState
from app.repositories.approval_repository import ApprovalRepository
from app.repositories.workflow_repository import WorkflowRepository
from app.services.approval_service import ApprovalService
from app.services.workflow_service import WorkflowService


def ready(db, requester_id):
    workflow_id = WorkflowService.create_workflow(
        db, TriggerType.HR_OPERATIONS_REQUEST, requester_id, None, "Sensitive correction",
    )["workflow_id"]
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    workflow.current_state = WorkflowState.COMPLIANCE_REVIEW
    db.commit()
    return workflow_id


def add_user(db, username, role_name=None, superuser=False):
    roles = []
    if role_name:
        role = db.query(Role).filter(Role.name == role_name).first()
        if not role:
            role = Role(name=role_name)
            db.add(role)
            db.flush()
        roles = [role]
    user = User(
        username=username,
        email=f"{username}@example.com",
        full_name=username.title(),
        hashed_password="unused",
        is_superuser=superuser,
        roles=roles,
    )
    db.add(user)
    db.commit()
    return user


def create_multilevel(db, requester_id):
    return ApprovalService.create_request(
        db,
        workflow_id=ready(db, requester_id),
        proposed_action="Correct sensitive payroll",
        risk_level="CRITICAL",
        financial_impact="HIGH",
        required_approver_roles=["MANAGER", "HR_ADMIN"],
    )[2]


def test_multi_level_approval_keeps_workflow_paused_until_final_level(db, users):
    requester, hr_admin, _ = users
    manager = add_user(db, "manager7", "MANAGER")
    created = create_multilevel(db, requester.id)
    approval = ApprovalRepository.get(db, created["approval_id"])

    success, error, first = ApprovalService.decide(
        db, approval_id=approval.approval_id, approver=manager,
        approve=True, comments="Manager approved",
    )
    assert success, error
    assert first["status"] == "PENDING"
    assert first["current_level"] == 1
    assert first["current_required_role"] == "HR_ADMIN"
    assert approval.workflow.current_state == WorkflowState.WAITING_FOR_APPROVAL
    assert approval.workflow.paused_at is not None

    success, error, final = ApprovalService.decide(
        db, approval_id=approval.approval_id, approver=hr_admin,
        approve=True, comments="HR approved",
    )
    assert success, error
    assert final["status"] == "APPROVED"
    assert approval.workflow.current_state == WorkflowState.APPROVED
    assert approval.workflow.paused_at is None
    assert db.query(ApprovalDecisionEntry).count() == 2
    assert [item["required_role"] for item in final["decisions"]] == ["MANAGER", "HR_ADMIN"]


def test_delegation_grants_only_named_user_current_level_access(db, users):
    requester, _, outsider = users
    manager = add_user(db, "manager_delegate", "MANAGER")
    target = add_user(db, "delegate_target")
    created = create_multilevel(db, requester.id)
    success, error, delegated = ApprovalService.delegate(
        db,
        approval_id=created["approval_id"],
        delegator=manager,
        delegated_to_id=target.id,
        reason="Out of office",
    )
    assert success, error
    assert delegated["delegated_to_id"] == target.id
    assert not ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=manager, approve=True,
    )[0]
    assert not ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=outsider, approve=True,
    )[0]
    success, error, result = ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=target, approve=True,
    )
    assert success, error
    assert result["current_level"] == 1
    assert result["delegated_to_id"] is None
    assert db.query(AuditLog).filter(AuditLog.event_type == "approval_delegated").count() == 1


def test_rejection_at_first_level_is_terminal(db, users):
    requester = users[0]
    manager = add_user(db, "manager_reject", "MANAGER")
    created = create_multilevel(db, requester.id)
    success, error, rejected = ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=manager,
        approve=False, comments="Insufficient evidence",
    )
    assert success, error
    assert rejected["status"] == "REJECTED"
    assert ApprovalRepository.get(db, created["approval_id"]).workflow.current_state == WorkflowState.REJECTED


def test_expiry_processor_expires_approval_and_workflow(db, users):
    created = create_multilevel(db, users[0].id)
    approval = ApprovalRepository.get(db, created["approval_id"])
    approval.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert ApprovalService.process_expired(db) == 1
    assert approval.status == ApprovalStatus.EXPIRED
    assert approval.workflow.current_state == WorkflowState.EXPIRED
    assert approval.workflow.paused_at is None
    assert db.query(AuditLog).filter(AuditLog.event_type == "approval_expired").count() == 1


def test_requester_can_cancel_pending_approval(db, users):
    requester = users[0]
    created = create_multilevel(db, requester.id)
    success, error, cancelled = ApprovalService.cancel(
        db, approval_id=created["approval_id"], actor=requester, reason="No longer needed",
    )
    assert success, error
    assert cancelled["status"] == "CANCELLED"
    assert ApprovalRepository.get(db, created["approval_id"]).workflow.current_state == WorkflowState.CANCELLED
