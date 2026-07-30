"""Deterministic, persisted workflow quality evaluation."""
from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.approval import ApprovalRequest, ComplianceDecisionRecord
from app.models.workflow import AgentExecution, Workflow, WorkflowEvidence, WorkflowState
from app.repositories.evaluation_repository import EvaluationRepository
from app.audit import log_event


class WorkflowEvaluator:
    TERMINAL_STATES = {
        WorkflowState.COMPLETED, WorkflowState.DENIED, WorkflowState.ESCALATED,
        WorkflowState.REJECTED, WorkflowState.FAILED, WorkflowState.CANCELLED,
        WorkflowState.EXPIRED,
    }

    @classmethod
    def evaluate(cls, db: Session, workflow_id: str):
        workflow = db.query(Workflow).filter(Workflow.workflow_id == workflow_id).first()
        if not workflow:
            return None

        executions = db.query(AgentExecution).filter(
            AgentExecution.workflow_id == workflow.id
        ).all()
        evidence_count = db.query(WorkflowEvidence).filter(
            WorkflowEvidence.workflow_id == workflow.id
        ).count()
        compliance = db.query(ComplianceDecisionRecord).filter(
            ComplianceDecisionRecord.workflow_id == workflow.id
        ).order_by(ComplianceDecisionRecord.evaluated_at.desc()).first()
        approval_required = db.query(ApprovalRequest).filter(
            ApprovalRequest.workflow_id == workflow.id
        ).count() > 0

        agent_rate = (
            sum(bool(item.success) for item in executions) / len(executions)
            if executions else 0.0
        )
        lifecycle_score = 1.0 if workflow.current_state == WorkflowState.COMPLETED else (
            0.5 if workflow.current_state not in cls.TERMINAL_STATES else 0.0
        )
        compliance_score = 1.0 if compliance and compliance.decision.value == "ALLOW" else (
            0.75 if compliance and compliance.decision.value == "REQUIRE_APPROVAL" else 0.0
        )
        evidence_score = min(evidence_count / 3, 1.0)
        scores = {
            "lifecycle": round(lifecycle_score, 3),
            "agent_performance": round(agent_rate, 3),
            "compliance": round(compliance_score, 3),
            "evidence": round(evidence_score, 3),
        }
        scores["overall"] = round(sum(scores.values()) / len(scores), 3)
        end = workflow.completed_at or workflow.updated_at or datetime.utcnow()
        duration_ms = max(0, int((end - workflow.created_at).total_seconds() * 1000))

        evaluation = EvaluationRepository.upsert(db, workflow.id, {
            "evaluation_id": (
                EvaluationRepository.get_by_workflow(db, workflow.id).evaluation_id
                if EvaluationRepository.get_by_workflow(db, workflow.id)
                else f"EVAL-{uuid4().hex[:16].upper()}"
            ),
            "success": workflow.current_state == WorkflowState.COMPLETED,
            "final_state": workflow.current_state.value,
            "duration_ms": duration_ms,
            "agent_success_rate": agent_rate,
            "compliance_decision": compliance.decision.value if compliance else None,
            "approval_required": approval_required,
            "evidence_count": evidence_count,
            "retry_count": workflow.retry_count,
            "scores": scores,
            "evaluated_at": datetime.utcnow(),
        })
        log_event(
            db,
            event_type="workflow_evaluated",
            workflow_id=workflow.id,
            entity_type="workflow_evaluation",
            entity_id=evaluation.id,
            action="evaluate",
            metadata={"success": evaluation.success, "scores": evaluation.scores},
        )
        return evaluation

    @classmethod
    def refresh_terminal(cls, db: Session) -> list:
        workflows = db.query(Workflow).filter(Workflow.current_state.in_(cls.TERMINAL_STATES)).all()
        return [cls.evaluate(db, workflow.workflow_id) for workflow in workflows]
