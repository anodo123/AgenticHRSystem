"""Durable orchestration of the five core agents."""
from dataclasses import replace
from time import perf_counter
from app.observability.metrics import MetricsCollector
from typing import Any

from sqlalchemy.orm import Session

from app.agents import (
    ActionAgent,
    AgentContext,
    AgentResult,
    AnomalyInvestigationAgent,
    ComplianceAgent,
    PolicyAgent,
    SupervisorAgent,
)
from app.audit import log_event
from app.models.approval import ComplianceDecision
from app.models.workflow import IntentCategory, WorkflowState
from app.repositories.workflow_repository import WorkflowRepository
from app.services.approval_service import ApprovalService
from app.services.workflow_service import WorkflowService
from app.services.rag_service import RAGService
from app.services.hr_integration_service import HRIntegrationService


class AgentOrchestrationService:
    """Run agents in order while persisting every state and result."""

    agents = {
        "supervisor": SupervisorAgent(),
        "policy": PolicyAgent(),
        "anomaly_investigation": AnomalyInvestigationAgent(),
        "action": ActionAgent(),
        "compliance": ComplianceAgent(),
    }

    @classmethod
    def run(
        cls, db: Session, workflow_id: str
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow:
            return False, "Workflow not found", None
        if workflow.paused_at:
            return False, "Workflow is paused", None
        if workflow.current_state == WorkflowState.APPROVED:
            return cls._complete_approved(db, workflow)
        executions = WorkflowRepository.get_agent_executions(db, workflow.id)
        resume_after_clarification = (
            workflow.current_state == WorkflowState.CLASSIFYING
            and any(item.agent_name == "supervisor" for item in executions)
            and workflow.intent is not None
        )
        if workflow.current_state != WorkflowState.RECEIVED and not resume_after_clarification:
            return False, f"Cannot orchestrate workflow in state: {workflow.current_state.value}", None

        outputs = {item.agent_name: item.output_data or {} for item in executions}
        context = AgentContext(
            workflow_id=workflow.workflow_id,
            request_summary=workflow.request_summary,
            request_data=workflow.request_data or {},
            requester_id=workflow.requester_id,
            employee_id=workflow.employee_id,
            intent=workflow.intent,
            prior_outputs=outputs.copy(),
        )
        order = len(executions) + 1

        try:
            if not resume_after_clarification:
                cls._transition(db, workflow_id, WorkflowState.AUTHENTICATED, "Request authenticated")
                cls._transition(db, workflow_id, WorkflowState.AUTHORIZED, "Requester authorized")
                cls._transition(db, workflow_id, WorkflowState.CLASSIFYING, "Classifying intent")
                supervisor = cls._execute(db, workflow.id, context, "supervisor", order)
                order += 1
                outputs["supervisor"] = supervisor.output
                intent = IntentCategory(supervisor.output["intent"])
                WorkflowService.set_intent(db, workflow_id, intent)
                context = replace(context, intent=intent, prior_outputs=outputs.copy())

                if supervisor.output["needs_clarification"]:
                    cls._transition(
                        db, workflow_id, WorkflowState.NEEDS_CLARIFICATION,
                        "Supervisor requires clarification",
                    )
                    WorkflowService.pause_workflow(db, workflow_id, "Clarification required")
                    clarification = WorkflowService.request_clarification(
                        db, workflow_id, supervisor.output["clarification_question"],
                        workflow.requester_id, {"agent": "supervisor"},
                    )[2]
                    return True, None, cls._response(
                        db, workflow_id, outputs, clarification=clarification,
                    )

            request_data = context.request_data.copy()
            request_data["similar_incidents"] = RAGService.search_incidents(
                db,
                context.request_summary,
                incident_type=context.intent.value if context.intent else None,
                country=request_data.get("country"),
                business_unit=request_data.get("business_unit"),
            )
            context = replace(context, request_data=request_data)

            cls._transition(db, workflow_id, WorkflowState.CONTEXT_RETRIEVAL, "Retrieving context")
            if workflow.employee_id:
                request_data = context.request_data.copy()
                integration_context = HRIntegrationService.fetch_context(
                    db, workflow.employee_id, context.intent, request_data,
                )
                request_data["integration_context"] = integration_context
                request_data.setdefault("source_system", integration_context["domain_system"])
                context = replace(context, request_data=request_data)
            cls._transition(db, workflow_id, WorkflowState.DATA_FRESHNESS_CHECK, "Checking data freshness")
            if (
                context.request_data.get("integration_context")
                and not context.request_data["integration_context"]["fresh"]
            ):
                raise RuntimeError("HR integration data remains stale after refresh")
            cls._transition(db, workflow_id, WorkflowState.INVESTIGATING, "Investigating request")
            investigation = cls._execute(
                db, workflow.id, context, "anomaly_investigation", order,
            )
            order += 1
            outputs["anomaly_investigation"] = investigation.output
            context = replace(context, prior_outputs=outputs.copy())

            cls._transition(db, workflow_id, WorkflowState.POLICY_RETRIEVAL, "Retrieving policies")
            if not context.request_data.get("policies"):
                request_data = context.request_data.copy()
                request_data["policies"] = RAGService.search_policies(
                    db,
                    context.request_summary,
                    country=request_data.get("country"),
                    legal_entity=request_data.get("legal_entity"),
                    business_unit=request_data.get("business_unit"),
                    employee_type=request_data.get("employee_type"),
                    policy_type=request_data.get("policy_type"),
                )
                request_data["policy_retrieval_mode"] = "semantic_search"
                context = replace(context, request_data=request_data)
            policy = cls._execute(db, workflow.id, context, "policy", order)
            order += 1
            outputs["policy"] = policy.output
            context = replace(context, prior_outputs=outputs.copy())

            cls._transition(db, workflow_id, WorkflowState.ACTION_PROPOSED, "Generating action")
            action = cls._execute(db, workflow.id, context, "action", order)
            order += 1
            outputs["action"] = action.output
            context = replace(context, prior_outputs=outputs.copy())

            cls._transition(db, workflow_id, WorkflowState.COMPLIANCE_REVIEW, "Reviewing compliance")
            compliance = cls._execute(db, workflow.id, context, "compliance", order)
            outputs["compliance"] = compliance.output
            return cls._apply_decision(db, workflow, context, outputs)
        except (RuntimeError, ValueError) as exc:
            cls._mark_failed(db, workflow_id, str(exc))
            return False, str(exc), cls._response(db, workflow_id, outputs)

    @classmethod
    def _execute(
        cls,
        db: Session,
        workflow_pk: int,
        context: AgentContext,
        agent_name: str,
        order: int,
    ) -> AgentResult:
        started = perf_counter()
        result = cls.agents[agent_name].execute(context)
        duration = int((perf_counter() - started) * 1000)
        WorkflowRepository.record_agent_execution(
            db, workflow_pk, agent_name, order,
            input_data={
                "intent": context.intent.value if context.intent else None,
                "prior_agents": list(context.prior_outputs),
            },
            output_data=result.output,
            success=result.success,
            error_message=result.error,
            duration_ms=duration,
        )
        MetricsCollector.observe_agent(agent_name, result.success, duration)
        for evidence in result.evidence:
            WorkflowRepository.add_evidence(
                db, workflow_pk,
                evidence_type=evidence["evidence_type"],
                source=evidence["source"],
                data=evidence["data"],
                confidence_score=evidence.get("confidence_score"),
            )
        log_event(
            db, event_type="agent_executed", workflow_id=workflow_pk,
            entity_type="workflow", entity_id=workflow_pk, action=agent_name,
            metadata={"success": result.success, "duration_ms": duration},
        )
        if not result.success:
            raise RuntimeError(result.error or f"{agent_name} failed")
        return result

    @classmethod
    def _apply_decision(
        cls,
        db: Session,
        workflow,
        context: AgentContext,
        outputs: dict[str, dict[str, Any]],
    ) -> tuple[bool, str | None, dict[str, Any] | None]:
        compliance = outputs["compliance"]
        decision = ComplianceDecision(compliance["decision"])
        WorkflowRepository.record_compliance_decision(
            db, workflow.id, decision,
            compliance["reason_code"], compliance["explanation"],
            compliance.get("policy_violations"),
            compliance.get("authorization_issues"),
            compliance.get("required_approver_roles"),
            compliance.get("approval_expiry_hours"),
        )
        if decision == ComplianceDecision.DENY:
            cls._transition(db, workflow.workflow_id, WorkflowState.DENIED, compliance["explanation"])
        elif decision == ComplianceDecision.ESCALATE:
            cls._transition(db, workflow.workflow_id, WorkflowState.ESCALATED, compliance["explanation"])
        elif decision == ComplianceDecision.REQUIRE_APPROVAL:
            action = outputs["action"]
            success, error, approval = ApprovalService.create_request(
                db,
                workflow_id=workflow.workflow_id,
                proposed_action=action["proposed_action"],
                affected_employee_id=workflow.employee_id,
                risk_level=str(context.request_data.get("risk_level", "HIGH")).upper(),
                financial_impact=str(context.request_data.get("financial_impact", "MEDIUM")).upper(),
                policy_references=[
                    item["policy_id"] for item in outputs["policy"].get("citations", [])
                ],
                evidence_summary="Agent investigation and policy review completed",
                required_approver_roles=compliance["required_approver_roles"],
                expiry_hours=compliance["approval_expiry_hours"],
            )
            if not success:
                raise RuntimeError(error or "Could not create approval")
            return True, None, cls._response(
                db, workflow.workflow_id, outputs, approval=approval,
            )
        else:
            cls._transition(db, workflow.workflow_id, WorkflowState.EXECUTING, "Compliance allowed")
            execution = cls._execute_adapter_action(
                db, workflow, context.request_data, outputs,
            )
            if execution:
                outputs["adapter_execution"] = execution
            cls._transition(db, workflow.workflow_id, WorkflowState.VERIFYING, "Adapter execution verified")
            cls._transition(db, workflow.workflow_id, WorkflowState.COMPLETED, "Workflow completed")
            cls._remember_incident(db, workflow, context.request_data, outputs)
        return True, None, cls._response(db, workflow.workflow_id, outputs)

    @classmethod
    def _complete_approved(cls, db: Session, workflow):
        outputs = {
            item.agent_name: item.output_data or {}
            for item in WorkflowRepository.get_agent_executions(db, workflow.id)
        }
        try:
            cls._transition(db, workflow.workflow_id, WorkflowState.EXECUTING, "Approval received")
            execution = cls._execute_adapter_action(
                db, workflow, workflow.request_data or {}, outputs,
            )
            if execution:
                outputs["adapter_execution"] = execution
            cls._transition(
                db, workflow.workflow_id, WorkflowState.VERIFYING,
                "Approved adapter action verified",
            )
            cls._transition(db, workflow.workflow_id, WorkflowState.COMPLETED, "Workflow completed")
            cls._remember_incident(db, workflow, workflow.request_data or {}, outputs)
            return True, None, cls._response(db, workflow.workflow_id, outputs)
        except (RuntimeError, ValueError) as exc:
            cls._mark_failed(db, workflow.workflow_id, str(exc))
            return False, str(exc), cls._response(db, workflow.workflow_id, outputs)

    @staticmethod
    def _execute_adapter_action(
        db: Session,
        workflow,
        request_data: dict[str, Any],
        outputs: dict[str, dict[str, Any]],
    ) -> dict[str, Any] | None:
        action = outputs.get("action", {})
        if not workflow.employee_id or action.get("action_type") == "NO_ACTION":
            return None
        success, error, execution = HRIntegrationService.execute_action(
            db,
            workflow_id=workflow.workflow_id,
            workflow_pk=workflow.id,
            employee_id=workflow.employee_id,
            intent=workflow.intent,
            action=action,
            request_data=request_data,
            actor_id=workflow.requester_id,
        )
        if not success:
            raise RuntimeError(error or "Adapter action execution failed")
        return execution

    @staticmethod
    def _remember_incident(
        db: Session,
        workflow,
        request_data: dict[str, Any],
        outputs: dict[str, dict[str, Any]],
    ) -> None:
        investigation = outputs.get("anomaly_investigation", {})
        if not investigation.get("anomaly_found"):
            return
        RAGService.remember_incident(
            db,
            workflow_id=workflow.workflow_id,
            incident_type=workflow.intent.value if workflow.intent else "UNKNOWN",
            summary=workflow.request_summary,
            symptoms=investigation,
            root_cause=request_data.get("root_cause"),
            resolution=outputs.get("action", {}).get("proposed_action"),
            affected_systems=[request_data.get("source_system", "REQUEST")],
            country=request_data.get("country"),
            business_unit=request_data.get("business_unit"),
            outcome="RESOLVED",
            confidence=(investigation.get("confidence_score") or 0) / 100,
        )

    @staticmethod
    def _transition(db: Session, workflow_id: str, state: WorkflowState, reason: str) -> None:
        success, error, _ = WorkflowService.transition_workflow(
            db, workflow_id, state, reason=reason, triggered_by="orchestrator",
        )
        if not success:
            raise RuntimeError(error or f"Could not transition to {state.value}")

    @staticmethod
    def _mark_failed(db: Session, workflow_id: str, error: str) -> None:
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        if not workflow or workflow.current_state == WorkflowState.FAILED:
            return
        success, _, _ = WorkflowService.transition_workflow(
            db, workflow_id, WorkflowState.FAILED,
            reason=error, triggered_by="orchestrator",
        )
        if not success:
            WorkflowRepository.update_workflow_state(
                db, workflow_id, WorkflowState.FAILED, workflow.version,
                error_message=error,
            )

    @staticmethod
    def _response(
        db: Session,
        workflow_id: str,
        outputs: dict[str, dict[str, Any]],
        **extra,
    ) -> dict[str, Any]:
        workflow = WorkflowRepository.get_workflow(db, workflow_id)
        return {
            "workflow_id": workflow_id,
            "state": workflow.current_state.value,
            "intent": workflow.intent.value if workflow.intent else None,
            "agent_outputs": outputs,
            **extra,
        }
