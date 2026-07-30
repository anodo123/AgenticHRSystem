"""Database-backed operational metrics."""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.approval import ApprovalRequest, ComplianceDecisionRecord
from app.models.evaluation import WorkflowEvaluation
from app.models.task import TaskRun
from app.models.workflow import AgentExecution, Workflow
from app.observability.metrics import MetricsCollector


class ObservabilityService:
    @staticmethod
    def snapshot(db: Session) -> dict:
        def grouped(model, column):
            return {str(key.value if hasattr(key, "value") else key): count
                    for key, count in db.query(column, func.count(model.id)).group_by(column).all()}

        workflow_total = db.query(Workflow).count()
        successful = db.query(Workflow).filter(Workflow.current_state == "COMPLETED").count()
        agent_rows = db.query(
            AgentExecution.agent_name, func.count(AgentExecution.id),
            func.sum(AgentExecution.success), func.avg(AgentExecution.execution_duration_ms),
        ).group_by(AgentExecution.agent_name).all()
        evaluation_scores = [
            (item.scores or {}).get("overall", 0)
            for item in db.query(WorkflowEvaluation).all()
        ]
        return {
            "runtime": MetricsCollector.snapshot(),
            "workflows": {
                "total": workflow_total,
                "by_state": grouped(Workflow, Workflow.current_state),
                "success_rate": successful / workflow_total if workflow_total else 0.0,
            },
            "agents": {
                name: {"count": count, "success_rate": (success or 0) / count,
                       "average_duration_ms": float(duration or 0)}
                for name, count, success, duration in agent_rows
            },
            "compliance": grouped(ComplianceDecisionRecord, ComplianceDecisionRecord.decision),
            "approvals": grouped(ApprovalRequest, ApprovalRequest.status),
            "task_runs": grouped(TaskRun, TaskRun.status),
            "evaluations": {
                "total": len(evaluation_scores),
                "average_overall_score": (
                    sum(evaluation_scores) / len(evaluation_scores)
                    if evaluation_scores else 0.0
                ),
            },
        }
