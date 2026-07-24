/**
 * Traffic page — Tenant Admin / Operator view.
 * Consumes site_traffic_daily via GET /v1/analytics/traffic.
 * Shows a bar chart of unique_visitors per day + a simple heatmap grid.
 */
import { useEffect, useState } from 'react'
import { analytics } from '../api/client'
import type { SiteTrafficDay } from '../types'

function BarChart({ data }: { data: SiteTrafficDay[] }) {
  if (!data.length) return <p data-testid="traffic-chart" style={{ color: '#64748b' }}>Sin datos de tráfico.</p>
  const max = Math.max(...data.map(d => d.unique_visitors), 1)
  return (
    <div data-testid="traffic-chart" style={{ display: 'flex', gap: 6, alignItems: 'flex-end', height: 180 }}>
      {data.slice(-14).map(d => (
        <div key={d.day + d.site_id} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', flex: 1 }}>
          <div
            style={{
              width: '100%', background: '#0ea5e9',
              height: `${(d.unique_visitors / max) * 140}px`,
              borderRadius: '4px 4px 0 0', minHeight: 2,
            }}
            title={`${d.day}: ${d.unique_visitors} visitantes`}
          />
          <span style={{ fontSize: 9, color: '#94a3b8', marginTop: 2, writingMode: 'vertical-lr' }}>
            {d.day.slice(5)}
          </span>
        </div>
      ))}
    </div>
  )
}

function HeatmapGrid({ data }: { data: SiteTrafficDay[] }) {
  if (!data.length) return null
  const max = Math.max(...data.map(d => d.total_detections), 1)
  const cells = data.slice(-28).map(d => ({
    label: d.day.slice(5),
    value: d.total_detections,
    intensity: d.total_detections / max,
  }))
  return (
    <div data-testid="traffic-heatmap" style={{ display: 'grid', gridTemplateColumns: 'repeat(7, 1fr)', gap: 4, marginTop: 16 }}>
      {cells.map((c, i) => (
        <div
          key={i}
          title={`${c.label}: ${c.value} detecciones`}
          style={{
            height: 40, borderRadius: 6,
            background: `rgba(14,165,233,${0.1 + c.intensity * 0.9})`,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, color: c.intensity > 0.5 ? '#fff' : '#1e293b',
          }}
        >
          {c.label}
        </div>
      ))}
    </div>
  )
}

export function Traffic() {
  const [data, setData] = useState<SiteTrafficDay[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    analytics.trafficDaily()
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Tráfico / Heatmap</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Visitantes únicos y detecciones totales por día — site_traffic_daily
      </p>

      {loading && <p style={{ color: '#64748b' }} data-testid="traffic-loading">Cargando…</p>}
      {error && <p style={{ color: '#ef4444' }} data-testid="traffic-error">{error}</p>}

      {!loading && !error && (
        <>
          <section style={{ background: '#fff', borderRadius: 12, padding: 24, marginBottom: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16 }}>Visitantes únicos — últimas 2 semanas</h2>
            <BarChart data={data} />
          </section>

          <section style={{ background: '#fff', borderRadius: 12, padding: 24, boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
            <h2 style={{ fontSize: 15, fontWeight: 600, marginBottom: 8 }}>Heatmap de detecciones — últimas 4 semanas</h2>
            <HeatmapGrid data={data} />
          </section>
        </>
      )}
    </div>
  )
}
