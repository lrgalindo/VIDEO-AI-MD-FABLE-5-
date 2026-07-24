import { Outlet, Navigate } from 'react-router-dom'
import { Nav } from './Nav'
import { useAuth } from '../hooks/useAuth'

export function Layout() {
  const { isAuthenticated } = useAuth()
  if (!isAuthenticated) return <Navigate to="/login" replace />
  return (
    <div style={{ display: 'flex', minHeight: '100vh' }}>
      <Nav />
      <main style={{ flex: 1, padding: 32, overflow: 'auto' }}>
        <Outlet />
      </main>
    </div>
  )
}
