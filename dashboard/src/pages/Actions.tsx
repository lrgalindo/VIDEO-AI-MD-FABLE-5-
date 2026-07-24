/**
 * Motor de Acciones — Tenant Admin only (SDD §12.10, Section 4.1).
 *
 * Tabs:
 *   Reglas  — CRUD for action rules (threshold + SOP templates)
 *   Canales — CRUD for notification channels; WhatsApp requires cost declaration
 *   Log     — read-only view of recent dispatches
 *
 * Partners NEVER see this page. The route is guarded at App.tsx (AdminOnly)
 * and the nav item carries adminOnly:true so the link never renders in partner
 * sessions. E2E tests confirm absence from DOM with toHaveCount(0).
 */
import { useEffect, useState } from 'react'
import { actions } from '../api/client'
import type { ActionRule, ActionChannel, ActionLogEntry, RuleType, ChannelType } from '../types'

type Tab = 'rules' | 'channels' | 'log'

const RULE_TYPE_LABELS: Record<RuleType, string> = {
  threshold: 'Umbral de ocupación',
  sop_staff_absent_checkout: 'SOP — Caja sin personal',
  sop_late_opening: 'SOP — Apertura tardía',
  sop_unattended_customer: 'SOP — Cliente sin atención',
}

const CHANNEL_TYPE_LABELS: Record<ChannelType, string> = {
  slack: 'Slack (webhook)',
  telegram: 'Telegram (Bot API)',
  email: 'Correo (SMTP)',
  whatsapp: 'WhatsApp (Meta Cloud API)',
}

export function Actions() {
  const [tab, setTab] = useState<Tab>('rules')
  const [rules, setRules] = useState<ActionRule[]>([])
  const [channels, setChannels] = useState<ActionChannel[]>([])
  const [log, setLog] = useState<ActionLogEntry[]>([])
  const [loadErr, setLoadErr] = useState('')

  // Rule form
  const [ruleType, setRuleType] = useState<RuleType>('threshold')
  const [ruleName, setRuleName] = useState('')
  const [ruleThreshold, setRuleThreshold] = useState('')
  const [ruleWindow, setRuleWindow] = useState('')
  const [ruleSubmitting, setRuleSubmitting] = useState(false)
  const [ruleMsg, setRuleMsg] = useState('')

  // Channel form
  const [chType, setChType] = useState<ChannelType>('slack')
  const [chName, setChName] = useState('')
  const [chConfig, setChConfig] = useState('')
  const [chWaCost, setChWaCost] = useState('')
  const [chSubmitting, setChSubmitting] = useState(false)
  const [chMsg, setChMsg] = useState('')

  useEffect(() => {
    load()
  }, [])

  async function load() {
    setLoadErr('')
    try {
      const [r, c, l] = await Promise.all([
        actions.listRules(),
        actions.listChannels(),
        actions.listLog(),
      ])
      setRules(r)
      setChannels(c)
      setLog(l)
    } catch (e: unknown) {
      setLoadErr(e instanceof Error ? e.message : String(e))
    }
  }

  async function handleCreateRule(e: React.FormEvent) {
    e.preventDefault()
    if (!ruleName.trim()) return
    setRuleSubmitting(true)
    setRuleMsg('')
    try {
      const payload: Parameters<typeof actions.createRule>[0] = {
        rule_type: ruleType,
        name: ruleName.trim(),
      }
      if (ruleType === 'threshold') {
        if (ruleThreshold) payload.threshold_value = Number(ruleThreshold)
        if (ruleWindow) payload.window_minutes = Number(ruleWindow)
      }
      const r = await actions.createRule(payload)
      setRules(prev => [...prev, r])
      setRuleMsg(`Regla "${r.name}" creada.`)
      setRuleName('')
      setRuleThreshold('')
      setRuleWindow('')
    } catch (e: unknown) {
      setRuleMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setRuleSubmitting(false)
    }
  }

  async function handleDeleteRule(id: string, name: string) {
    if (!confirm(`¿Eliminar regla "${name}"?`)) return
    try {
      await actions.deleteRule(id)
      setRules(prev => prev.filter(r => r.id !== id))
    } catch (e: unknown) {
      setRuleMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  async function handleCreateChannel(e: React.FormEvent) {
    e.preventDefault()
    if (!chName.trim() || !chConfig.trim()) return
    if (chType === 'whatsapp' && !chWaCost.trim()) return
    setChSubmitting(true)
    setChMsg('')
    try {
      let config: Record<string, unknown>
      try {
        config = JSON.parse(chConfig)
      } catch {
        setChMsg('Error: la configuración debe ser JSON válido.')
        setChSubmitting(false)
        return
      }
      const payload: Parameters<typeof actions.createChannel>[0] = {
        channel_type: chType,
        name: chName.trim(),
        config,
      }
      if (chType === 'whatsapp') {
        payload.whatsapp_cost_per_conversation_usd = parseFloat(chWaCost)
      }
      const c = await actions.createChannel(payload)
      setChannels(prev => [...prev, c])
      setChMsg(`Canal "${c.name}" creado.`)
      setChName('')
      setChConfig('')
      setChWaCost('')
    } catch (e: unknown) {
      setChMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally {
      setChSubmitting(false)
    }
  }

  async function handleDeleteChannel(id: string, name: string) {
    if (!confirm(`¿Eliminar canal "${name}"?`)) return
    try {
      await actions.deleteChannel(id)
      setChannels(prev => prev.filter(c => c.id !== id))
    } catch (e: unknown) {
      setChMsg(`Error: ${e instanceof Error ? e.message : String(e)}`)
    }
  }

  return (
    <div>
      <h1 style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>Motor de Acciones</h1>
      <p style={{ color: '#64748b', marginBottom: 20, fontSize: 14 }}>
        Reglas de alerta automática y canales de notificación para tu tenant.
      </p>

      {loadErr && (
        <p style={{ color: '#b91c1c', marginBottom: 16, fontSize: 13 }}>
          Error al cargar: {loadErr}
        </p>
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 24, borderBottom: '1px solid #e2e8f0' }}>
        {(['rules', 'channels', 'log'] as Tab[]).map(t => (
          <button
            key={t}
            data-testid={`actions-tab-${t}`}
            onClick={() => setTab(t)}
            style={{
              padding: '8px 18px', border: 'none', borderRadius: '6px 6px 0 0',
              background: tab === t ? '#0ea5e9' : 'transparent',
              color: tab === t ? '#fff' : '#64748b',
              fontWeight: tab === t ? 600 : 400,
              fontSize: 14, cursor: 'pointer',
            }}
          >
            {t === 'rules' ? 'Reglas' : t === 'channels' ? 'Canales' : 'Log'}
          </button>
        ))}
      </div>

      {/* ── Rules tab ── */}
      {tab === 'rules' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          <div style={cardStyle}>
            <h2 style={h2Style}>Nueva regla</h2>
            <form onSubmit={handleCreateRule}>
              <label style={labelStyle}>Tipo de regla</label>
              <select
                data-testid="rule-type-select"
                value={ruleType}
                onChange={e => setRuleType(e.target.value as RuleType)}
                style={inputStyle}
              >
                {(Object.keys(RULE_TYPE_LABELS) as RuleType[]).map(rt => (
                  <option key={rt} value={rt}>{RULE_TYPE_LABELS[rt]}</option>
                ))}
              </select>

              <label style={labelStyle}>Nombre</label>
              <input
                data-testid="rule-name-input"
                value={ruleName}
                onChange={e => setRuleName(e.target.value)}
                placeholder="ej. Alerta caja > 5 personas"
                required
                style={inputStyle}
              />

              {ruleType === 'threshold' && (
                <>
                  <label style={labelStyle}>Umbral (personas)</label>
                  <input
                    data-testid="rule-threshold-input"
                    type="number"
                    min={1}
                    value={ruleThreshold}
                    onChange={e => setRuleThreshold(e.target.value)}
                    placeholder="ej. 5"
                    style={inputStyle}
                  />
                  <label style={labelStyle}>Ventana (minutos)</label>
                  <input
                    data-testid="rule-window-input"
                    type="number"
                    min={1}
                    value={ruleWindow}
                    onChange={e => setRuleWindow(e.target.value)}
                    placeholder="ej. 10"
                    style={inputStyle}
                  />
                </>
              )}

              <button
                type="submit"
                data-testid="rule-submit-btn"
                disabled={ruleSubmitting}
                style={btnStyle(ruleSubmitting)}
              >
                {ruleSubmitting ? 'Creando…' : 'Crear regla'}
              </button>
            </form>
            {ruleMsg && (
              <p style={msgStyle(ruleMsg)}>{ruleMsg}</p>
            )}
          </div>

          <div style={cardStyle}>
            <h2 style={h2Style}>Reglas activas</h2>
            {rules.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: 14 }}>Sin reglas. Crea la primera.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {rules.map(r => (
                  <div key={r.id} data-testid="rule-row" style={rowStyle}>
                    <div>
                      <p style={{ fontWeight: 600, fontSize: 14 }}>{r.name}</p>
                      <p style={{ fontSize: 12, color: '#64748b' }}>
                        {RULE_TYPE_LABELS[r.rule_type]}
                        {r.threshold_value != null && ` · umbral ${r.threshold_value}`}
                        {r.window_minutes != null && ` · ${r.window_minutes} min`}
                      </p>
                    </div>
                    <button
                      data-testid="rule-delete-btn"
                      onClick={() => handleDeleteRule(r.id, r.name)}
                      style={deleteBtnStyle}
                    >
                      Eliminar
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Channels tab ── */}
      {tab === 'channels' && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
          <div style={cardStyle}>
            <h2 style={h2Style}>Nuevo canal</h2>
            <form onSubmit={handleCreateChannel}>
              <label style={labelStyle}>Tipo de canal</label>
              <select
                data-testid="channel-type-select"
                value={chType}
                onChange={e => setChType(e.target.value as ChannelType)}
                style={inputStyle}
              >
                {(Object.keys(CHANNEL_TYPE_LABELS) as ChannelType[]).map(ct => (
                  <option key={ct} value={ct}>{CHANNEL_TYPE_LABELS[ct]}</option>
                ))}
              </select>

              <label style={labelStyle}>Nombre</label>
              <input
                data-testid="channel-name-input"
                value={chName}
                onChange={e => setChName(e.target.value)}
                placeholder="ej. Alertas Slack #ops"
                required
                style={inputStyle}
              />

              <label style={labelStyle}>Configuración (JSON)</label>
              <textarea
                data-testid="channel-config-input"
                value={chConfig}
                onChange={e => setChConfig(e.target.value)}
                placeholder={
                  chType === 'slack'    ? '{"webhook_url":"https://hooks.slack.com/..."}' :
                  chType === 'telegram' ? '{"bot_token":"...","chat_id":"..."}' :
                  chType === 'email'    ? '{"smtp_host":"smtp.example.com","to":"ops@co.com"}' :
                                         '{"phone_number_id":"...","access_token":"..."}'
                }
                required
                rows={3}
                style={{ ...inputStyle, fontFamily: 'monospace', fontSize: 12 }}
              />

              {/* WhatsApp: cost declaration is mandatory before submit is enabled */}
              {chType === 'whatsapp' && (
                <div
                  data-testid="whatsapp-cost-section"
                  style={{
                    background: '#fff7ed', border: '1px solid #fed7aa',
                    borderRadius: 8, padding: 12, marginTop: 12,
                  }}
                >
                  <p style={{ fontSize: 13, color: '#92400e', marginBottom: 8 }}>
                    <strong>WhatsApp tiene costo por conversación.</strong> Debes declarar el
                    costo antes de activar este canal.
                  </p>
                  <label style={labelStyle}>Costo por conversación (USD)</label>
                  <input
                    data-testid="whatsapp-cost-input"
                    type="number"
                    step="0.0001"
                    min="0"
                    value={chWaCost}
                    onChange={e => setChWaCost(e.target.value)}
                    placeholder="ej. 0.0630"
                    required={chType === 'whatsapp'}
                    style={inputStyle}
                  />
                </div>
              )}

              <button
                type="submit"
                data-testid="channel-submit-btn"
                disabled={chSubmitting || (chType === 'whatsapp' && !chWaCost.trim())}
                style={btnStyle(chSubmitting || (chType === 'whatsapp' && !chWaCost.trim()))}
              >
                {chSubmitting ? 'Creando…' : 'Crear canal'}
              </button>
            </form>
            {chMsg && <p style={msgStyle(chMsg)}>{chMsg}</p>}
          </div>

          <div style={cardStyle}>
            <h2 style={h2Style}>Canales activos</h2>
            {channels.length === 0 ? (
              <p style={{ color: '#94a3b8', fontSize: 14 }}>Sin canales. Crea el primero.</p>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                {channels.map(c => (
                  <div key={c.id} data-testid="channel-row" style={rowStyle}>
                    <div>
                      <p style={{ fontWeight: 600, fontSize: 14 }}>{c.name}</p>
                      <p style={{ fontSize: 12, color: '#64748b' }}>
                        {CHANNEL_TYPE_LABELS[c.channel_type]}
                        {c.whatsapp_cost_per_conversation_usd != null &&
                          ` · $${c.whatsapp_cost_per_conversation_usd.toFixed(4)}/conv`}
                      </p>
                    </div>
                    <button
                      data-testid="channel-delete-btn"
                      onClick={() => handleDeleteChannel(c.id, c.name)}
                      style={deleteBtnStyle}
                    >
                      Eliminar
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Log tab ── */}
      {tab === 'log' && (
        <div style={cardStyle}>
          <h2 style={h2Style}>Log de acciones disparadas</h2>
          {log.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: 14 }}>Sin acciones registradas todavía.</p>
          ) : (
            <table data-testid="actions-log-table" style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#f8fafc' }}>
                  {['Fecha', 'Canal', 'Estado', 'Resumen', 'Costo'].map(h => (
                    <th key={h} style={{ textAlign: 'left', padding: '8px 12px', borderBottom: '1px solid #e2e8f0', fontWeight: 600 }}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {log.map(entry => (
                  <tr key={entry.id} data-testid="log-row">
                    <td style={tdStyle}>{new Date(entry.triggered_at).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' })}</td>
                    <td style={tdStyle}>{CHANNEL_TYPE_LABELS[entry.channel_type]}</td>
                    <td style={tdStyle}>
                      <span style={{
                        padding: '2px 8px', borderRadius: 99, fontSize: 11,
                        background: entry.status === 'sent' ? '#dcfce7' : '#fee2e2',
                        color: entry.status === 'sent' ? '#166534' : '#b91c1c',
                      }}>
                        {entry.status}
                      </span>
                    </td>
                    <td style={tdStyle}>{entry.payload_summary}</td>
                    <td style={tdStyle}>
                      {entry.meta_cost_usd != null
                        ? `$${entry.meta_cost_usd.toFixed(4)}`
                        : <span style={{ color: '#94a3b8' }}>—</span>}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

// ── Shared styles ──────────────────────────────────────────────────────────────

const cardStyle: React.CSSProperties = {
  background: '#fff', borderRadius: 12, padding: 24,
  boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
}

const h2Style: React.CSSProperties = {
  fontSize: 16, fontWeight: 600, marginBottom: 20,
}

const labelStyle: React.CSSProperties = {
  display: 'block', fontSize: 12, color: '#64748b', marginBottom: 4, marginTop: 14,
}

const inputStyle: React.CSSProperties = {
  width: '100%', padding: '8px 10px', border: '1px solid #e2e8f0',
  borderRadius: 6, fontSize: 14, boxSizing: 'border-box',
}

const btnStyle = (disabled: boolean): React.CSSProperties => ({
  marginTop: 20, width: '100%', padding: '11px',
  background: disabled ? '#94a3b8' : '#0ea5e9',
  color: '#fff', border: 'none', borderRadius: 8,
  fontSize: 15, fontWeight: 600,
  cursor: disabled ? 'not-allowed' : 'pointer',
})

const msgStyle = (msg: string): React.CSSProperties => ({
  marginTop: 14, fontSize: 13,
  color: msg.startsWith('Error') ? '#ef4444' : '#16a34a',
})

const rowStyle: React.CSSProperties = {
  border: '1px solid #e2e8f0', borderRadius: 8, padding: '10px 14px',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
}

const deleteBtnStyle: React.CSSProperties = {
  padding: '5px 12px', background: '#fef2f2', color: '#b91c1c',
  border: '1px solid #fecaca', borderRadius: 6, fontSize: 12, cursor: 'pointer',
}

const tdStyle: React.CSSProperties = {
  padding: '8px 12px', borderBottom: '1px solid #f1f5f9',
}
