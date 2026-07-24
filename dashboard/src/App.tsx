import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Traffic } from './pages/Traffic'
import { Comparison } from './pages/Comparison'
import { Dwell } from './pages/Dwell'
import { Zones } from './pages/Zones'
import { Copilot } from './pages/Copilot'
import { Export } from './pages/Export'
import { Partners } from './pages/Partners'
import { Users } from './pages/Users'
import { Actions } from './pages/Actions'
import { Findings } from './pages/Findings'
import { useAuth } from './hooks/useAuth'

function RequireAuth({ children }: { children: React.ReactNode }) {
  const { token } = useAuth()
  if (!token) return <Navigate to="/login" replace />
  return <>{children}</>
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const { isAdmin } = useAuth()
  if (!isAdmin) return <Navigate to="/" replace />
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/traffic" replace />} />
          <Route path="traffic" element={<Traffic />} />
          <Route path="dwell" element={<Dwell />} />
          <Route path="copilot" element={<Copilot />} />
          <Route path="findings" element={<Findings />} />
          <Route path="export" element={<Export />} />

          {/* Tenant admin only routes */}
          <Route
            path="actions"
            element={<AdminOnly><Actions /></AdminOnly>}
          />
          <Route
            path="comparison"
            element={<AdminOnly><Comparison /></AdminOnly>}
          />
          <Route
            path="zones"
            element={<AdminOnly><Zones /></AdminOnly>}
          />
          <Route
            path="users"
            element={<AdminOnly><Users /></AdminOnly>}
          />
          <Route
            path="partners"
            element={<AdminOnly><Partners /></AdminOnly>}
          />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </BrowserRouter>
  )
}
