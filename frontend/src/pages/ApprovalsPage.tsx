import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorMessage } from '../api/client'
import type { Approval, ListResponse } from '../types'
import { ErrorNotice, Loading, StatusBadge } from '../components/AppLayout'

export function ApprovalsPage() {
  const [status, setStatus] = useState('PENDING'); const [selected, setSelected] = useState<Approval | null>(null)
  const query = useQuery({ queryKey: ['approvals', status], queryFn: () => api.get<ListResponse<Approval>>('/approvals/', { params: { approval_status: status } }).then(r => r.data) })
  return <><div className="toolbar"><div className="filters">{['PENDING','APPROVED','REJECTED','EXPIRED'].map(s => <button className={status === s ? 'active' : ''} onClick={() => setStatus(s)} key={s}>{s}</button>)}</div></div>{query.isLoading ? <Loading /> : query.error ? <ErrorNotice message={errorMessage(query.error)} /> : <div className="approval-grid">{query.data?.items.map(item => <article className="approval-card" key={item.approval_id} onClick={() => setSelected(item)}><div><StatusBadge value={item.status} /><span className={`risk risk-${item.risk_level.toLowerCase()}`}>{item.risk_level} RISK</span></div><h3>{item.proposed_action}</h3><p className="mono">{item.approval_id}</p><footer><span>Role: {item.current_required_role || item.required_approver_roles[0]}</span><b>Review →</b></footer></article>)}</div>}{!query.isLoading && !query.data?.items.length && <div className="empty">No {status.toLowerCase()} approvals.</div>}{selected && <ApprovalDrawer item={selected} close={() => setSelected(null)} />}</>
}
function ApprovalDrawer({ item, close }: { item: Approval; close: () => void }) {
  const client = useQueryClient(); const [comments, setComments] = useState('')
  const mutation = useMutation({ mutationFn: (decision: string) => api.post(`/approvals/${item.approval_id}/${decision}`, { comments }), onSuccess: () => { client.invalidateQueries({ queryKey: ['approvals'] }); close() } })
  return <div className="drawer-backdrop" onMouseDown={close}><aside className="drawer" onMouseDown={e => e.stopPropagation()}><button className="close" onClick={close}>×</button><span className="eyebrow">APPROVAL REVIEW</span><h2>{item.approval_id}</h2><StatusBadge value={item.status} /><section><label>Proposed action</label><p>{item.proposed_action}</p></section><div className="two-col"><section><label>Risk level</label><strong>{item.risk_level}</strong></section><section><label>Financial impact</label><strong>{item.financial_impact}</strong></section></div><section><label>Required roles</label><p>{item.required_approver_roles.join(', ')}</p></section>{item.status === 'PENDING' && <><label>Decision comments<textarea rows={4} value={comments} onChange={e => setComments(e.target.value)} /></label>{mutation.error && <ErrorNotice message={errorMessage(mutation.error)} />}<div className="decision-row"><button className="danger" onClick={() => mutation.mutate('reject')}>Reject</button><button className="primary" onClick={() => mutation.mutate('approve')}>Approve</button></div></>}</aside></div>
}
