"""Action proposal agent."""
import hashlib
import json

from app.agents.base import AgentContext, AgentResult, BaseAgent


class ActionAgent(BaseAgent):
    name = "action"
    system_prompt = (
        "You propose safe HR remediation actions from verified investigation and policy "
        "outputs. Keep the supplied idempotency key and payload exact, never execute an "
        "action, and return only the required structured output."
    )

    def execute(self, context: AgentContext) -> AgentResult:
        investigation = context.prior_outputs.get("anomaly_investigation", {})
        needs_change = bool(investigation.get("anomaly_found"))
        action_type = context.request_data.get(
            "action_type", "CORRECT_RECORD" if needs_change else "NO_ACTION"
        )
        payload = {
            "employee_id": context.employee_id,
            "field": context.request_data.get("field"),
            "before": investigation.get("observed_value"),
            "after": investigation.get("expected_value"),
        }
        digest = hashlib.sha256(
            json.dumps(
                {"workflow_id": context.workflow_id, "action": action_type, "payload": payload},
                sort_keys=True,
                default=str,
            ).encode()
        ).hexdigest()
        output = {
            "action_type": action_type,
            "proposed_action": (
                f"{action_type}: change {payload['field'] or 'affected record'} "
                f"from {payload['before']} to {payload['after']}"
                if needs_change else "No data mutation proposed"
            ),
            "payload": payload,
            "dry_run": True,
            "rollback_supported": needs_change,
            "idempotency_key": digest,
        }
        generated = self.complete(context, output)
        for key in ("action_type", "payload", "dry_run", "rollback_supported", "idempotency_key"):
            generated[key] = output[key]
        return AgentResult(self.name, True, generated)
