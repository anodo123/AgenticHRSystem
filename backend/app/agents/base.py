"""Shared contract for LLM-backed workflow agents."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.workflow import IntentCategory
from app.llm import OpenAIResponsesClient


@dataclass(frozen=True)
class AgentContext:
    """Normalized workflow context passed between agents."""

    workflow_id: str
    request_summary: str
    request_data: dict[str, Any] = field(default_factory=dict)
    requester_id: int = 0
    employee_id: int | None = None
    intent: IntentCategory | None = None
    prior_outputs: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class AgentResult:
    """Serializable outcome returned by every agent."""

    agent_name: str
    success: bool
    output: dict[str, Any]
    evidence: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None


class BaseAgent(ABC):
    """Common interface implemented by all five agents."""

    name: str
    system_prompt: str
    llm_client = OpenAIResponsesClient()

    def complete(
        self,
        context: AgentContext,
        validated_facts: dict[str, Any],
    ) -> dict[str, Any]:
        return self.llm_client.generate(
            agent_name=self.name,
            system_prompt=self.system_prompt,
            context={
                "workflow_id": context.workflow_id,
                "request_summary": context.request_summary,
                "request_data": context.request_data,
                "requester_id": context.requester_id,
                "employee_id": context.employee_id,
                "intent": context.intent.value if context.intent else None,
                "prior_outputs": context.prior_outputs,
            },
            candidate=validated_facts,
            schema=self._schema(validated_facts),
        )

    @classmethod
    def _schema(cls, value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return {
                "type": "object",
                "properties": {key: cls._schema(item) for key, item in value.items()},
                "required": list(value),
                "additionalProperties": False,
            }
        if isinstance(value, list):
            return {
                "type": "array",
                # Strict structured outputs reject an unconstrained `items: {}`.
                # Empty deterministic lists are replaced by the agent after the
                # model call, so a string item schema keeps the request valid.
                "items": cls._schema(value[0]) if value else {"type": "string"},
            }
        if value is None:
            return {"type": ["string", "null"]}
        if isinstance(value, bool):
            return {"type": "boolean"}
        if isinstance(value, int):
            return {"type": "integer"}
        if isinstance(value, float):
            return {"type": "number"}
        return {"type": "string"}

    @abstractmethod
    def execute(self, context: AgentContext) -> AgentResult:
        """Execute deterministically against normalized context."""
