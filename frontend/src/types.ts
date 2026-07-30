export type User = {
  id?: number; user_id?: number; username: string; email: string
  full_name: string; roles: string[]; is_active?: boolean
}
export type Workflow = {
  id: number; workflow_id: string; trigger_type: string; intent?: string
  current_state: string; previous_state?: string; requester_id: number
  employee_id?: number; request_summary: string; created_at: string
  updated_at: string; completed_at?: string; transitions?: Transition[]
  evidence_count?: number; retry_count?: number; max_retries?: number
  paused_at?: string; paused_reason?: string; error_message?: string
}
export type Transition = {
  from_state: string; to_state: string; reason?: string
  triggered_by?: string; created_at: string
}
export type Approval = {
  approval_id: string; workflow_id: string; proposed_action: string
  risk_level: string; financial_impact: string; required_approver_roles: string[]
  status: string; expires_at: string; current_level: number; total_levels: number
  current_required_role?: string; decision_comments?: string
}
export type ListResponse<T> = { total: number; page: number; page_size: number; items: T[] }
export type AuditEvent = {
  id: number; event_type: string; actor_id?: number; actor_role?: string
  workflow_id?: number; entity_type?: string; entity_id?: number
  action?: string; decision?: string; timestamp: string
}
