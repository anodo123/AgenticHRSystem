"""Phase 9 evaluation and observability tests."""
import json
import logging

from app.evaluation import WorkflowEvaluator
from app.models.audit import AuditLog
from app.models.workflow import TriggerType, WorkflowState
from app.observability.logging import JsonFormatter, reset_correlation_id, set_correlation_id
from app.observability.metrics import MetricsCollector
from app.observability.rate_limit import RateLimiter
from app.repositories.workflow_repository import WorkflowRepository


def test_runtime_metrics_and_prometheus_rendering():
    MetricsCollector.reset()
    MetricsCollector.observe_request("GET", "/api/v1/workflows/WF-ABC", 200, 10)
    MetricsCollector.observe_agent("policy", True, 20)
    MetricsCollector.observe_workflow("COMPLETED")
    MetricsCollector.observe_task("SUCCESS")
    snapshot = MetricsCollector.snapshot()
    assert snapshot["requests"][0]["path"] == "/api/v1/workflows/{id}"
    assert snapshot["agents"]["policy"]["success_rate"] == 1
    assert 'state="COMPLETED"' in MetricsCollector.prometheus()


def test_structured_logging_uses_correlation_context():
    token = set_correlation_id("corr-123")
    try:
        record = logging.LogRecord("test", logging.INFO, "", 0, "hello", (), None)
        payload = json.loads(JsonFormatter().format(record))
        assert payload["correlation_id"] == "corr-123"
        assert payload["message"] == "hello"
    finally:
        reset_correlation_id(token)


def test_rate_limiter_enforces_window():
    limiter = RateLimiter(1)
    assert limiter.allow("client") == (True, 0)
    allowed, retry_after = limiter.allow("client")
    assert not allowed
    assert retry_after >= 1


def test_evaluator_persists_scores_and_audit(db, users):
    workflow = WorkflowRepository.create_workflow(
        db, "WF-EVALUATE", TriggerType.EMPLOYEE_REQUEST, users[0].id, None,
        "Evaluate workflow",
    )
    workflow.current_state = WorkflowState.COMPLETED
    workflow.completed_at = workflow.updated_at
    db.commit()
    WorkflowRepository.record_agent_execution(
        db, workflow.id, "policy", 1, success=True, duration_ms=12
    )
    WorkflowRepository.add_evidence(
        db, workflow.id, "policy_reference", "POLICY", {"id": "P-1"}, 90
    )

    evaluation = WorkflowEvaluator.evaluate(db, workflow.workflow_id)
    assert evaluation.success is True
    assert evaluation.agent_success_rate == 1
    assert evaluation.evidence_count == 1
    assert 0 <= evaluation.scores["overall"] <= 1
    assert db.query(AuditLog).filter(AuditLog.event_type == "workflow_evaluated").count() == 1

    refreshed = WorkflowEvaluator.evaluate(db, workflow.workflow_id)
    assert refreshed.id == evaluation.id
