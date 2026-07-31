"""Workflow service for orchestration."""
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
import uuid

from app.models.workflow import TriggerType, WorkflowState, IntentCategory
from app.models.audit import IdempotencyRecord
from app.repositories.workflow_repository import WorkflowRepository
from app.workflows.state_machine import WorkflowStateMachine
from app.audit import log_event, log_workflow_created, log_state_transition
from app.core.config import get_settings
from app.observability.metrics import MetricsCollector

settings = get_settings()


class WorkflowService:
    """Workflow orchestration service."""

    @staticmethod
    def create_workflow(
        db: Session,
        trigger_type: TriggerType,
        requester_id: int,
        employee_id: Optional[int],
        request_summary: str,
        request_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create and initialize a new workflow."""
        # Generate unique workflow ID
        workflow_id = f"WF-{uuid.uuid4().hex[:12].upper()}"

        # Create workflow record
        workflow = WorkflowRepository.create_workflow(
            db=db,
            workflow_id=workflow_id,
            trigger_type=trigger_type,
            requester_id=requester_id,
            employee_id=employee_id,
            request_summary=request_summary,
            request_data=request_data,
        )

        # Log workflow creation
        log_workflow_created(
            db=db,
            actor_id=requester_id,
            workflow_id=workflow.id,
            intent="UNKNOWN",
        )

        return {
            "workflow_id": workflow.workflow_id,
            "id": workflow.id,
            "state": workflow.current_state.value,
            "created_at": workflow.created_at,
        }

    @staticmethod
    def transition_workflow(
        db: Session,
        workflow_id: str,
        to_state: WorkflowState,
        reason: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Transition workflow to new state."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)

        if not workflow:
            return False, "Workflow not found", None

        # Check if workflow is terminal
        if WorkflowStateMachine.is_terminal_state(workflow.current_state):
            return False, f"Cannot transition from terminal state: {workflow.current_state.value}", None
        if workflow.paused_at:
            return False, "Cannot transition a paused workflow; resume it first", None
        from_state = workflow.current_state

        # Validate transition
        is_valid, error_msg = WorkflowStateMachine.validate_transition(
            from_state,
            to_state,
        )

        if not is_valid:
            return False, error_msg, None

        # Update workflow state (with optimistic locking)
        updated_workflow = WorkflowRepository.update_workflow_state(
            db=db,
            workflow_id_str=workflow_id,
            new_state=to_state,
            version=workflow.version,
        )

        if not updated_workflow:
            return False, "Concurrent modification detected (version mismatch)", None

        # Record transition
        WorkflowRepository.record_transition(
            db=db,
            workflow_id=updated_workflow.id,
            from_state=from_state,
            to_state=to_state,
            reason=reason,
            triggered_by=triggered_by,
        )

        # Log transition
        log_state_transition(
            db=db,
            workflow_id=updated_workflow.id,
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason,
        )
        MetricsCollector.observe_workflow(to_state.value)

        return True, None, {
            "workflow_id": updated_workflow.workflow_id,
            "state": updated_workflow.current_state.value,
            "previous_state": from_state.value,
            "updated_at": updated_workflow.updated_at,
            "version": updated_workflow.version,
        }

    @staticmethod
    def get_workflow_details(db: Session, workflow_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow details with all related data."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)

        if not workflow:
            return None

        transitions = WorkflowRepository.get_workflow_transitions(db, workflow.id)
        evidence = WorkflowRepository.get_workflow_evidence(db, workflow.id)
        executions = WorkflowRepository.get_agent_executions(db, workflow.id)

        return {
            "workflow_id": workflow.workflow_id,
            "id": workflow.id,
            "trigger_type": workflow.trigger_type.value,
            "intent": workflow.intent.value if workflow.intent else None,
            "current_state": workflow.current_state.value,
            "previous_state": workflow.previous_state.value if workflow.previous_state else None,
            "requester_id": workflow.requester_id,
            "employee_id": workflow.employee_id,
            "request_summary": workflow.request_summary,
            "retry_count": workflow.retry_count,
            "max_retries": workflow.max_retries,
            "error_message": workflow.error_message,
            "paused_at": workflow.paused_at,
            "paused_reason": workflow.paused_reason,
            "created_at": workflow.created_at,
            "updated_at": workflow.updated_at,
            "completed_at": workflow.completed_at,
            "version": workflow.version,
            "transitions": [
                {
                    "from_state": t.from_state.value,
                    "to_state": t.to_state.value,
                    "reason": t.transition_reason,
                    "triggered_by": t.triggered_by,
                    "created_at": t.created_at,
                }
                for t in transitions
            ],
            "agent_executions": [
                {
                    "agent_name": execution.agent_name,
                    "execution_order": execution.execution_order,
                    "success": bool(execution.success),
                    "output": execution.output_data or {},
                    "error_message": execution.error_message,
                    "duration_ms": execution.execution_duration_ms,
                    "created_at": execution.created_at,
                }
                for execution in executions
            ],
            "evidence_count": len(evidence),
        }

    @staticmethod
    def set_intent(
        db: Session,
        workflow_id: str,
        intent: IntentCategory,
    ) -> Optional[Dict[str, Any]]:
        """Set workflow intent."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)

        if not workflow:
            return None

        workflow.intent = intent
        db.commit()
        db.refresh(workflow)

        return {
            "workflow_id": workflow.workflow_id,
            "intent": workflow.intent.value,
        }

    @staticmethod
    def pause_workflow(
        db: Session,
        workflow_id: str,
        reason: str,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Pause a workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None

        if WorkflowStateMachine.is_terminal_state(workflow.current_state):
            return False, f"Cannot pause terminal workflow in state: {workflow.current_state.value}", None

        if workflow.paused_at:
            return False, "Workflow is already paused", None

        paused_workflow = WorkflowRepository.pause_workflow(db, workflow_id, reason)

        log_event(
            db=db,
            event_type="workflow_paused",
            workflow_id=paused_workflow.id,
            entity_type="workflow",
            entity_id=paused_workflow.id,
            action="pause",
            metadata={"state": workflow.current_state.value, "reason": reason},
        )

        return True, None, {
            "workflow_id": paused_workflow.workflow_id,
            "state": paused_workflow.current_state.value,
            "paused_at": paused_workflow.paused_at,
            "paused_reason": paused_workflow.paused_reason,
        }

    @staticmethod
    def resume_workflow(
        db: Session,
        workflow_id: str,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Resume a paused workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None

        if not workflow.paused_at:
            return False, "Workflow is not paused", None

        resumed_workflow = WorkflowRepository.resume_workflow(db, workflow_id)

        log_event(
            db=db,
            event_type="workflow_resumed",
            workflow_id=resumed_workflow.id,
            entity_type="workflow",
            entity_id=resumed_workflow.id,
            action="resume",
            metadata={"resumed_state": resumed_workflow.current_state.value},
        )

        return True, None, {
            "workflow_id": resumed_workflow.workflow_id,
            "state": resumed_workflow.current_state.value,
            "paused_at": resumed_workflow.paused_at,
        }

    @staticmethod
    def cancel_workflow(
        db: Session,
        workflow_id: str,
        reason: Optional[str] = None,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Cancel a workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None

        if WorkflowStateMachine.is_terminal_state(workflow.current_state):
            return False, f"Cannot cancel terminal workflow in state: {workflow.current_state.value}", None

        is_valid, error_msg = WorkflowStateMachine.validate_transition(
            workflow.current_state, WorkflowState.CANCELLED
        )
        if not is_valid:
            return False, error_msg, None

        from_state = workflow.current_state

        cancelled_workflow = WorkflowRepository.cancel_workflow(db, workflow_id, reason)

        log_state_transition(
            db=db,
            workflow_id=cancelled_workflow.id,
            from_state=from_state.value,
            to_state=WorkflowState.CANCELLED.value,
            reason=f"Cancelled: {reason}" if reason else "Cancelled",
        )
        WorkflowRepository.record_transition(
            db, cancelled_workflow.id, from_state, WorkflowState.CANCELLED,
            reason=reason, triggered_by="user",
        )

        return True, None, {
            "workflow_id": cancelled_workflow.workflow_id,
            "state": cancelled_workflow.current_state.value,
            "completed_at": cancelled_workflow.completed_at,
        }

    @staticmethod
    def retry_workflow(
        db: Session,
        workflow_id: str,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Retry a failed workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None

        if workflow.current_state != WorkflowState.FAILED:
            return False, f"Cannot retry workflow in state: {workflow.current_state.value}", None

        retried_workflow = WorkflowRepository.retry_workflow(db, workflow_id)

        if not retried_workflow:
            return False, f"Max retries ({workflow.max_retries}) exceeded", None

        WorkflowRepository.record_transition(
            db, retried_workflow.id, WorkflowState.FAILED,
            WorkflowState.RETRY_SCHEDULED,
            reason=f"Retry {retried_workflow.retry_count}/{retried_workflow.max_retries}",
            triggered_by="user",
        )
        log_state_transition(
            db=db,
            workflow_id=retried_workflow.id,
            from_state=WorkflowState.FAILED.value,
            to_state=WorkflowState.RETRY_SCHEDULED.value,
            reason=f"Retry {retried_workflow.retry_count}/{retried_workflow.max_retries}",
        )

        success, error_msg, result = WorkflowService.transition_workflow(
            db, workflow_id, WorkflowState.RECEIVED,
            reason="Restarting persisted workflow", triggered_by="system",
        )
        if not success:
            return False, error_msg, None

        return True, None, {
            "workflow_id": retried_workflow.workflow_id,
            "state": result["state"],
            "retry_count": retried_workflow.retry_count,
            "max_retries": retried_workflow.max_retries,
        }

    @staticmethod
    def request_clarification(
        db: Session,
        workflow_id: str,
        question: str,
        requested_from_id: int,
        context: Optional[Dict[str, Any]] = None,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Request clarification during workflow."""
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None

        if workflow.current_state != WorkflowState.NEEDS_CLARIFICATION:
            return False, f"Cannot request clarification in state: {workflow.current_state.value}", None

        required_by = datetime.utcnow() + timedelta(hours=24)
        clarification = WorkflowRepository.create_clarification_request(
            db=db,
            workflow_id=workflow.id,
            question=question,
            requested_from_id=requested_from_id,
            required_by=required_by,
            context=context,
        )

        log_event(
            db=db,
            event_type="clarification_requested",
            actor_id=workflow.requester_id,
            workflow_id=workflow.id,
            action="clarification_request",
            metadata={"clarification_id": clarification.id, "question": question},
        )
        return True, None, {
            "clarification_id": clarification.id,
            "question": clarification.question,
            "required_by": clarification.required_by,
        }

    @staticmethod
    def respond_to_clarification(
        db: Session,
        clarification_id: int,
        response: str,
        responder_id: int,
    ) -> tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """Respond to a clarification request."""
        clarification = WorkflowRepository.get_clarification_request(db, clarification_id)

        if not clarification:
            return False, "Clarification request not found", None

        if clarification.responded_at:
            return False, "Clarification already responded to", None
        if clarification.requested_from_id != responder_id:
            return False, "Clarification can only be answered by the requested user", None
        if clarification.required_by <= datetime.utcnow():
            return False, "Clarification request has expired", None

        responded_clarification = WorkflowRepository.respond_to_clarification(
            db=db,
            clarification_id=clarification_id,
            response=response,
        )

        log_event(
            db=db,
            event_type="clarification_responded",
            actor_id=responder_id,
            workflow_id=clarification.workflow_id,
            action="clarification_response",
            metadata={"clarification_id": clarification_id},
        )

        workflow = WorkflowRepository.get_workflow_by_pk(db, clarification.workflow_id)
        if workflow and workflow.paused_at:
            WorkflowRepository.resume_workflow(db, workflow.workflow_id)
        if workflow and workflow.current_state == WorkflowState.NEEDS_CLARIFICATION:
            WorkflowService.transition_workflow(
                db, workflow.workflow_id, WorkflowState.CLASSIFYING,
                reason="Clarification received", triggered_by="user",
            )

        return True, None, {
            "clarification_id": responded_clarification.id,
            "response": responded_clarification.response,
            "responded_at": responded_clarification.responded_at,
        }

    @staticmethod
    def check_idempotency(
        db: Session,
        idempotency_key: str,
    ) -> Optional[Dict[str, Any]]:
        """Check if request with idempotency key already processed."""
        record = db.query(IdempotencyRecord).filter(
            IdempotencyRecord.idempotency_key == idempotency_key
        ).first()

        if record:
            return {
                "status_code": record.response_status,
                "response_body": record.response_body,
            }

        return None

    @staticmethod
    def record_idempotency(
        db: Session,
        idempotency_key: str,
        request_method: str,
        request_path: str,
        request_body: Optional[str],
        response_status: int,
        response_body: str,
    ) -> IdempotencyRecord:
        """Record idempotent request."""
        record = IdempotencyRecord(
            idempotency_key=idempotency_key,
            request_method=request_method,
            request_path=request_path,
            request_body=request_body,
            response_status=response_status,
            response_body=response_body,
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return record

