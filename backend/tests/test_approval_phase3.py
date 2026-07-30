"""Phase 3 approval workflow tests."""
from app.models.approval import ApprovalStatus
from app.models.workflow import TriggerType, WorkflowState
from app.repositories.workflow_repository import WorkflowRepository
from app.services.approval_service import ApprovalService
from app.services.workflow_service import WorkflowService


def approval_ready_workflow(db, requester_id):
    workflow_id = WorkflowService.create_workflow(
        db, TriggerType.HR_OPERATIONS_REQUEST, requester_id, None, "Adjust payroll",
    )["workflow_id"]
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    workflow.current_state = WorkflowState.COMPLIANCE_REVIEW
    db.commit()
    return workflow_id


def test_approval_create_pauses_and_approve_resumes(db, users):
    requester, approver, _ = users
    workflow_id = approval_ready_workflow(db, requester.id)
    success, _, created = ApprovalService.create_request(
        db, workflow_id=workflow_id, proposed_action="Correct payroll",
        risk_level="HIGH", financial_impact="MEDIUM",
        required_approver_roles=["HR_ADMIN"],
    )
    assert success and created["status"] == "PENDING"
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    assert workflow.current_state == WorkflowState.WAITING_FOR_APPROVAL
    assert workflow.paused_at is not None

    success, _, decided = ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=approver,
        approve=True, comments="Approved",
    )
    assert success and decided["status"] == "APPROVED"
    assert workflow.current_state == WorkflowState.APPROVED
    assert workflow.paused_at is None


def test_approval_rejects_unauthorized_user_then_rejects_workflow(db, users):
    requester, approver, outsider = users
    workflow_id = approval_ready_workflow(db, requester.id)
    created = ApprovalService.create_request(
        db, workflow_id=workflow_id, proposed_action="Correct payroll",
        risk_level="HIGH", financial_impact="MEDIUM",
        required_approver_roles=["HR_ADMIN"],
    )[2]
    success, error, _ = ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=outsider, approve=True,
    )
    assert not success and "required approver role" in error
    success, _, decided = ApprovalService.decide(
        db, approval_id=created["approval_id"], approver=approver, approve=False,
    )
    assert success and decided["status"] == ApprovalStatus.REJECTED.value
    assert WorkflowRepository.get_workflow(db, workflow_id).current_state == WorkflowState.REJECTED
