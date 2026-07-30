"""Compliance agent and deterministic decision rules."""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.approval import ComplianceDecision


class ComplianceAgent(BaseAgent):
    name = "compliance"
    system_prompt = (
        "You are the final HR compliance gate. Review authorization, policy evidence, "
        "risk and proposed action. Choose only ALLOW, REQUIRE_APPROVAL, DENY, or ESCALATE. "
        "Never weaken required approvals and return only the structured decision."
    )

    def execute(self, context: AgentContext) -> AgentResult:
        action = context.prior_outputs.get("action", {})
        policy = context.prior_outputs.get("policy", {})
        override = context.request_data.get("compliance_decision")

        if override:
            try:
                decision = ComplianceDecision(str(override).upper())
            except ValueError:
                return AgentResult(
                    self.name, False, {}, error=f"Invalid compliance decision: {override}"
                )
        elif policy.get("conflict_detected"):
            decision = ComplianceDecision.ESCALATE
        elif context.request_data.get("policy_violation"):
            decision = ComplianceDecision.DENY
        elif action.get("action_type") == "NO_ACTION":
            decision = ComplianceDecision.ALLOW
        elif str(context.request_data.get("risk_level", "MEDIUM")).upper() in {"HIGH", "CRITICAL"}:
            decision = ComplianceDecision.REQUIRE_APPROVAL
        else:
            decision = ComplianceDecision.ALLOW

        required_roles = context.request_data.get("required_approver_roles") or ["HR_ADMIN"]
        output = {
            "decision": decision.value,
            "reason_code": f"DETERMINISTIC_{decision.value}",
            "explanation": f"Policy-constrained compliance result: {decision.value}",
            "required_approver_roles": required_roles if decision == ComplianceDecision.REQUIRE_APPROVAL else [],
            "approval_expiry_hours": context.request_data.get("approval_expiry_hours", 48),
            "authorization_issues": context.request_data.get("authorization_issues", []),
            "policy_violations": context.request_data.get("policy_violations", []),
        }
        generated = self.complete(context, output)
        # The model explains the gate; deterministic policy constraints remain authoritative.
        for key in (
            "decision", "required_approver_roles", "approval_expiry_hours",
            "authorization_issues", "policy_violations",
        ):
            generated[key] = output[key]
        return AgentResult(self.name, True, generated)
