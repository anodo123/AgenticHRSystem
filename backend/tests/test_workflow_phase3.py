"""Phase 3 workflow behavior tests."""
from app.models.audit import AuditLog
from app.models.workflow import TriggerType, WorkflowState
from app.repositories.workflow_repository import WorkflowRepository
from app.services.workflow_service import WorkflowService


def create_workflow(db, requester_id):
    result = WorkflowService.create_workflow(
        db, TriggerType.EMPLOYEE_REQUEST, requester_id, None, "Test request",
    )
    return result["workflow_id"]


def force_state(db, workflow_id, state):
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    workflow.current_state = state
    db.commit()
    return workflow


def test_pause_blocks_transition_and_resume_preserves_state(db, users):
    workflow_id = create_workflow(db, users[0].id)
    force_state(db, workflow_id, WorkflowState.CLASSIFYING)

    success, _, paused = WorkflowService.pause_workflow(db, workflow_id, "operator hold")
    assert success and paused["state"] == "CLASSIFYING"
    success, error, _ = WorkflowService.transition_workflow(
        db, workflow_id, WorkflowState.CONTEXT_RETRIEVAL,
    )
    assert not success and "paused" in error

    success, _, resumed = WorkflowService.resume_workflow(db, workflow_id)
    assert success and resumed["state"] == "CLASSIFYING"
    success, _, transitioned = WorkflowService.transition_workflow(
        db, workflow_id, WorkflowState.CONTEXT_RETRIEVAL,
    )
    assert success and transitioned["state"] == "CONTEXT_RETRIEVAL"
    events = {row.event_type for row in db.query(AuditLog).all()}
    assert {"workflow_paused", "workflow_resumed"}.issubset(events)


def test_cancel_records_valid_transition(db, users):
    workflow_id = create_workflow(db, users[0].id)
    success, _, result = WorkflowService.cancel_workflow(db, workflow_id, "withdrawn")
    assert success and result["state"] == "CANCELLED"
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    assert workflow.previous_state == WorkflowState.RECEIVED
    transitions = WorkflowRepository.get_workflow_transitions(db, workflow.id)
    assert [(item.from_state, item.to_state) for item in transitions] == [
        (WorkflowState.RECEIVED, WorkflowState.CANCELLED)
    ]
    assert not WorkflowService.cancel_workflow(db, workflow_id)[0]


def test_retry_uses_declared_state_path_and_limit(db, users):
    workflow_id = create_workflow(db, users[0].id)
    workflow = force_state(db, workflow_id, WorkflowState.FAILED)
    workflow.max_retries = 1
    db.commit()

    success, _, result = WorkflowService.retry_workflow(db, workflow_id)
    assert success and result["state"] == "RECEIVED"
    transitions = WorkflowRepository.get_workflow_transitions(db, workflow.id)
    assert [(item.from_state, item.to_state) for item in transitions] == [
        (WorkflowState.FAILED, WorkflowState.RETRY_SCHEDULED),
        (WorkflowState.RETRY_SCHEDULED, WorkflowState.RECEIVED),
    ]
    force_state(db, workflow_id, WorkflowState.FAILED)
    success, error, _ = WorkflowService.retry_workflow(db, workflow_id)
    assert not success and "Max retries" in error


def test_clarification_requires_target_user_and_resumes(db, users):
    requester, _, target = users
    workflow_id = create_workflow(db, requester.id)
    force_state(db, workflow_id, WorkflowState.NEEDS_CLARIFICATION)
    WorkflowService.pause_workflow(db, workflow_id, "clarification")
    success, _, created = WorkflowService.request_clarification(
        db, workflow_id, "Which pay period?", target.id,
    )
    assert success
    assert not WorkflowService.respond_to_clarification(
        db, created["clarification_id"], "Wrong user", requester.id,
    )[0]
    success, _, response = WorkflowService.respond_to_clarification(
        db, created["clarification_id"], "July 2026", target.id,
    )
    assert success and response["response"] == "July 2026"
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    assert workflow.paused_at is None
    assert workflow.current_state == WorkflowState.CLASSIFYING
