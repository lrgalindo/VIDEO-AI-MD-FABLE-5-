/**
 * Dwell Time page — visible to ALL roles (tenant + partner).
 * Partners see only their own zones (enforced by RLS on zone_dwell_summary).
 * Tenant admins see all non-staff_exclusion zones.
 */
import { useEffect, useState } from 'react'
import { analytics } from '../api/client'
import type { ZoneDwellDay } from '../types'

export function Dwell() {
  const [data, setData] = useState<ZoneDwellDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    analytics.dwellSummary()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Dwell Time por Zona</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Tiempo de permanencia por zona (excluye zonas staff_exclusion) — zone_dwell_summary
      </p>

      {loading && <p style={{ color: '#64748b' }} data-testid="dwell-loading">Cargando…</p>}
      {error && <p style={{ color: '#ef4444' }} data-testid="dwell-error">{error}</p>}

      {!loading && !error && (
        <div data-testid="dwell-table" style={{ background: '#fff', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f1f5f9' }}>
                <th style={th}>Zona</th>
                <th style={th}>Tipo</th>
                <th style={th}>Día</th>
                <th style={th}>Sesiones</th>
                <th style={th}>Dwell promedio (s)</th>
                <th style={th}>Máximo (s)</th>
              </tr>
            </thead>
            <tbody>
              {data.map(r => (
                <tr key={r.zone_id + r.day} style={{ borderBottom: '1px solid #f1f5f9' }}>
                  <td style={td}>{r.zone_name}</td>
                  <td style={td}>
                    <span style={{
                      background: r.zone_type === 'shelf' ? '#dbeafe' : '#f0fdf4',
                      color: r.zone_type === 'shelf' ? '#1d4ed8' : '#166534',
                      padding: '2px 8px', borderRadius: 99, fontSize: 12,
                    }}>
                      {r.zone_type}
                    </span>
                  </td>
                  <td style={td}>{r.day.slice(0, 10)}</td>
                  <td style={td}>{r.sessions}</td>
                  <td style={td}>{r.avg_dwell_seconds}</td>
                  <td style={td}>{r.max_dwell_seconds}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!data.length && (
            <p style={{ padding: 24, color: '#64748b', textAlign: 'center' }}>Sin datos de dwell time.</p>
          )}
        </div>
      )}
    </div>
  )
}

const th: React.CSSProperties = { padding: '12px 16px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: '#64748b' }
const td: React.CSSProperties = { padding: '10px 16px', fontSize: 14 }
