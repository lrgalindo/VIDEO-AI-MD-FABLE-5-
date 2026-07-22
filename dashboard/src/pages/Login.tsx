/**
 * Login page — email + password form that calls POST /v1/auth/login.
 * If Supabase returns mfa_required (401), shows the TOTP second-factor step.
 */
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

type Step = 'credentials' | 'mfa'

interface MfaContext {
  factor_id: string
  challenge_id: string
}

const API_BASE = '/v1'

export function Login() {
  const [step, setStep] = useState<Step>('credentials')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [totp, setTotp] = useState('')
  const [mfaCtx, setMfaCtx] = useState<MfaContext | null>(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const nav = useNavigate()

  async function handleCredentials(e: React.FormEvent) {
    e.preventDefault()
    if (!email.trim() || !password) { setError('Ingresa email y contraseña'); return }
    setError('')
    setLoading(true)

    try {
      const resp = await fetch(`${API_BASE}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      })

      const data = await resp.json()

      if (resp.status === 401 && data?.detail?.code === 'mfa_required') {
        const factors: Array<{ id: string }> = data.detail.factors ?? []
        const challenge = data.detail.amr_challenge ?? {}
        setMfaCtx({
          factor_id: factors[0]?.id ?? '',
          challenge_id: challenge.id ?? '',
        })
        setStep('mfa')
        return
      }

      if (!resp.ok) {
        setError(data?.detail?.message ?? data?.detail ?? 'Error de autenticación')
        return
      }

      // Successful login — data is the Supabase session or our JWT wrapper
      const token = data.access_token
      if (!token) { setError('Respuesta inesperada del servidor'); return }
      localStorage.setItem('traxia_token', token)
      nav('/', { replace: true })
    } catch {
      setError('No se pudo conectar con el servidor')
    } finally {
      setLoading(false)
    }
  }

  async function handleMfa(e: React.FormEvent) {
    e.preventDefault()
    if (!totp.trim() || totp.trim().length !== 6) { setError('Código TOTP de 6 dígitos requerido'); return }
    if (!mfaCtx) return
    setError('')
    setLoading(true)

    try {
      const resp = await fetch(`${API_BASE}/auth/mfa/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          factor_id: mfaCtx.factor_id,
          challenge_id: mfaCtx.challenge_id,
          code: totp.trim(),
        }),
      })

      const data = await resp.json()

      if (!resp.ok) {
        setError(data?.detail ?? 'Código TOTP incorrecto')
        return
      }

      const token = data.access_token
      if (!token) { setError('Respuesta inesperada del servidor'); return }
      localStorage.setItem('traxia_token', token)
      nav('/', { replace: true })
    } catch {
      setError('No se pudo conectar con el servidor')
    } finally {
      setLoading(false)
    }
  }

  const card: React.CSSProperties = {
    background: '#fff', padding: 40, borderRadius: 12,
    boxShadow: '0 4px 24px rgba(0,0,0,0.08)', width: 400,
  }
  const input: React.CSSProperties = {
    width: '100%', padding: '10px 12px', border: '1px solid #e2e8f0',
    borderRadius: 8, fontSize: 14, marginBottom: 16, boxSizing: 'border-box',
  }
  const btn: React.CSSProperties = {
    width: '100%', padding: '12px', background: loading ? '#94a3b8' : '#0ea5e9',
    color: '#fff', border: 'none', borderRadius: 8,
    fontSize: 15, fontWeight: 600, cursor: loading ? 'not-allowed' : 'pointer',
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center',
      justifyContent: 'center', background: '#f8fafc',
    }}>
      {step === 'credentials' ? (
        <form onSubmit={handleCredentials} data-testid="login-form" style={card}>
          <h1 style={{ fontSize: 24, fontWeight: 700, marginBottom: 8, color: '#1e293b' }}>
            Traxia Analytics
          </h1>
          <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
            Ingresa tu email y contraseña para continuar.
          </p>

          <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
            Email
          </label>
          <input
            data-testid="email-input"
            type="email"
            value={email}
            onChange={e => setEmail(e.target.value)}
            placeholder="usuario@empresa.com"
            autoComplete="email"
            style={{ ...input, marginTop: 4 }}
          />

          <label style={{ fontSize: 13, fontWeight: 500, color: '#374151' }}>
            Contraseña
          </label>
          <input
            data-testid="password-input"
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="••••••••"
            autoComplete="current-password"
            style={{ ...input, marginTop: 4 }}
          />

          {error && (
            <p style={{ color: '#ef4444', fontSize: 13, marginBottom: 12 }} data-testid="login-error">
              {error}
            </p>
          )}

          <button type="submit" data-testid="login-submit" style={btn} disabled={loading}>
            {loading ? 'Verificando…' : 'Iniciar sesión'}
          </button>
        </form>
      ) : (
        <form onSubmit={handleMfa} data-testid="mfa-form" style={card}>
          <h1 style={{ fontSize: 20, fontWeight: 700, marginBottom: 8, color: '#1e293b' }}>
            Verificación en dos pasos
          </h1>
          <p style={{ color: '#64748b', marginBottom: 24, fontSize: 14 }}>
            Ingresa el código de 6 dígitos de tu aplicación de autenticación.
          </p>

          <input
            data-testid="totp-input"
            type="text"
            inputMode="numeric"
            maxLength={6}
            value={totp}
            onChange={e => setTotp(e.target.value.replace(/\D/g, ''))}
            placeholder="123456"
            autoComplete="one-time-code"
            style={{ ...input, fontSize: 24, letterSpacing: 8, textAlign: 'center' }}
          />

          {error && (
            <p style={{ color: '#ef4444', fontSize: 13, marginBottom: 12 }} data-testid="login-error">
              {error}
            </p>
          )}

          <button type="submit" data-testid="mfa-submit" style={btn} disabled={loading}>
            {loading ? 'Verificando…' : 'Confirmar'}
          </button>
          <button
            type="button"
            data-testid="mfa-back"
            onClick={() => { setStep('credentials'); setError('') }}
            style={{ ...btn, background: 'transparent', color: '#64748b', marginTop: 8 }}
          >
            Volver
          </button>
        </form>
      )}
    </div>
  )
}
