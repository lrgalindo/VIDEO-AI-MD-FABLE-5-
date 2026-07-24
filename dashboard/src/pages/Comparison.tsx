/**
 * Site comparison — Tenant Admin only.
 * Consumes site_traffic_comparison via GET /v1/analytics/comparison.
 */
import { useEffect, useState } from 'react'
import { analytics } from '../api/client'
import type { SiteTrafficWeek } from '../types'

export function Comparison() {
  const [data, setData] = useState<SiteTrafficWeek[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    analytics.trafficComparison()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  // Group by site
  const bySite = data.reduce<Record<string, SiteTrafficWeek[]>>((acc, row) => {
    const key = row.site_id
    acc[key] = acc[key] ?? []
    acc[key].push(row)
    return acc
  }, {})

  const siteNames = Object.fromEntries(data.map(r => [r.site_id, r.site_name]))

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Comparativo entre Sucursales</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Visitantes únicos por semana — site_traffic_comparison
      </p>

      {loading && <p style={{ color: '#64748b' }}>Cargando…</p>}
      {error && <p style={{ color: '#ef4444' }}>{error}</p>}

      {!loading && !error && (
        <div data-testid="comparison-table" style={{ background: '#fff', borderRadius: 12, overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ background: '#f1f5f9' }}>
                <th style={th}>Sucursal</th>
                <th style={th}>Semana</th>
                <th style={th}>Visitantes únicos</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(bySite).map(([siteId, rows]) =>
                rows.map((r, i) => (
                  <tr key={siteId + r.week} style={{ borderBottom: '1px solid #f1f5f9' }}>
                    {i === 0 && (
                      <td style={{ ...td, fontWeight: 600 }} rowSpan={rows.length}>
                        {siteNames[siteId] ?? siteId.slice(0, 8)}
                      </td>
                    )}
                    <td style={td}>{r.week.slice(0, 10)}</td>
                    <td style={td}>{r.unique_visitors.toLocaleString()}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          {!data.length && (
            <p style={{ padding: 24, color: '#64748b', textAlign: 'center' }}>Sin datos comparativos.</p>
          )}
        </div>
      )}
    </div>
  )
}

const th: React.CSSProperties = { padding: '12px 16px', textAlign: 'left', fontSize: 13, fontWeight: 600, color: '#64748b' }
const td: React.CSSProperties = { padding: '10px 16px', fontSize: 14 }
