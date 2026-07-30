"""Policy Agent integration with persisted Phase 5 RAG."""
from datetime import datetime, timedelta

from app.models.rag import Incident
from app.models.workflow import TriggerType
from app.services.agent_orchestration import AgentOrchestrationService
from app.services.rag_service import RAGService
from app.services.workflow_service import WorkflowService


def test_orchestration_retrieves_policy_and_remembers_incident(db, users):
    RAGService.ingest_policy(
        db,
        policy_id="PAY-INDIA-1",
        title="Payroll Correction Policy",
        policy_type="PAYROLL",
        country="IN",
        legal_entity="ACME",
        content="Payroll salary corrections require verification and manager approval.",
        effective_from=datetime.utcnow() - timedelta(days=1),
    )
    workflow_id = WorkflowService.create_workflow(
        db,
        TriggerType.EMPLOYEE_REQUEST,
        users[0].id,
        None,
        "Payroll salary correction requires verification",
        {
            "observed_value": 90,
            "expected_value": 100,
            "risk_level": "LOW",
            "country": "IN",
            "legal_entity": "ACME",
            "policy_type": "PAYROLL",
        },
    )["workflow_id"]
    success, error, result = AgentOrchestrationService.run(db, workflow_id)
    assert success, error
    assert result["state"] == "COMPLETED"
    policy = result["agent_outputs"]["policy"]
    assert policy["grounded"]
    assert policy["retrieval_mode"] == "semantic_search"
    assert policy["citations"][0]["policy_id"] == "PAY-INDIA-1"
    assert db.query(Incident).filter(Incident.workflow_id == workflow_id).count() == 1
