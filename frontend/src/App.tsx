import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from './components/AppLayout'
import { useAuthStore } from './store/auth'
import { LoginPage } from './pages/LoginPage'
import { DashboardPage } from './pages/DashboardPage'
import { WorkflowsPage, WorkflowDetailPage } from './pages/WorkflowsPage'
import { ApprovalsPage } from './pages/ApprovalsPage'
import { AuditPage } from './pages/AuditPage'
import { AdminPage } from './pages/AdminPage'
import { ChangePasswordPage } from './pages/ChangePasswordPage'
import './App.css'

function Protected() {
  const token = useAuthStore((state) => state.accessToken)
  return token ? <AppLayout /> : <Navigate to="/login" replace />
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Protected />}>
        <Route index element={<DashboardPage />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/workflows/:workflowId" element={<WorkflowDetailPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/admin" element={<AdminPage />} />
        <Route path="/change-password" element={<ChangePasswordPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
