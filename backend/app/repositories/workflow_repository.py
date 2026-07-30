"""Workflow persistence and repository."""
from datetime import datetime
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.workflow import (
    Workflow,
    WorkflowState,
    WorkflowTransition,
    AgentExecution,
    WorkflowEvidence,
    ClarificationRequest,
    TriggerType,
)
from app.models.approval import ComplianceDecision, ComplianceDecisionRecord


class WorkflowRepository:
    """Repository for workflow operations."""

    @staticmethod
    def create_workflow(
        db: Session,
        workflow_id: str,
        trigger_type: TriggerType,
        requester_id: int,
        employee_id: Optional[int],
        request_summary: str,
        request_data: Optional[dict] = None,
    ) -> Workflow:
        """Create a new workflow."""
        workflow = Workflow(
            workflow_id=workflow_id,
            trigger_type=trigger_type,
            current_state=WorkflowState.RECEIVED,
            requester_id=requester_id,
            employee_id=employee_id,
            request_summary=request_summary,
            request_data=request_data,
        )
        db.add(workflow)
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def get_workflow(db: Session, workflow_id_str: str) -> Optional[Workflow]:
        """Get workflow by ID."""
        return db.query(Workflow).filter(Workflow.workflow_id == workflow_id_str).first()

    @staticmethod
    def get_workflow_by_pk(db: Session, pk: int) -> Optional[Workflow]:
        """Get workflow by primary key."""
        return db.query(Workflow).filter(Workflow.id == pk).first()

    @staticmethod
    def list_workflows(
        db: Session,
        skip: int = 0,
        limit: int = 50,
        state: Optional[WorkflowState] = None,
        requester_id: Optional[int] = None,
        employee_id: Optional[int] = None,
    ) -> tuple[int, List[Workflow]]:
        """List workflows with filtering."""
        query = db.query(Workflow)

        if state:
            query = query.filter(Workflow.current_state == state)

        if requester_id:
            query = query.filter(Workflow.requester_id == requester_id)

        if employee_id:
            query = query.filter(Workflow.employee_id == employee_id)

        total = query.count()
        workflows = query.order_by(desc(Workflow.created_at)).offset(skip).limit(limit).all()

        return total, workflows

    @staticmethod
    def update_workflow_state(
        db: Session,
        workflow_id_str: str,
        new_state: WorkflowState,
        version: int,
        error_message: Optional[str] = None,
    ) -> Optional[Workflow]:
        """Update workflow state with optimistic locking."""
        workflow = db.query(Workflow).filter(
            Workflow.workflow_id == workflow_id_str,
            Workflow.version == version,
        ).first()

        if not workflow:
            return None

        workflow.previous_state = workflow.current_state
        workflow.current_state = new_state
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()

        if error_message:
            workflow.error_message = error_message
        if new_state in {
            WorkflowState.COMPLETED,
            WorkflowState.DENIED,
            WorkflowState.ESCALATED,
            WorkflowState.REJECTED,
            WorkflowState.CANCELLED,
            WorkflowState.EXPIRED,
        }:
            workflow.completed_at = datetime.utcnow()

        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def record_transition(
        db: Session,
        workflow_id: int,
        from_state: WorkflowState,
        to_state: WorkflowState,
        reason: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> WorkflowTransition:
        """Record state transition."""
        transition = WorkflowTransition(
            workflow_id=workflow_id,
            from_state=from_state,
            to_state=to_state,
            transition_reason=reason,
            triggered_by=triggered_by,
        )
        db.add(transition)
        db.commit()
        return transition

    @staticmethod
    def record_agent_execution(
        db: Session,
        workflow_id: int,
        agent_name: str,
        execution_order: int,
        input_data: Optional[dict] = None,
        output_data: Optional[dict] = None,
        success: bool = True,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
    ) -> AgentExecution:
        """Record agent execution."""
        execution = AgentExecution(
            workflow_id=workflow_id,
            agent_name=agent_name,
            execution_order=execution_order,
            input_data=input_data,
            output_data=output_data,
            success=1 if success else 0,
            error_message=error_message,
            execution_duration_ms=duration_ms,
        )
        db.add(execution)
        db.commit()
        return execution

    @staticmethod
    def add_evidence(
        db: Session,
        workflow_id: int,
        evidence_type: str,
        source: str,
        data: dict,
        confidence_score: Optional[int] = None,
    ) -> WorkflowEvidence:
        """Add evidence to workflow."""
        evidence = WorkflowEvidence(
            workflow_id=workflow_id,
            evidence_type=evidence_type,
            source=source,
            data=data,
            confidence_score=confidence_score,
        )
        db.add(evidence)
        db.commit()
        return evidence

    @staticmethod
    def get_workflow_evidence(db: Session, workflow_id: int) -> List[WorkflowEvidence]:
        """Get all evidence for workflow."""
        return db.query(WorkflowEvidence).filter(
            WorkflowEvidence.workflow_id == workflow_id
        ).order_by(WorkflowEvidence.created_at).all()

    @staticmethod
    def get_workflow_transitions(db: Session, workflow_id: int) -> List[WorkflowTransition]:
        """Get all transitions for workflow."""
        return db.query(WorkflowTransition).filter(
            WorkflowTransition.workflow_id == workflow_id
        ).order_by(WorkflowTransition.created_at).all()

    @staticmethod
    def get_agent_executions(db: Session, workflow_id: int) -> List[AgentExecution]:
        """Get persisted agent executions in execution order."""
        return db.query(AgentExecution).filter(
            AgentExecution.workflow_id == workflow_id
        ).order_by(AgentExecution.execution_order, AgentExecution.created_at).all()

    @staticmethod
    def record_compliance_decision(
        db: Session,
        workflow_id: int,
        decision: ComplianceDecision,
        reason_code: str,
        explanation: str,
        policy_violations: Optional[list] = None,
        authorization_issues: Optional[list] = None,
        required_approver_roles: Optional[list] = None,
        approval_expiry_hours: Optional[int] = None,
    ) -> ComplianceDecisionRecord:
        """Persist the compliance agent's final decision."""
        record = ComplianceDecisionRecord(
            workflow_id=workflow_id,
            decision=decision,
            reason_code=reason_code,
            explanation=explanation,
            policy_violations=policy_violations,
            authorization_issues=authorization_issues,
            required_approver_roles=required_approver_roles,
            approval_expiry_hours=approval_expiry_hours,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

    @staticmethod
    def increment_retry_count(
        db: Session,
        workflow_id_str: str,
        max_retries: int,
    ) -> Optional[Workflow]:
        """Increment retry count and check if max retries exceeded."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id_str)
        if not workflow:
            return None

        workflow.retry_count += 1
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def mark_completed(
        db: Session,
        workflow_id_str: str,
    ) -> Optional[Workflow]:
        """Mark workflow as completed."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id_str)
        if not workflow:
            return None

        workflow.current_state = WorkflowState.COMPLETED
        workflow.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def pause_workflow(
        db: Session,
        workflow_id_str: str,
        reason: str,
    ) -> Optional[Workflow]:
        """Pause a workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id_str)
        if not workflow:
            return None

        workflow.paused_at = datetime.utcnow()
        workflow.paused_reason = reason
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def resume_workflow(
        db: Session,
        workflow_id_str: str,
    ) -> Optional[Workflow]:
        """Resume a paused workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id_str)
        if not workflow:
            return None

        workflow.paused_at = None
        workflow.paused_reason = None
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def cancel_workflow(
        db: Session,
        workflow_id_str: str,
        reason: Optional[str] = None,
    ) -> Optional[Workflow]:
        """Cancel a workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id_str)
        if not workflow:
            return None

        previous_state = workflow.current_state
        workflow.previous_state = previous_state
        workflow.current_state = WorkflowState.CANCELLED
        workflow.version += 1
        if reason:
            workflow.error_message = reason
        workflow.completed_at = datetime.utcnow()
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def retry_workflow(
        db: Session,
        workflow_id_str: str,
    ) -> Optional[Workflow]:
        """Retry a failed workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id_str)
        if not workflow:
            return None

        if workflow.retry_count >= workflow.max_retries:
            return None

        workflow.retry_count += 1
        workflow.current_state = WorkflowState.RETRY_SCHEDULED
        workflow.previous_state = WorkflowState.FAILED
        workflow.error_message = None
        workflow.version += 1
        workflow.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(workflow)
        return workflow

    @staticmethod
    def create_clarification_request(
        db: Session,
        workflow_id: int,
        question: str,
        requested_from_id: int,
        required_by: datetime,
        context: Optional[dict] = None,
    ) -> ClarificationRequest:
        """Create a clarification request."""
        clarification = ClarificationRequest(
            workflow_id=workflow_id,
            question=question,
            requested_from_id=requested_from_id,
            context=context,
            required_by=required_by,
        )
        db.add(clarification)
        db.commit()
        db.refresh(clarification)
        return clarification

    @staticmethod
    def respond_to_clarification(
        db: Session,
        clarification_id: int,
        response: str,
    ) -> Optional[ClarificationRequest]:
        """Respond to a clarification request."""
        clarification = db.query(ClarificationRequest).filter(
            ClarificationRequest.id == clarification_id
        ).first()

        if not clarification:
            return None

        clarification.response = response
        clarification.responded_at = datetime.utcnow()
        db.commit()
        db.refresh(clarification)
        return clarification

    @staticmethod
    def get_clarification_requests(db: Session, workflow_id: int) -> List[ClarificationRequest]:
        """Get all clarification requests for a workflow."""
        return db.query(ClarificationRequest).filter(
            ClarificationRequest.workflow_id == workflow_id
        ).order_by(ClarificationRequest.created_at).all()

    @staticmethod
    def get_clarification_request(
        db: Session,
        clarification_id: int,
    ) -> Optional[ClarificationRequest]:
        """Get a clarification request by primary key."""
        return db.query(ClarificationRequest).filter(
            ClarificationRequest.id == clarification_id
        ).first()

    @staticmethod
    def check_expired_workflows(db: Session) -> List[Workflow]:
        """Check for expired workflows and mark them as expired."""
        expired_workflows = db.query(Workflow).filter(
            Workflow.expires_at <= datetime.utcnow(),
            Workflow.current_state != WorkflowState.EXPIRED,
            Workflow.current_state != WorkflowState.COMPLETED,
        ).all()

        for workflow in expired_workflows:
            workflow.current_state = WorkflowState.EXPIRED
            workflow.error_message = "Workflow expired"
            workflow.completed_at = datetime.utcnow()

        if expired_workflows:
            db.commit()

        return expired_workflows
