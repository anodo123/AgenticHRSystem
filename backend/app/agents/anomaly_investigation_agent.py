"""Anomaly investigation agent."""
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.agents.base import AgentContext, AgentResult, BaseAgent


class AnomalyInvestigationAgent(BaseAgent):
    name = "anomaly_investigation"
    system_prompt = (
        "You investigate HR data anomalies. Use only supplied records and validated "
        "calculations. Explain the evidence-based finding in the required structured "
        "shape; never fabricate source data or claim a mutation occurred."
    )

    def execute(self, context: AgentContext) -> AgentResult:
        observed = context.request_data.get("observed_value")
        expected = context.request_data.get("expected_value")
        integration = context.request_data.get("integration_context") or {}
        domain = integration.get("domain_system")
        domain_data = integration.get("systems", {}).get(domain, {}).get("data", {})
        field = context.request_data.get("field")
        if observed is None and field:
            source_record = domain_data.get("latest") or domain_data
            observed = source_record.get(field) if isinstance(source_record, dict) else None
        discrepancy = None
        anomaly_found = observed is not None and expected is not None and observed != expected
        try:
            if anomaly_found:
                discrepancy = float(Decimal(str(observed)) - Decimal(str(expected)))
        except (InvalidOperation, TypeError):
            discrepancy = None

        freshness = context.request_data.get("data_timestamp")
        stale = not integration.get("fresh", True)
        if freshness:
            try:
                age = datetime.utcnow() - datetime.fromisoformat(str(freshness).replace("Z", "+00:00")).replace(tzinfo=None)
                stale = age.total_seconds() > 1800
            except ValueError:
                stale = True

        confidence = 95 if anomaly_found and not stale else 65 if anomaly_found else 80
        data = {
            "anomaly_found": anomaly_found,
            "observed_value": observed,
            "expected_value": expected,
            "discrepancy": discrepancy,
            "data_stale": stale,
            "confidence_score": confidence,
            "remediation": "Correct the source record and verify downstream synchronization"
            if anomaly_found else "No corrective data change required",
            "source_system": domain or context.request_data.get("source_system", "REQUEST"),
            "adapter_context_used": bool(integration),
        }
        output = self.complete(context, data)
        for key in (
            "anomaly_found", "observed_value", "expected_value", "discrepancy",
            "data_stale", "confidence_score", "source_system", "adapter_context_used",
        ):
            output[key] = data[key]
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=output,
            evidence=[{
                "evidence_type": "anomaly_analysis",
                "source": domain or context.request_data.get("source_system", "REQUEST"),
                "data": output,
                "confidence_score": confidence,
            }],
        )
