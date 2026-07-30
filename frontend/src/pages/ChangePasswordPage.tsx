import { FormEvent, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { api, errorMessage } from '../api/client'
import { ErrorNotice } from '../components/AppLayout'

export function ChangePasswordPage() {
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [confirm, setConfirm] = useState('')
  const mutation = useMutation({ mutationFn: () => api.post('/auth/change-password', { current_password: current, new_password: next, confirm_password: confirm }) })
  return <section className="panel form-panel"><span className="eyebrow">ACCOUNT SECURITY</span><h2>Change password</h2><p className="muted">Use a strong, unique password for your operations account.</p>{mutation.isSuccess && <div className="success-notice">Password changed successfully.</div>}{mutation.error && <ErrorNotice message={errorMessage(mutation.error)} />}<form onSubmit={(e: FormEvent) => { e.preventDefault(); mutation.mutate() }}><label>Current password<input type="password" value={current} onChange={e => setCurrent(e.target.value)} required /></label><label>New password<input type="password" minLength={8} value={next} onChange={e => setNext(e.target.value)} required /></label><label>Confirm new password<input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} required /></label><button className="primary">Update password</button></form></section>
}
