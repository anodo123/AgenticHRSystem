import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api, errorMessage } from '../api/client'
import { ErrorNotice, Loading, StatusBadge } from '../components/AppLayout'

type Employee = { id: number; employee_number: string; first_name: string; last_name: string; email: string; department?: string; job_title?: string; employment_status: string }

export function AdminPage() {
  const [tab, setTab] = useState('employees')
  return <><div className="toolbar"><div className="filters"><button className={tab === 'employees' ? 'active' : ''} onClick={() => setTab('employees')}>Employees</button><button className={tab === 'policies' ? 'active' : ''} onClick={() => setTab('policies')}>Policy library</button><button className={tab === 'tasks' ? 'active' : ''} onClick={() => setTab('tasks')}>Scheduled tasks</button></div></div>{tab === 'employees' ? <Employees /> : tab === 'policies' ? <Policies /> : <Tasks />}</>
}
function Employees() {
  const query = useQuery({ queryKey: ['employees'], queryFn: () => api.get('/employees/').then(r => r.data) })
  if (query.isLoading) return <Loading />; if (query.error) return <ErrorNotice message={errorMessage(query.error)} />
  return <section className="panel"><div className="panel-title"><div><span className="eyebrow">PEOPLE DIRECTORY</span><h2>{query.data.total} employees</h2></div></div><div className="table-wrap"><table><thead><tr><th>Employee</th><th>ID</th><th>Department</th><th>Title</th><th>Status</th></tr></thead><tbody>{query.data.items.map((e: Employee) => <tr key={e.id}><td><strong>{e.first_name} {e.last_name}</strong><small className="block">{e.email}</small></td><td className="mono">{e.employee_number}</td><td>{e.department || '—'}</td><td>{e.job_title || '—'}</td><td><StatusBadge value={e.employment_status} /></td></tr>)}</tbody></table></div></section>
}
function Policies() {
  const [query, setQuery] = useState('leave and payroll')
  const search = useQuery({ queryKey: ['policies', query], queryFn: () => api.get('/rag/policies/search', { params: { query } }).then(r => r.data), enabled: query.length > 2 })
  return <><div className="search wide"><span>⌕</span><input value={query} onChange={e => setQuery(e.target.value)} placeholder="Search the policy knowledge base…" /></div>{search.isLoading ? <Loading /> : search.error ? <ErrorNotice message={errorMessage(search.error)} /> : <div className="policy-grid">{search.data?.items.map((item: any) => <article className="panel" key={item.policy_id}><span className="eyebrow">{item.policy_type || 'POLICY'}</span><h3>{item.title}</h3><p>{item.content_preview || item.content || 'Policy content match'}</p><footer><span>{Math.round((item.score || 0) * 100)}% relevance</span><span>{item.country || 'Global'}</span></footer></article>)}</div>}</>
}
function Tasks() {
  const client = useQueryClient()
  const query = useQuery({ queryKey: ['tasks'], queryFn: () => api.get('/tasks/').then(r => r.data), retry: false })
  const run = useMutation({ mutationFn: (id: string) => api.post(`/tasks/${id}/run`), onSuccess: () => client.invalidateQueries({ queryKey: ['tasks'] }) })
  if (query.isLoading) return <Loading />; if (query.error) return <ErrorNotice message={errorMessage(query.error)} />
  return <div className="approval-grid">{query.data.items.map((task: any) => <article className="approval-card" key={task.task_id}><div><StatusBadge value={task.is_enabled ? 'ENABLED' : 'DISABLED'} /><span className="risk">{task.priority}</span></div><h3>{task.name}</h3><p>{task.description || task.workflow_type}</p><footer><span>{task.schedule_cron || 'Manual trigger'}</span><button onClick={() => run.mutate(task.task_id)}>Run now →</button></footer></article>)}</div>
}
