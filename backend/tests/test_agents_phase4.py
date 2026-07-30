"""Unit tests for the five deterministic agents."""
from app.agents import (
    ActionAgent,
    AgentContext,
    AnomalyInvestigationAgent,
    ComplianceAgent,
    PolicyAgent,
    SupervisorAgent,
)


def context(**request_data):
    return AgentContext(
        workflow_id="WF-TEST", request_summary="Payroll salary discrepancy",
        request_data=request_data, requester_id=1,
    )


def test_supervisor_classifies_and_routes():
    result = SupervisorAgent().execute(context())
    assert result.success
    assert result.output["intent"] == "PAYROLL_ANOMALY"
    assert result.output["route"] == [
        "policy", "anomaly_investigation", "action", "compliance",
    ]


def test_policy_returns_grounded_citations_and_conflict():
    result = PolicyAgent().execute(context(policies=[
        {"policy_id": "P1", "title": "Payroll", "decision": "ALLOW"},
        {"policy_id": "P2", "title": "Exception", "decision": "DENY"},
    ]))
    assert result.output["grounded"]
    assert result.output["conflict_detected"]
    assert len(result.evidence) == 2


def test_investigation_action_and_compliance_contracts():
    investigation = AnomalyInvestigationAgent().execute(
        context(observed_value=90, expected_value=100),
    )
    assert investigation.output["anomaly_found"]
    assert investigation.output["discrepancy"] == -10.0

    action_context = context(observed_value=90, expected_value=100)
    action_context = AgentContext(
        **{**action_context.__dict__, "prior_outputs": {
            "anomaly_investigation": investigation.output,
        }}
    )
    action = ActionAgent().execute(action_context)
    assert action.output["dry_run"]
    assert action.output["rollback_supported"]
    assert len(action.output["idempotency_key"]) == 64

    compliance_context = AgentContext(
        **{**action_context.__dict__, "request_data": {"risk_level": "HIGH"},
           "prior_outputs": {"action": action.output, "policy": {}}}
    )
    compliance = ComplianceAgent().execute(compliance_context)
    assert compliance.output["decision"] == "REQUIRE_APPROVAL"
    assert compliance.output["required_approver_roles"] == ["HR_ADMIN"]
