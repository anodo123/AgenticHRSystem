"""Integration tests for durable five-agent orchestration."""
from app.models.audit import AuditLog
from app.models.workflow import TriggerType, WorkflowState
from app.repositories.workflow_repository import WorkflowRepository
from app.services.agent_orchestration import AgentOrchestrationService
from app.services.approval_service import ApprovalService
from app.services.workflow_service import WorkflowService


def create(db, requester_id, data, summary="Payroll discrepancy"):
    return WorkflowService.create_workflow(
        db, TriggerType.EMPLOYEE_REQUEST, requester_id, None, summary, data,
    )["workflow_id"]


def test_allow_path_runs_all_agents_and_completes(db, users):
    workflow_id = create(db, users[0].id, {
        "observed_value": 90,
        "expected_value": 100,
        "risk_level": "LOW",
        "policies": [{"policy_id": "PAY-1", "title": "Payroll corrections"}],
    })
    success, error, result = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert result["state"] == "COMPLETED"
    assert result["intent"] == "PAYROLL_ANOMALY"
    workflow = WorkflowRepository.get_workflow(db, workflow_id)
    executions = WorkflowRepository.get_agent_executions(db, workflow.id)
    assert [item.agent_name for item in executions] == [
        "supervisor", "anomaly_investigation", "policy", "action", "compliance",
    ]
    assert len(WorkflowRepository.get_workflow_evidence(db, workflow.id)) == 2
    assert db.query(AuditLog).filter(AuditLog.event_type == "agent_executed").count() == 5


def test_approval_path_pauses_then_continues_after_decision(db, users):
    requester, approver, _ = users
    workflow_id = create(db, requester.id, {
        "observed_value": 90, "expected_value": 100, "risk_level": "HIGH",
    })
    success, error, result = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert result["state"] == "WAITING_FOR_APPROVAL"
    assert result["approval"]["status"] == "PENDING"

    success, error, _ = ApprovalService.decide(
        db, approval_id=result["approval"]["approval_id"],
        approver=approver, approve=True,
    )
    assert success, error
    success, error, continued = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert continued["state"] == "COMPLETED"


def test_deny_and_clarification_paths_stop_safely(db, users):
    requester = users[0]
    denied_id = create(db, requester.id, {
        "observed_value": 1, "expected_value": 2,
        "compliance_decision": "DENY",
    })
    assert AgentOrchestrationService.run(db, denied_id)[2]["state"] == "DENIED"

    clarification_id = create(
        db, requester.id, {"needs_clarification": True}, summary="Help",
    )
    success, error, result = AgentOrchestrationService.run(db, clarification_id)
    assert success, error
    assert result["state"] == "NEEDS_CLARIFICATION"
    workflow = WorkflowRepository.get_workflow(db, clarification_id)
    assert workflow.paused_at is not None
    assert result["clarification"]["question"]
    assert [item.agent_name for item in WorkflowRepository.get_agent_executions(db, workflow.id)] == [
        "supervisor"
    ]
    clarification = WorkflowRepository.get_clarification_requests(db, workflow.id)[0]
    success, error, _ = WorkflowService.respond_to_clarification(
        db, clarification.id, "Payroll adjustment for July", requester.id,
    )
    assert success, error
    success, error, continued = AgentOrchestrationService.run(db, clarification_id)
    assert success, error
    assert continued["state"] == "COMPLETED"
    assert len(WorkflowRepository.get_agent_executions(db, workflow.id)) == 5


def test_agent_failure_is_persisted_as_failed_workflow(db, users):
    workflow_id = create(db, users[0].id, {
        "observed_value": 1, "expected_value": 2,
        "compliance_decision": "NOT_A_DECISION",
    })
    success, error, result = AgentOrchestrationService.run(db, workflow_id)
    assert not success
    assert "Invalid compliance decision" in error
    assert result["state"] == WorkflowState.FAILED.value
