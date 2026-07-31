import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/auth'

const nav = [
  ['/', 'Overview', '⌂'], ['/workflows', 'Workflows', '◇'],
  ['/approvals', 'Approvals', '✓'], ['/audit', 'Audit trail', '≡'],
  ['/admin', 'Admin', '⚙'],
]

export function AppLayout() {
  const user = useAuthStore((state) => state.user)
  const logout = useAuthStore((state) => state.logout)
  const location = useLocation()
  const title = nav.find(([path]) => path === location.pathname)?.[1] || 'Workflow detail'
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand"><span className="brand-mark">A</span><div>AGENTIC HR <span>AI</span></div></div>
        <div className="workspace-label">OPERATIONS</div>
        <nav>{nav.map(([path, label, icon]) => (
          <NavLink key={path} to={path} end={path === '/'}><i>{icon}</i>{label}</NavLink>
        ))}</nav>
        <div className="sidebar-foot">
          <div className="system-dot"><span /> All systems operational</div>
          <button className="profile-card" onClick={() => location.pathname !== '/change-password' && (window.location.href = '/change-password')}>
            <div className="avatar">{user?.full_name?.[0] || 'U'}</div>
            <div><strong>{user?.full_name || user?.username}</strong><small>{user?.roles?.[0] || 'User'}</small></div>
            <span onClick={(event) => { event.stopPropagation(); logout() }}>↪</span>
          </button>
        </div>
      </aside>
      <main>
        <header><div><span className="eyebrow">HR OPERATIONS</span><h1>{title}</h1></div><div className="header-actions"><span className="live"><i /> LIVE</span><button className="icon-button">⌕</button><button className="icon-button">◌</button></div></header>
        <div className="page"><Outlet /></div>
      </main>
    </div>
  )
}

export function StatusBadge({ value }: { value: string }) {
  const key = value.toLowerCase().replaceAll('_', '-')
  return <span className={`status status-${key}`}><i />{value.replaceAll('_', ' ')}</span>
}

export function Loading() { return <div className="empty"><div className="spinner" />Loading operational data…</div> }
export function ErrorNotice({ message }: { message: string }) { return <div className="error-notice">⚠ {message}</div> }
