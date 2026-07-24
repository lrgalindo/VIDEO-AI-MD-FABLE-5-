/**
 * Export page — visible to ALL roles (tenant + partner).
 * Downloads dwell time data as CSV scoped to the caller's RLS context.
 */
import { useState } from 'react'
import { analytics } from '../api/client'

export function Export() {
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  async function handleExport() {
    setLoading(true)
    try {
      const rows = await analytics.dwellSummary()
      const header = 'zona,tipo,dia,sesiones,dwell_promedio_s,dwell_max_s\n'
      const csv = rows
        .map(r => [r.zone_name, r.zone_type, r.day.slice(0, 10), r.sessions, r.avg_dwell_seconds, r.max_dwell_seconds].join(','))
        .join('\n')
      const blob = new Blob([header + csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `traxia-export-${new Date().toISOString().slice(0, 10)}.csv`
      a.click()
      URL.revokeObjectURL(url)
      setDone(true)
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e)
      alert(`Error al exportar: ${msg}`)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Exportar Reportes</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Descarga tus datos de dwell time en CSV (acotado a tu alcance).
      </p>
      <div style={{ background: '#fff', borderRadius: 12, padding: 32, boxShadow: '0 1px 4px rgba(0,0,0,0.06)', maxWidth: 480 }}>
        <button
          data-testid="export-csv-btn"
          onClick={handleExport}
          disabled={loading}
          style={{
            padding: '12px 24px', background: loading ? '#94a3b8' : '#0ea5e9',
            color: '#fff', border: 'none', borderRadius: 8,
            fontSize: 15, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Generando…' : 'Exportar CSV'}
        </button>
        {done && (
          <p data-testid="export-done" style={{ marginTop: 16, color: '#16a34a', fontSize: 14 }}>
            ✓ Descarga iniciada
          </p>
        )}
      </div>
    </div>
  )
}
