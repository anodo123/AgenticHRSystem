import { FormEvent, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useParams } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import type { ListResponse, Workflow } from '../types'
import { ErrorNotice, Loading, StatusBadge } from '../components/AppLayout'
import { relative } from './DashboardPage'

export function WorkflowsPage() {
  const [state, setState] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const query = useQuery({ queryKey: ['workflows', state], queryFn: () => api.get<ListResponse<Workflow>>('/workflows/', { params: state ? { state } : {} }).then(r => r.data) })
  return <>
    <div className="toolbar"><div className="filters"><button className={!state ? 'active' : ''} onClick={() => setState('')}>All</button>{['RECEIVED','INVESTIGATING','WAITING_FOR_APPROVAL','COMPLETED','FAILED'].map(s => <button key={s} className={state === s ? 'active' : ''} onClick={() => setState(s)}>{s.replaceAll('_',' ')}</button>)}</div><button className="primary" onClick={() => setShowCreate(true)}>+ New workflow</button></div>
    {query.isLoading ? <Loading /> : query.error ? <ErrorNotice message={errorMessage(query.error)} /> : <section className="panel"><div className="table-wrap"><table><thead><tr><th>ID</th><th>Request summary</th><th>Intent</th><th>State</th><th>Employee</th><th>Updated</th><th /></tr></thead><tbody>{query.data?.items.map(w => <tr key={w.workflow_id}><td className="mono">{w.workflow_id}</td><td className="summary-cell">{w.request_summary}</td><td>{w.intent || '—'}</td><td><StatusBadge value={w.current_state} /></td><td>{w.employee_id || '—'}</td><td>{relative(w.updated_at)}</td><td><Link to={`/workflows/${w.workflow_id}`}>Open →</Link></td></tr>)}</tbody></table></div></section>}
    {showCreate && <CreateWorkflow onClose={() => setShowCreate(false)} />}
  </>
}

function CreateWorkflow({ onClose }: { onClose: () => void }) {
  const client = useQueryClient()
  const [summary, setSummary] = useState('')
  const [employee, setEmployee] = useState('')
  const mutation = useMutation({
    mutationFn: () => api.post('/workflows/', { trigger_type: 'HR_OPERATIONS_REQUEST', employee_id: employee ? Number(employee) : null, request_summary: summary, request_data: {} }),
    onSuccess: () => { client.invalidateQueries({ queryKey: ['workflows'] }); onClose() },
  })
  return <div className="modal-backdrop" onMouseDown={onClose}><form className="modal" onSubmit={(e: FormEvent) => { e.preventDefault(); mutation.mutate() }} onMouseDown={e => e.stopPropagation()}><button type="button" className="close" onClick={onClose}>×</button><span className="eyebrow">NEW REQUEST</span><h2>Start an HR workflow</h2><label>Request summary<textarea rows={5} value={summary} onChange={e => setSummary(e.target.value)} placeholder="Describe the issue, expected result and any important context…" required /></label><label>Employee database ID (optional)<input type="number" min="1" value={employee} onChange={e => setEmployee(e.target.value)} /></label>{mutation.error && <ErrorNotice message={errorMessage(mutation.error)} />}<div className="modal-actions"><button type="button" onClick={onClose}>Cancel</button><button className="primary" disabled={mutation.isPending}>Create workflow</button></div></form></div>
}

export function WorkflowDetailPage() {
  const { workflowId = '' } = useParams()
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['workflow', workflowId], queryFn: () => api.get<Workflow>(`/workflows/${workflowId}`).then(r => r.data) })
  const action = useMutation({ mutationFn: (name: string) => api.post(`/workflows/${workflowId}/${name}`, name === 'pause' ? { reason: 'Paused from operations console' } : name === 'cancel' ? { reason: 'Cancelled from operations console' } : {}), onSuccess: () => client.invalidateQueries({ queryKey: ['workflow', workflowId] }) })
  if (query.isLoading) return <Loading />; if (query.error || !query.data) return <ErrorNotice message={errorMessage(query.error)} />
  const w = query.data
  return <><div className="detail-head"><div><Link to="/workflows">← Workflows</Link><div className="title-line"><h2>{w.workflow_id}</h2><StatusBadge value={w.current_state} /></div><p>{w.request_summary}</p></div><div className="action-row">{w.paused_at ? <button onClick={() => action.mutate('resume')}>Resume</button> : <button onClick={() => action.mutate('pause')}>Pause</button>}<button className="danger" onClick={() => action.mutate('cancel')}>Cancel</button></div></div>{action.error && <ErrorNotice message={errorMessage(action.error)} />}
    <div className="detail-grid"><section className="panel span-2"><div className="panel-title"><div><span className="eyebrow">STATE HISTORY</span><h2>Workflow timeline</h2></div></div><div className="timeline">{w.transitions?.map((t, i) => <div key={`${t.created_at}-${i}`}><span className="timeline-node">{i + 1}</span><div><strong>{t.to_state.replaceAll('_',' ')}</strong><p>{t.reason || 'State advanced'} · {t.triggered_by || 'system'}</p><small>{new Date(t.created_at).toLocaleString()}</small></div></div>)}</div></section>
      <aside className="panel facts"><span className="eyebrow">CONTEXT</span><h2>Request facts</h2><dl><dt>Trigger</dt><dd>{w.trigger_type}</dd><dt>Intent</dt><dd>{w.intent || 'Pending'}</dd><dt>Employee</dt><dd>{w.employee_id || 'Not linked'}</dd><dt>Evidence</dt><dd>{w.evidence_count || 0} records</dd><dt>Retries</dt><dd>{w.retry_count || 0} / {w.max_retries || 3}</dd><dt>Created</dt><dd>{new Date(w.created_at).toLocaleString()}</dd></dl></aside>
    </div></>
}
