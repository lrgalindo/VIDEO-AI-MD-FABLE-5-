/**
 * Partner onboarding — Tenant Admin only.
 * One-step form: name, contact email, cameras/zones to share, access expiry.
 * POST /v1/backoffice/partners
 */
import { useEffect, useState } from 'react'
import { backoffice, sites } from '../api/client'
import type { Site, PartnerResponse } from '../types'

export function Partners() {
  const [siteList, setSiteList] = useState<Site[]>([])
  const [partnerList, setPartnerList] = useState<PartnerResponse[]>([])

  // form fields
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [selectedSites, setSelectedSites] = useState<string[]>([])
  const [expiresAt, setExpiresAt] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [msg, setMsg] = useState('')
  const [revoking, setRevoking] = useState<string | null>(null)

  useEffect(() => {
    sites.list().then(setSiteList).catch(() => {})
    backoffice.listUsers().catch(() => {})  // warm auth
    loadPartners()
  }, [])

  function loadPartners() {
    // There is no GET /v1/backoffice/partners in the current API — we derive
    // the list from the create response cache kept in local state.
    // (Backend GET /v1/backoffice/partners would be wired up in a future iteration.)
  }

  function toggleSite(id: string) {
    setSelectedSites(prev =>
      prev.includes(id) ? prev.filter(s => s !== id) : [...prev, id]
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!name.trim() || !email.trim()) return
    setSubmitting(true)
    setMsg('')
    try {
      const res = await backoffice.createPartner({
        name: name.trim(),
        contact_email: email.trim(),
        site_ids: selectedSites,
        access_expires_at: expiresAt || undefined,
      })
      setPartnerList(prev => [...prev, res])
      setMsg(`Partner "${res.name}" dado de alta. Invitación enviada a ${email}.`)
      setName('')
      setEmail('')
      setSelectedSites([])
      setExpiresAt('')
    } catch (e: unknown) {
      setMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRevoke(partnerId: string, partnerName: string) {
    setRevoking(partnerId)
    try {
      await backoffice.revokePartner(partnerId)
      setPartnerList(prev => prev.map(p => p.id === partnerId ? { ...p, status: 'inactive' } : p))
      setMsg(`Acceso de "${partnerName}" revocado.`)
    } catch (e: unknown) {
      setMsg(`Error al revocar: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRevoking(null)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Gestión de Partners</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Alta en un solo paso — crea el registro y genera la invitación automáticamente.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* Create form */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20 }}>Nuevo Partner</h2>
          <form onSubmit={handleSubmit}>
            <label style={labelStyle}>Nombre de la empresa</label>
            <input
              data-testid="partner-name-input"
              value={name}
              onChange={e => setName(e.target.value)}
              placeholder="ej. Distribuidora Norteña S.A."
              required
              style={inputStyle}
            />

            <label style={labelStyle}>Correo de contacto</label>
            <input
              data-testid="partner-email-input"
              type="email"
              value={email}
              onChange={e => setEmail(e.target.value)}
              placeholder="admin@partner.com"
              required
              style={inputStyle}
            />

            <label style={labelStyle}>Sucursales a compartir</label>
            <div style={{ border: '1px solid #e2e8f0', borderRadius: 6, padding: 8, maxHeight: 140, overflowY: 'auto' }}>
              {siteList.length === 0 && (
                <p style={{ fontSize: 13, color: '#94a3b8', padding: 4 }}>Sin sucursales disponibles</p>
              )}
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
            </div>

            <label style={labelStyle}>Acceso hasta (opcional)</label>
            <input
              data-testid="partner-expires-input"
              type="date"
              value={expiresAt}
              onChange={e => setExpiresAt(e.target.value)}
              style={inputStyle}
            />

            <button
              type="submit"
              data-testid="partner-submit-btn"
              disabled={submitting}
              style={{
                marginTop: 20, width: '100%', padding: '11px',
                background: submitting ? '#94a3b8' : '#0ea5e9',
                color: '#fff', border: 'none', borderRadius: 8,
                fontSize: 15, fontWeight: 600, cursor: submitting ? 'not-allowed' : 'pointer',
              }}
            >
              {submitting ? 'Creando…' : 'Dar de alta Partner'}
            </button>
          </form>

          {msg && (
            <p data-testid="partner-msg" style={{ marginTop: 14, fontSize: 13, color: msg.startsWith('Error') ? '#ef4444' : '#16a34a' }}>
              {msg}
            </p>
          )}
        </div>

        {/* Partner list */}
        <div style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <h2 style={{ fontSize: 16, fontWeight: 600, marginBottom: 20 }}>Partners activos (esta sesión)</h2>
          {partnerList.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: 14 }}>Da de alta un Partner para verlo aquí.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {partnerList.map(p => (
                <div
                  key={p.id}
                  data-testid="partner-row"
                  style={{
                    border: '1px solid #e2e8f0', borderRadius: 8, padding: '12px 16px',
                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                  }}
                >
                  <div>
                    <p style={{ fontWeight: 600, fontSize: 14, marginBottom: 2 }}>{p.name}</p>
                    <p style={{ fontSize: 12, color: '#64748b' }}>{p.contact_email}</p>
                    <span style={{
                      fontSize: 11, padding: '2px 8px', borderRadius: 99,
                      background: p.status === 'active' ? '#dcfce7' : '#f1f5f9',
                      color: p.status === 'active' ? '#166534' : '#64748b',
                    }}>
                      {p.status}
                    </span>
                  </div>
                  {p.status === 'active' && (
                    <button
                      data-testid="partner-revoke-btn"
                      onClick={() => handleRevoke(p.id, p.name)}
                      disabled={revoking === p.id}
                      style={{
                        padding: '6px 14px', background: revoking === p.id ? '#f1f5f9' : '#fef2f2',
                        color: '#b91c1c', border: '1px solid #fecaca', borderRadius: 6,
                        fontSize: 13, cursor: 'pointer',
                      }}
                    >
                      {revoking === p.id ? 'Revocando…' : 'Revocar'}
                    </button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

const labelStyle: React.CSSProperties = { display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4, marginTop: 14 }
const inputStyle: React.CSSProperties = { width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 14, boxSizing: 'border-box' }
