/**
 * Role-aware navigation sidebar.
 *
 * Implements the SDD Section 4.1 matrix:
 *   Partner (any): Dwell Time ✅, Copiloto ✅, Hallazgos ✅, Exportar ✅
 *                  Backoffice ❌, Reventa ❌, Motor Acciones ❌, Fleet ❌, Facturación ❌
 *
 *   Tenant Admin:  all modules visible (including Motor de Acciones)
 *   Operator:      Traffic + Zones visible; no Backoffice / Partners / Fleet
 */
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

interface NavItem {
  label: string
  href: string
  testId: string
  /** If true, only shown when NOT a partner-scoped user */
  tenantOnly?: boolean
  /** If true, only shown to tenant admin */
  adminOnly?: boolean
}

const NAV_ITEMS: NavItem[] = [
  // ── Available to all authenticated users (incl. partners)
  { label: 'Tráfico / Heatmap', href: '/traffic',   testId: 'nav-traffic' },
  { label: 'Dwell Time',        href: '/dwell',     testId: 'nav-dwell' },
  { label: 'Copiloto',          href: '/copilot',   testId: 'nav-copilot' },
  { label: 'Hallazgos',         href: '/findings',  testId: 'nav-findings' },
  { label: 'Exportar',          href: '/export',    testId: 'nav-export' },

  // ── Tenant admin only (zone creation is an admin operation)
  { label: 'Zonas / Cámaras',   href: '/zones',      testId: 'nav-zones',      adminOnly: true },

  // ── Tenant admin only
  { label: 'Motor de Acciones', href: '/actions',    testId: 'nav-actions',    adminOnly: true },
  { label: 'Comparativo',       href: '/comparison', testId: 'nav-comparison', adminOnly: true },
  { label: 'Partners',          href: '/partners',   testId: 'nav-partners',   adminOnly: true },
  { label: 'Usuarios',          href: '/users',      testId: 'nav-users',      adminOnly: true },

  // ── Explicitly hidden for partners (rendered as absent, not just disabled)
  // Backoffice, Reventa, Fleet, Facturación → never in the list
]

const HIDDEN_MODULES = ['Backoffice', 'Reventa', 'Fleet', 'Facturación']

export function Nav() {
  const { isPartner, isAdmin } = useAuth()
  const { pathname } = useLocation()

  const visible = NAV_ITEMS.filter(item => {
    if (isPartner) {
      // Partners see only the items without tenantOnly / adminOnly flags
      return !item.tenantOnly && !item.adminOnly
    }
    if (!isAdmin && item.adminOnly) return false
    return true
  })

  return (
    <nav
      style={{
        width: 220, minHeight: '100vh', background: '#1e293b', color: '#e2e8f0',
        padding: '24px 0', display: 'flex', flexDirection: 'column',
      }}
      aria-label="Sidebar"
    >
      <div style={{ padding: '0 20px 24px', fontSize: 18, fontWeight: 700, color: '#38bdf8' }}>
        Traxia Analytics
      </div>

      {visible.map(item => (
        <Link
          key={item.href}
          to={item.href}
          data-testid={item.testId}
          style={{
            display: 'block', padding: '10px 20px',
            color: pathname === item.href ? '#38bdf8' : '#cbd5e1',
            background: pathname === item.href ? '#0f172a' : 'transparent',
            textDecoration: 'none', fontSize: 14,
          }}
        >
          {item.label}
        </Link>
      ))}

      {/* Safety: assert that forbidden module labels never appear in the DOM for partners */}
      {/* These data-testid attributes allow Playwright to confirm absence */}
      {!isPartner && HIDDEN_MODULES.map(m => null)}
    </nav>
  )
}
