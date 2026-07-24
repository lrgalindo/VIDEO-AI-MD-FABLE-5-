import { useMemo } from 'react'
import type { UserToken } from '../types'

function parseJwt(token: string): UserToken | null {
  try {
    const payload = token.split('.')[1]
    // JWTs use base64url — convert to standard base64 before atob
    const b64 = payload.replace(/-/g, '+').replace(/_/g, '/')
    return JSON.parse(atob(b64)) as UserToken
  } catch {
    return null
  }
}

export function useAuth() {
  const raw = localStorage.getItem('traxia_token') ?? ''
  const token = useMemo(() => parseJwt(raw), [raw])

  const isPartner = Boolean(token?.pid)
  const role = token?.role ?? null
  const tenantId = token?.tid ?? null

  return {
    token,
    raw,
    role,
    tenantId,
    isPartner,
    isAdmin: role === 'admin' && !isPartner,
    isOperator: role === 'operator' && !isPartner,
    isViewer: role === 'viewer' && !isPartner,
    isPartnerAdmin: role === 'admin' && isPartner,
    isPartnerViewer: isPartner,
    isAuthenticated: token != null && token.exp > Date.now() / 1000,
  }
}
