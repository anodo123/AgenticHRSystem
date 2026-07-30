"""Workflow state machine definition and transitions."""
from typing import Set, Optional
from app.models.workflow import WorkflowState


class WorkflowStateMachine:
    """Deterministic workflow state machine."""

    # Define all valid transitions
    VALID_TRANSITIONS = {
        WorkflowState.RECEIVED: {
            WorkflowState.AUTHENTICATED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.AUTHENTICATED: {
            WorkflowState.AUTHORIZED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.AUTHORIZED: {
            WorkflowState.CLASSIFYING,
            WorkflowState.NEEDS_CLARIFICATION,
            WorkflowState.CANCELLED,
        },
        WorkflowState.CLASSIFYING: {
            WorkflowState.CONTEXT_RETRIEVAL,
            WorkflowState.NEEDS_CLARIFICATION,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.NEEDS_CLARIFICATION: {
            WorkflowState.CLASSIFYING,
            WorkflowState.CANCELLED,
        },
        WorkflowState.CONTEXT_RETRIEVAL: {
            WorkflowState.DATA_FRESHNESS_CHECK,
            WorkflowState.CANCELLED,
        },
        WorkflowState.DATA_FRESHNESS_CHECK: {
            WorkflowState.INVESTIGATING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.INVESTIGATING: {
            WorkflowState.POLICY_RETRIEVAL,
            WorkflowState.ACTION_PROPOSED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.POLICY_RETRIEVAL: {
            WorkflowState.ACTION_PROPOSED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.ACTION_PROPOSED: {
            WorkflowState.COMPLIANCE_REVIEW,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.COMPLIANCE_REVIEW: {
            WorkflowState.WAITING_FOR_APPROVAL,
            WorkflowState.EXECUTING,
            WorkflowState.DENIED,
            WorkflowState.ESCALATED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.WAITING_FOR_APPROVAL: {
            WorkflowState.APPROVED,
            WorkflowState.REJECTED,
            WorkflowState.EXPIRED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.APPROVED: {
            WorkflowState.EXECUTING,
            WorkflowState.CANCELLED,
        },
        WorkflowState.EXECUTING: {
            WorkflowState.VERIFYING,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.VERIFYING: {
            WorkflowState.COMPLETED,
            WorkflowState.FAILED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.COMPLETED: set(),  # Terminal state
        WorkflowState.DENIED: set(),  # Terminal state
        WorkflowState.ESCALATED: set(),  # Terminal state
        WorkflowState.FAILED: {
            WorkflowState.RETRY_SCHEDULED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.RETRY_SCHEDULED: {
            WorkflowState.RECEIVED,
            WorkflowState.CANCELLED,
        },
        WorkflowState.CANCELLED: set(),  # Terminal state
        WorkflowState.EXPIRED: set(),  # Terminal state
        WorkflowState.REJECTED: set(),  # Terminal state
    }

    # Terminal states
    TERMINAL_STATES = {
        WorkflowState.COMPLETED,
        WorkflowState.DENIED,
        WorkflowState.ESCALATED,
        WorkflowState.CANCELLED,
        WorkflowState.EXPIRED,
        WorkflowState.REJECTED,
    }

    @classmethod
    def is_valid_transition(
        cls,
        from_state: WorkflowState,
        to_state: WorkflowState,
    ) -> bool:
        """Check if a transition is valid."""
        return to_state in cls.VALID_TRANSITIONS.get(from_state, set())

    @classmethod
    def is_terminal_state(cls, state: WorkflowState) -> bool:
        """Check if state is terminal."""
        return state in cls.TERMINAL_STATES

    @classmethod
    def get_valid_next_states(cls, current_state: WorkflowState) -> Set[WorkflowState]:
        """Get all valid next states from current state."""
        return cls.VALID_TRANSITIONS.get(current_state, set()).copy()

    @classmethod
    def validate_transition(
        cls,
        from_state: WorkflowState,
        to_state: WorkflowState,
    ) -> tuple[bool, Optional[str]]:
        """Validate transition and return (is_valid, error_message)."""
        if from_state == to_state:
            return False, "Cannot transition to same state"
        
        if not cls.is_valid_transition(from_state, to_state):
            valid_states = cls.get_valid_next_states(from_state)
            states_str = ", ".join(s.value for s in valid_states) if valid_states else "none"
            return False, f"Invalid transition from {from_state.value} to {to_state.value}. Valid states: {states_str}"
        
        return True, None
