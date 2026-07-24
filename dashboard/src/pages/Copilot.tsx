/**
 * Copiloto page — visible to ALL roles (tenant admin, operator, partner).
 * Partners see only insights scoped to their zones (enforced server-side by RLS +
 * the authorized-zone list in the system prompt). The UI never decides scope.
 */
import { useState } from 'react'
import { copilot } from '../api/client'
import type { ChatResponse } from '../types'

export function Copilot() {
  const [question, setQuestion] = useState('')
  const [response, setResponse] = useState<ChatResponse | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleAsk(e: React.FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q) return
    setLoading(true)
    setError('')
    setResponse(null)
    try {
      const res = await copilot.chat(q)
      setResponse(res)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Copiloto</h1>
      <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
        Análisis y recomendaciones sobre tus zonas — acotado a tu alcance.
      </p>

      <div style={{
        background: '#fff', borderRadius: 12, padding: 24,
        boxShadow: '0 1px 4px rgba(0,0,0,0.06)', maxWidth: 720,
      }}>
        <form onSubmit={handleAsk} style={{ display: 'flex', gap: 12, marginBottom: 24 }}>
          <input
            data-testid="copilot-input"
            value={question}
            onChange={e => setQuestion(e.target.value)}
            placeholder="Pregunta sobre tus datos (ej. '¿Cuál fue el día más concurrido?')"
            maxLength={2000}
            style={{
              flex: 1, padding: '10px 14px', border: '1px solid #e2e8f0',
              borderRadius: 8, fontSize: 14,
            }}
          />
          <button
            type="submit"
            data-testid="copilot-submit"
            disabled={loading || !question.trim()}
            style={{
              padding: '10px 20px',
              background: loading || !question.trim() ? '#94a3b8' : '#0ea5e9',
              color: '#fff', border: 'none', borderRadius: 8,
              fontSize: 14, fontWeight: 600,
              cursor: loading || !question.trim() ? 'not-allowed' : 'pointer',
            }}
          >
            {loading ? 'Analizando…' : 'Preguntar'}
          </button>
        </form>

        {error && (
          <div
            data-testid="copilot-error"
            style={{
              background: '#fef2f2', border: '1px solid #fecaca',
              borderRadius: 8, padding: 14, fontSize: 14, color: '#b91c1c',
            }}
          >
            {error}
          </div>
        )}

        {response && (
          <div
            data-testid="copilot-answer"
            style={{
              background: '#f0f9ff', border: '1px solid #bae6fd',
              borderRadius: 8, padding: 16, fontSize: 14, lineHeight: 1.6, color: '#0c4a6e',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 8 }}>
              <strong>Copiloto</strong>
              <span style={{ fontSize: 11, color: '#64748b' }}>
                {response.authorized_zone_count} zona{response.authorized_zone_count !== 1 ? 's' : ''} en alcance
                &nbsp;·&nbsp;{response.model}
              </span>
            </div>
            <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{response.answer}</p>
          </div>
        )}
      </div>
    </div>
  )
}
