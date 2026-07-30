import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, errorMessage } from '../api/client'
import type { AuditEvent, ListResponse } from '../types'
import { ErrorNotice, Loading } from '../components/AppLayout'

export function AuditPage() {
  const [eventType, setEventType] = useState('')
  const query = useQuery({ queryKey: ['audit', eventType], queryFn: () => api.get<ListResponse<AuditEvent>>('/audit/', { params: { limit: 100, event_type: eventType || undefined } }).then(r => r.data) })
  return <><div className="toolbar"><div className="search"><span>⌕</span><input placeholder="Filter by event type…" value={eventType} onChange={e => setEventType(e.target.value)} /></div><span className="muted">{query.data?.total || 0} immutable events</span></div>{query.isLoading ? <Loading /> : query.error ? <ErrorNotice message={errorMessage(query.error)} /> : <section className="panel"><div className="table-wrap"><table><thead><tr><th>Timestamp</th><th>Event</th><th>Action</th><th>Actor</th><th>Entity</th><th>Workflow</th></tr></thead><tbody>{query.data?.items.map(event => <tr key={event.id}><td>{new Date(event.timestamp).toLocaleString()}</td><td><span className="event-name">{event.event_type.replaceAll('_',' ')}</span></td><td>{event.action || '—'}</td><td>{event.actor_role || event.actor_id || 'System'}</td><td>{event.entity_type ? `${event.entity_type} #${event.entity_id}` : '—'}</td><td className="mono">{event.workflow_id || '—'}</td></tr>)}</tbody></table></div></section>}</>
}
