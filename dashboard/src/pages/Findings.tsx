/**
 * Agent Findings page — visible to Tenant Admin and Partner (same scope as Copiloto).
 * Partners see only findings for zones within their partner scope (RLS-enforced server-side).
 * Shows stock audit findings with summary, detail, and date.
 */
import { useEffect, useState } from 'react'
import { findings } from '../api/client'
import type { AgentFinding, FindingTaskType } from '../types'

const TASK_TYPE_LABELS: Record<FindingTaskType, string> = {
  stock_audit: 'Auditoría de stock',
  dwell_drop: 'Caída de dwell',
  copilot_audit: 'Auditoría Copiloto',
}

const TASK_TYPE_COLORS: Record<FindingTaskType, { bg: string; text: string }> = {
  stock_audit:   { bg: '#fef9c3', text: '#854d0e' },
  dwell_drop:    { bg: '#fee2e2', text: '#991b1b' },
  copilot_audit: { bg: '#ede9fe', text: '#5b21b6' },
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString('es-MX', { dateStyle: 'medium', timeStyle: 'short' })
}

export function Findings() {
  const [items, setItems] = useState<AgentFinding[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    findings.list()
      .then(setItems)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Hallazgos del Agente</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Resultados de auditorías automáticas de stock y anomalías detectadas.
      </p>

      {loading && (
        <p style={{ color: '#94a3b8', fontSize: 14 }}>Cargando hallazgos…</p>
      )}

      {error && (
        <p data-testid="findings-error" style={{ color: '#b91c1c', fontSize: 14 }}>
          Error al cargar: {error}
        </p>
      )}

      {!loading && !error && items.length === 0 && (
        <div style={{
          background: '#fff', borderRadius: 12, padding: 32,
          boxShadow: '0 1px 4px rgba(0,0,0,0.06)', textAlign: 'center',
        }}>
          <p style={{ color: '#94a3b8', fontSize: 14 }}>
            Sin hallazgos registrados. El agente los genera automáticamente.
          </p>
        </div>
      )}

      {!loading && items.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {items.map(item => {
            const colors = TASK_TYPE_COLORS[item.task_type]
            return (
              <div
                key={item.id}
                data-testid="finding-row"
                style={{
                  background: '#fff', borderRadius: 12, padding: 20,
                  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                  borderLeft: `4px solid ${colors.text}`,
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
                      <span style={{
                        padding: '2px 10px', borderRadius: 99, fontSize: 11, fontWeight: 600,
                        background: colors.bg, color: colors.text,
                      }}>
                        {TASK_TYPE_LABELS[item.task_type]}
                      </span>
                      {item.zone_id && (
                        <span style={{ fontSize: 12, color: '#64748b' }}>
                          Zona: {item.zone_id.slice(0, 8)}…
                        </span>
                      )}
                    </div>
                    <p style={{ fontWeight: 600, fontSize: 15, marginBottom: 6 }}>{item.summary}</p>

                    {/* Detail fields */}
                    <div style={{ fontSize: 13, color: '#475569', display: 'flex', flexWrap: 'wrap', gap: '4px 20px' }}>
                      {item.detail.recent_avg_dwell != null && (
                        <span>Dwell reciente: <strong>{item.detail.recent_avg_dwell.toFixed(0)}s</strong></span>
                      )}
                      {item.detail.baseline_avg_dwell != null && (
                        <span>Baseline: <strong>{item.detail.baseline_avg_dwell.toFixed(0)}s</strong></span>
                      )}
                      {item.detail.vision_finding && (
                        <span style={{ width: '100%', marginTop: 4, fontStyle: 'italic', color: '#64748b' }}>
                          "{item.detail.vision_finding}"
                        </span>
                      )}
                      {item.detail.snapshot_available === false && (
                        <span style={{ color: '#94a3b8' }}>Sin snapshot disponible</span>
                      )}
                    </div>

                    {/* Snapshot image — rendered only when server provides a presigned URL.
                        The URL is short-lived (default 5 min) and scoped to one R2 object.
                        It is generated server-side per-request under RLS — a partner cannot
                        construct or extend a URL for a snapshot outside their scope. */}
                    {item.snapshot_url && (
                      <div style={{ marginTop: 12 }}>
                        <img
                          src={item.snapshot_url}
                          alt={`Snapshot — ${item.summary}`}
                          data-testid="finding-snapshot"
                          style={{
                            maxWidth: '100%',
                            maxHeight: 220,
                            borderRadius: 6,
                            border: '1px solid #e2e8f0',
                            objectFit: 'cover',
                            display: 'block',
                          }}
                          onError={e => {
                            // Presigned URL may have expired if user left the tab open
                            ;(e.target as HTMLImageElement).style.display = 'none'
                          }}
                        />
                        <p style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>
                          Snapshot (enlace expira en 5 min)
                        </p>
                      </div>
                    )}
                  </div>

                  <div style={{ textAlign: 'right', flexShrink: 0 }}>
                    <p style={{ fontSize: 12, color: '#94a3b8' }}>{formatDate(item.created_at)}</p>
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
