"""Supervisor agent for intent classification and routing."""
from app.agents.base import AgentContext, AgentResult, BaseAgent
from app.models.workflow import IntentCategory


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    system_prompt = (
        "You are the supervisor for a governed HR operations workflow. Classify the "
        "request, decide whether clarification is essential, and return only the "
        "required structured output. Preserve enum values and do not invent employee facts."
    )

    KEYWORDS = {
        IntentCategory.PAYROLL_ANOMALY: ("payroll", "salary", "bonus", "deduction", "payslip"),
        IntentCategory.ATTENDANCE_ANOMALY: ("attendance", "clock", "timesheet", "overtime"),
        IntentCategory.LEAVE_ANOMALY: ("leave", "vacation", "pto", "absence"),
        IntentCategory.BENEFITS_ANOMALY: ("benefit", "insurance", "coverage"),
        IntentCategory.LMS_ANOMALY: ("training", "course", "lms", "certification"),
        IntentCategory.DATA_CORRECTION: ("correct", "update", "change", "fix"),
        IntentCategory.POLICY_QUERY: ("policy", "eligible", "eligibility", "rule"),
    }

    def execute(self, context: AgentContext) -> AgentResult:
        explicit = context.request_data.get("intent")
        intent = None
        if explicit:
            try:
                intent = IntentCategory(str(explicit).upper())
            except ValueError:
                intent = IntentCategory.UNKNOWN

        summary = context.request_summary.lower()
        if intent is None:
            for category, keywords in self.KEYWORDS.items():
                if any(keyword in summary for keyword in keywords):
                    intent = category
                    break
        intent = intent or IntentCategory.GENERAL_HR_REQUEST

        needs_clarification = (
            intent == IntentCategory.UNKNOWN
            or len(context.request_summary.strip()) < 8
            or bool(context.request_data.get("needs_clarification"))
        )
        route = ["policy", "anomaly_investigation", "action", "compliance"]
        output = self.complete(context, {
            "intent": intent.value,
            "needs_clarification": needs_clarification,
            "clarification_question": (
                "Please provide the affected HR process, employee, and expected outcome."
                if needs_clarification else None
            ),
            "route": route,
        })
        try:
            IntentCategory(output["intent"])
        except (KeyError, ValueError) as exc:
            raise ValueError("LLM returned an invalid workflow intent") from exc
        output["route"] = route
        return AgentResult(
            agent_name=self.name,
            success=True,
            output=output,
        )
