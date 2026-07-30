"""LLM-backed policy agent with a grounded pre-RAG contract."""
from app.agents.base import AgentContext, AgentResult, BaseAgent


class PolicyAgent(BaseAgent):
    name = "policy"
    system_prompt = (
        "You are an HR policy-grounding agent. Base every conclusion exclusively on "
        "the retrieved policy citations supplied in context. Preserve citation IDs, "
        "surface conflicts, and return only the required structured output."
    )

    def execute(self, context: AgentContext) -> AgentResult:
        policies = context.request_data.get("policies") or []
        citations = [
            {
                "policy_id": item.get("policy_id", f"POL-{index + 1}"),
                "title": item.get("title", "Provided policy"),
                "section": item.get("section"),
                "excerpt": item.get("excerpt"),
                "chunk_id": item.get("chunk_id"),
                "version": item.get("version"),
                "score": item.get("score"),
            }
            for index, item in enumerate(policies)
            if isinstance(item, dict)
        ]
        conflict = len({
            item.get("decision") for item in policies
            if isinstance(item, dict) and item.get("decision")
        }) > 1
        output = self.complete(context, {
            "grounded": bool(citations),
            "citations": citations,
            "conflict_detected": conflict,
            "retrieval_mode": context.request_data.get(
                "policy_retrieval_mode",
                "provided_context" if citations else "no_match",
            ),
        })
        output["citations"] = citations
        output["grounded"] = bool(citations)
        output["conflict_detected"] = conflict
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=output,
            evidence=[
                {
                    "evidence_type": "policy_reference",
                    "source": "POLICY",
                    "data": citation,
                    "confidence_score": 100,
                }
                for citation in output["citations"]
            ],
        )
