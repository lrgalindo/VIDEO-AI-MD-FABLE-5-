/**
 * Typed API client for the Traxia Cloud API.
 * All requests include the user JWT from localStorage.
 * Responses that return 401 trigger a redirect to /login.
 */
import type {
  SiteTrafficDay, SiteTrafficWeek, ZoneDwellDay,
  Site, Camera, Zone, UserListItem, PartnerResponse,
  ActionRule, ActionChannel, ActionLogEntry, ChannelType,
  ChatResponse, AgentFinding,
} from '../types'

const BASE = import.meta.env.VITE_API_URL ?? ''

function getToken(): string {
  return localStorage.getItem('traxia_token') ?? ''
}

async function req<T>(
  method: string,
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${getToken()}`,
    },
    body: body != null ? JSON.stringify(body) : undefined,
  })
  if (res.status === 401) {
    localStorage.removeItem('traxia_token')
    window.location.href = '/login'
    throw new Error('unauthenticated')
  }
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail ?? res.statusText)
  }
  if (res.status === 204) return undefined as T
  return res.json()
}

// ── Analytics endpoints (new, added in analytics router) ──────────────────────

export const analytics = {
  trafficDaily: (siteId?: string) =>
    req<SiteTrafficDay[]>('GET', `/v1/analytics/traffic${siteId ? `?site_id=${siteId}` : ''}`),

  trafficComparison: () =>
    req<SiteTrafficWeek[]>('GET', '/v1/analytics/comparison'),

  dwellSummary: () =>
    req<ZoneDwellDay[]>('GET', '/v1/analytics/dwell'),
}

// ── Sites / Cameras / Zones ────────────────────────────────────────────────────

export const sites = {
  list: () => req<Site[]>('GET', '/v1/sites'),
}

export const cameras = {
  bySite: (siteId: string) => req<Camera[]>('GET', `/v1/cameras?site_id=${siteId}`),
  snapshot: (cameraId: string) => `${BASE}/v1/cameras/${cameraId}/snapshot`,
}

export const zones = {
  list: (cameraId: string) => req<Zone[]>('GET', `/v1/zones?camera_id=${cameraId}`),
  create: (payload: {
    camera_id: string
    name: string
    zone_type: string
    coordinates: Record<string, unknown>
  }) => req<Zone>('POST', '/v1/zones', payload),
}

// ── Motor de Acciones ─────────────────────────────────────────────────────────

export const actions = {
  listRules: () => req<ActionRule[]>('GET', '/v1/actions/rules'),

  createRule: (payload: {
    rule_type: string
    name: string
    zone_id?: string
    threshold_value?: number
    window_minutes?: number
  }) => req<ActionRule>('POST', '/v1/actions/rules', payload),

  deleteRule: (ruleId: string) =>
    req<void>('DELETE', `/v1/actions/rules/${ruleId}`),

  listChannels: () => req<ActionChannel[]>('GET', '/v1/actions/channels'),

  createChannel: (payload: {
    channel_type: ChannelType
    name: string
    config: Record<string, unknown>
    whatsapp_cost_per_conversation_usd?: number
  }) => req<ActionChannel>('POST', '/v1/actions/channels', payload),

  deleteChannel: (channelId: string) =>
    req<void>('DELETE', `/v1/actions/channels/${channelId}`),

  listLog: () => req<ActionLogEntry[]>('GET', '/v1/actions/log'),
}

// ── Copiloto ──────────────────────────────────────────────────────────────────

export const copilot = {
  chat: (question: string) =>
    req<ChatResponse>('POST', '/v1/copilot/chat', { question }),
}

// ── Agent Findings ────────────────────────────────────────────────────────────

export const findings = {
  list: () => req<AgentFinding[]>('GET', '/v1/findings'),
}

// ── Backoffice ─────────────────────────────────────────────────────────────────

export const backoffice = {
  listUsers: () => req<UserListItem[]>('GET', '/v1/backoffice/users'),

  createUser: (payload: {
    email: string
    role: string
    site_ids: string[]
  }) => req<UserListItem>('POST', '/v1/backoffice/users', payload),

  createPartner: (payload: {
    name: string
    contact_email: string
    site_ids: string[]
    access_expires_at?: string
  }) => req<PartnerResponse>('POST', '/v1/backoffice/partners', payload),

  revokePartner: (partnerId: string) =>
    req<{ revoked: string }>('POST', `/v1/backoffice/partners/${partnerId}/revoke`),
}
