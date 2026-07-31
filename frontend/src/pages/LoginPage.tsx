import { FormEvent, useState } from 'react'
import { Navigate } from 'react-router-dom'
import { api, errorMessage } from '../api/client'
import { useAuthStore } from '../store/auth'

export function LoginPage() {
  const auth = useAuthStore()
  const [username, setUsername] = useState('admin')
  const [password, setPassword] = useState('demo123!')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  if (auth.accessToken) return <Navigate to="/" replace />
  async function submit(event: FormEvent) {
    event.preventDefault(); setBusy(true); setError('')
    try {
      const { data } = await api.post('/auth/login', { username, password })
      auth.login(data.access_token, data.refresh_token, data)
    } catch (err) { setError(errorMessage(err)) } finally { setBusy(false) }
  }
  return <div className="login-page">
    <div className="login-visual"><div className="brand large"><span className="brand-mark">A</span><div>AGENTIC HR <span>AI</span></div></div><h1>HR operations that<br /><em>heal themselves.</em></h1><p>Detect, investigate and resolve workforce anomalies with governed AI workflows.</p><div className="signal-grid">{['Real-time anomaly detection','Policy-grounded decisions','Human approval controls'].map((x, i) => <div key={x}><b>0{i + 1}</b><span>{x}</span></div>)}</div></div>
    <form className="login-card" onSubmit={submit}><span className="eyebrow">SECURE ACCESS</span><h2>Welcome back</h2><p>Sign in to your operations workspace.</p>{error && <div className="error-notice">{error}</div>}<label>Username<input value={username} onChange={e => setUsername(e.target.value)} required /></label><label>Password<input type="password" value={password} onChange={e => setPassword(e.target.value)} required /></label><button className="primary" disabled={busy}>{busy ? 'Authenticating…' : 'Sign in securely →'}</button><small>Protected by role-based access controls</small></form>
  </div>
}
