/**
 * User management — Tenant Admin only.
 * List users and create operator/viewer accounts with site assignments.
 */
import { useEffect, useState } from 'react'
import { backoffice, sites } from '../api/client'
import type { UserListItem, Site } from '../types'

const ROLES = ['operator', 'viewer'] as const

export function Users() {
  const [userList, setUserList] = useState<UserListItem[]>([])
  const [siteList, setSiteList] = useState<Site[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  // form
  const [email, setEmail] = useState('')
  const [role, setRole] = useState<'operator' | 'viewer'>('operator')
  const [selectedSites, setSelectedSites] = useState<string[]>([])
  const [submitting, setSubmitting] = useState(false)
  const [formMsg, setFormMsg] = useState('')

  useEffect(() => {
    Promise.all([
      backoffice.listUsers().then(setUserList),
      sites.list().then(setSiteList),
    ])
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  function toggleSite(id: string) {
    setSelectedSites(prev => prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id])
  }

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || selectedSites.length === 0) return
    setSubmitting(true)
    setFormMsg('')
    try {
      const created = await backoffice.createUser({
        email: email.trim(),
        role,
        site_ids: selectedSites,
      })
      setUserList(prev => [...prev, created])
      setFormMsg(`Usuario ${created.email} creado. Invitación enviada (válida 72 h).`)
      setEmail('')
      setSelectedSites([])
    } catch (e: unknown) {
      setFormMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Usuarios</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Crea y administra operadores y viewers con acceso a sucursales específicas.
      </p>

      {loading && <p style={{ color: '#64748b' }}>Cargando…</p>}
      {error && <p style={{ color: '#ef4444' }}>{error}</p>}

      {!loading && !error && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 360px', gap: 24 }}>
          {/* User table */}
          <div style={{ background: '#fff', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
            <div style={{ padding: '16px 20px', borderBottom: '1px solid #f1f5f9', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ fontSize: 15, fontWeight: 600 }}>Usuarios del tenant</h2>
              <span style={{ fontSize: 13, color: '#64748b' }}>{userList.length} usuarios</span>
            </div>
            <table data-testid="users-table" style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ background: '#f8fafc' }}>
                  <th style={th}>Email</th>
                  <th style={th}>Rol</th>
                  <th style={th}>Sucursales</th>
                  <th style={th}>Estado</th>
                </tr>
              </thead>
              <tbody>
                {userList.map(u => (
                  <tr key={u.id} data-testid="user-row" style={{ borderBottom: '1px solid #f1f5f9' }}>
                    <td style={td}>{u.email}</td>
                    <td style={td}>
                      <span style={roleBadge(u.role)}>{u.role}</span>
                    </td>
                    <td style={td}>{u.site_count ?? '—'}</td>
                    <td style={td}>
                      <span style={{
                        fontSize: 12, padding: '2px 8px', borderRadius: 99,
                        background: u.status === 'active' ? '#dcfce7' : '#fef9c3',
                        color: u.status === 'active' ? '#166534' : '#854d0e',
                      }}>
                        {u.status ?? 'pending'}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!userList.length && (
              <p style={{ padding: 24, color: '#94a3b8', textAlign: 'center', fontSize: 14 }}>Sin usuarios aún.</p>
            )}
          </div>

          {/* Create form */}
          <div style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 18 }}>Invitar usuario</h2>
            <form onSubmit={handleCreate}>
              <label style={labelStyle}>Email</label>
              <input
                data-testid="user-email-input"
                type="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                placeholder="usuario@empresa.com"
                required
                style={inputStyle}
              />

              <label style={labelStyle}>Rol</label>
              <select
                data-testid="user-role-select"
                value={role}
                onChange={e => setRole(e.target.value as typeof role)}
                style={inputStyle}
              >
                {ROLES.map(r => (
                  <option key={r} value={r}>{r}</option>
                ))}
              </select>

              <label style={labelStyle}>Sucursales</label>
              <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: 8, maxHeight: 150, overflowY: 'auto' }}>
                {siteList.map(s => (
                  <label key={s.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 6px', fontSize: 14, cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selectedSites.includes(s.id)}
                      onChange={() => toggleSite(s.id)}
                    />
                    {s.name}
                  </label>
                ))}
                {!siteList.length && <p style={{ fontSize: 13, color: '#94a3b8' }}>Sin sucursales</p>}
              </div>

              <button
                type="submit"
                data-testid="user-create-btn"
                disabled={submitting || !email.trim() || selectedSites.length === 0}
                style={{
                  marginTop: 18, width: '100%', padding: 10,
                  background: (submitting || !email.trim() || selectedSites.length === 0) ? '#94a3b8' : '#0ea5e9',
                  color: '#fff', border: 'none', borderRadius: 8, fontSize: 14, fontWeight: 600, cursor: 'pointer',
                }}
              >
                {submitting ? 'Creando…' : 'Enviar invitación'}
              </button>
            </form>
            {formMsg && (
              <p data-testid="user-form-msg" style={{ marginTop: 12, fontSize: 13, color: formMsg.startsWith('Error') ? '#ef4444' : '#16a34a' }}>
                {formMsg}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function roleBadge(r: string): React.CSSProperties {
  const map: Record<string, [string, string]> = {
    admin:    ['#ede9fe', '#6d28d9'],
    operator: ['#dbeafe', '#1d4ed8'],
    viewer:   ['#f0fdf4', '#166534'],
  }
  const [bg, color] = map[r] ?? ['#f1f5f9', '#64748b']
  return { fontSize: 12, padding: '2px 8px', borderRadius: 99, background: bg, color }
}

const th: React.CSSProperties = { padding: '10px 16px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: '#64748b' }
const td: React.CSSProperties = { padding: '10px 16px', fontSize: 14 }
const labelStyle: React.CSSProperties = { display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4, marginTop: 14 }
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 14, boxSizing: 'border-box' }
