export interface UserToken {
  sub: string       // user_id
  tid: string       // tenant_id
  role: 'admin' | 'operator' | 'viewer'
  pid?: string      // partner_id — present only for partner-scoped tokens
  sids?: string[]   // site_ids — present for operator/viewer
  exp: number
  iat: number
}

export interface SiteTrafficDay {
  site_id: string
  day: string
  unique_visitors: number
  total_detections: number
}

export interface SiteTrafficWeek {
  site_id: string
  site_name: string
  week: string
  unique_visitors: number
}

export interface ZoneDwellDay {
  zone_id: string
  zone_name: string
  zone_type: string
  site_id: string
  day: string
  sessions: number
  avg_dwell_seconds: number
  max_dwell_seconds: number
}

export interface Site {
  id: string
  name: string
  status: string
}

export interface Camera {
  id: string
  site_id: string
  name: string
  status: string
}

export interface Zone {
  id: string
  camera_id: string
  owner_type: 'TENANT' | 'PARTNER'
  name: string
  zone_type: string
  coordinates: Record<string, unknown>
}

export interface UserListItem {
  id: string
  email: string
  role: string
  status: string
  site_count?: number
}

export interface PartnerResponse {
  id: string
  name: string
  contact_email: string
  status: 'active' | 'inactive'
  access_expires_at?: string
}

export type ZoneType = 'shelf' | 'entrance' | 'exit' | 'checkout' | 'staff_exclusion' | 'generic'

export interface Polygon {
  points: [number, number][]
}

// ── Motor de Acciones ─────────────────────────────────────────────────────────

export type RuleType =
  | 'threshold'
  | 'sop_staff_absent_checkout'
  | 'sop_late_opening'
  | 'sop_unattended_customer'

export type ChannelType = 'slack' | 'telegram' | 'email' | 'whatsapp'

export interface ActionRule {
  id: string
  rule_type: RuleType
  name: string
  zone_id?: string
  threshold_value?: number
  window_minutes?: number
  enabled: boolean
  created_at: string
}

export interface ActionChannel {
  id: string
  channel_type: ChannelType
  name: string
  enabled: boolean
  whatsapp_cost_per_conversation_usd?: number
  created_at: string
}

export interface ActionLogEntry {
  id: string
  rule_id: string
  channel_type: ChannelType
  status: 'sent' | 'failed'
  payload_summary: string
  meta_cost_usd?: number
  triggered_at: string
}

// ── Copiloto ──────────────────────────────────────────────────────────────────

export interface ChatResponse {
  answer: string
  authorized_zone_count: number
  model: string
}

// ── Agent Findings ────────────────────────────────────────────────────────────

export type FindingTaskType = 'stock_audit' | 'dwell_drop' | 'copilot_audit'

export interface AgentFinding {
  id: string
  task_type: FindingTaskType
  zone_id?: string
  summary: string
  detail: {
    recent_avg_dwell?: number
    baseline_avg_dwell?: number
    vision_finding?: string
    snapshot_available?: boolean
    // snapshot_r2_key is intentionally absent — the server strips it
    // and replaces it with snapshot_url (presigned URL or null)
  }
  snapshot_url?: string   // presigned R2 URL (short-lived); null if R2 unconfigured
  created_at: string
}
