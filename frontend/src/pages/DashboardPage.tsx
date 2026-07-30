import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { AuditEvent, ListResponse, Workflow } from '../types'
import { ErrorNotice, Loading, StatusBadge } from '../components/AppLayout'

export function DashboardPage() {
  const workflows = useQuery({ queryKey: ['workflows'], queryFn: () => api.get<ListResponse<Workflow>>('/workflows/').then(r => r.data), refetchInterval: 15_000 })
  const audit = useQuery({ queryKey: ['audit', 'recent'], queryFn: () => api.get<ListResponse<AuditEvent>>('/audit/', { params: { limit: 6 } }).then(r => r.data), retry: false, refetchInterval: 15_000 })
  const metrics = useQuery({ queryKey: ['metrics'], queryFn: () => api.get('/metrics').then(r => r.data), retry: false, refetchInterval: 15_000 })
  if (workflows.isLoading) return <Loading />
  if (workflows.error) return <ErrorNotice message={errorMessage(workflows.error)} />
  const items = workflows.data?.items || []
  const active = items.filter(w => !['COMPLETED', 'FAILED', 'CANCELLED', 'DENIED'].includes(w.current_state)).length
  const completed = items.filter(w => w.current_state === 'COMPLETED').length
  const success = metrics.data?.workflows?.success_rate ?? (items.length ? completed / items.length : 0)
  return <>
    <section className="hero-row"><div><p className="lead">Good to see you. Here’s what your HR operation is doing right now.</p></div><Link className="primary button" to="/workflows">+ New workflow</Link></section>
    <section className="stat-grid">
      <Stat label="Total workflows" value={metrics.data?.workflows?.total ?? workflows.data?.total ?? 0} trend="All tracked requests" />
      <Stat label="Active now" value={active} trend="Live orchestration" accent />
      <Stat label="Success rate" value={`${Math.round(success * 100)}%`} trend="Completed successfully" />
      <Stat label="Agent executions" value={Object.values(metrics.data?.agents || {}).reduce((n: number, x: any) => n + x.count, 0)} trend="Across five agents" />
    </section>
    <div className="dashboard-grid">
      <section className="panel span-2"><div className="panel-title"><div><span className="eyebrow">LIVE QUEUE</span><h2>Recent workflows</h2></div><Link to="/workflows">View all →</Link></div>
        <div className="table-wrap"><table><thead><tr><th>Workflow</th><th>Request</th><th>Intent</th><th>Status</th><th>Updated</th></tr></thead><tbody>{items.slice(0, 7).map(w => <tr key={w.workflow_id}><td><Link className="mono" to={`/workflows/${w.workflow_id}`}>{w.workflow_id}</Link></td><td className="truncate">{w.request_summary}</td><td>{w.intent || 'Classifying'}</td><td><StatusBadge value={w.current_state} /></td><td>{relative(w.updated_at)}</td></tr>)}</tbody></table>{!items.length && <div className="empty">No workflows yet. Create the first request.</div>}</div>
      </section>
      <section className="panel"><div className="panel-title"><div><span className="eyebrow">ACTIVITY</span><h2>Audit pulse</h2></div></div>
        <div className="activity">{audit.data?.items?.map(event => <div key={event.id}><span className="activity-icon">↗</span><div><strong>{event.event_type.replaceAll('_', ' ')}</strong><small>{event.action || 'System event'} · {relative(event.timestamp)}</small></div></div>) || <p className="muted">Audit access is restricted for this role.</p>}</div>
      </section>
    </div>
  </>
}
function Stat({ label, value, trend, accent = false }: { label: string; value: string | number; trend: string; accent?: boolean }) {
  return <article className={`stat-card ${accent ? 'accent' : ''}`}><span>{label}</span><strong>{value}</strong><small><i />{trend}</small></article>
}
export function relative(value: string) {
  const seconds = Math.floor((Date.now() - new Date(value).getTime()) / 1000)
  if (seconds < 60) return 'just now'; if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`; return new Date(value).toLocaleDateString()
}
