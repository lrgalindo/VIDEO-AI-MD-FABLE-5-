"""Server-side context resolution for the Copiloto (SDD §12.2 / §12.4).

The ONLY source of truth for what data a user is allowed to see is the JWT
already verified by _require_user(), propagated into the DB session via
user_conn() and enforced by RLS.

Context is NEVER derived from any parameter the client sends — the tenant_id,
role, partner_id, and site_ids all come exclusively from the verified token.

This module queries the RLS-filtered view of the DB to build the data context
that will be embedded in the system prompt for Claude. Because every query here
runs through user_conn(token), RLS acts as a second enforcement layer even if
the prompt-building logic has a bug.
"""

from typing import Any, Dict, List, Optional
import psycopg2.extras

from cloud.db import user_conn


def resolve_authorized_zones(token: dict) -> List[Dict[str, Any]]:
    """Return the zones the authenticated user is allowed to see.

    Runs under user_conn(token) — RLS filters automatically:
    - Tenant admin: all zones owned by their tenant + all partner zones under them
    - Operator: zones for their assigned sites only
    - Partner viewer: only zones owned by their partner_id
    """
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT z.id::text, z.name, z.zone_type, z.owner_type,
                   s.id::text AS site_id, s.name AS site_name,
                   c.id::text AS camera_id
            FROM zones z
            JOIN cameras c ON c.id = z.camera_id
            JOIN sites s ON s.id = c.site_id
            ORDER BY s.name, z.name
            """
        )
        return [dict(r) for r in cur.fetchall()]


def resolve_recent_zone_metrics(token: dict, zone_ids: List[str]) -> List[Dict[str, Any]]:
    """Return dwell time metrics for the last 24h for authorized zones."""
    if not zone_ids:
        return []
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT
                z.id::text AS zone_id,
                z.name AS zone_name,
                COUNT(DISTINCT zds.person_id)          AS unique_visitors_24h,
                AVG(zds.dwell_seconds)::int            AS avg_dwell_seconds,
                MAX(zds.dwell_seconds)                 AS max_dwell_seconds,
                COUNT(zds.id)                          AS total_sessions_24h
            FROM zones z
            LEFT JOIN zone_dwell_sessions zds
                ON zds.zone_id = z.id
               AND zds.entered_at >= now() - interval '24 hours'
            WHERE z.id = ANY(%s::uuid[])
            GROUP BY z.id, z.name
            ORDER BY z.name
            """,
            (zone_ids,),
        )
        return [dict(r) for r in cur.fetchall()]


def resolve_recent_findings(token: dict) -> List[Dict[str, Any]]:
    """Return the 5 most recent agent_findings visible to this user."""
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT id::text, task_type, summary, created_at::text
            FROM agent_findings
            ORDER BY created_at DESC
            LIMIT 5
            """
        )
        return [dict(r) for r in cur.fetchall()]


def build_data_context(token: dict) -> Dict[str, Any]:
    """Assemble the full authorized data context for the Copiloto system prompt."""
    zones = resolve_authorized_zones(token)
    zone_ids = [z["id"] for z in zones]
    metrics = resolve_recent_zone_metrics(token, zone_ids)
    findings = resolve_recent_findings(token)

    return {
        "role": token.get("role", "viewer"),
        "tenant_id": token.get("tid"),
        "partner_id": token.get("pid"),
        "authorized_zone_ids": zone_ids,
        "authorized_zones": zones,
        "zone_metrics_24h": metrics,
        "recent_findings": findings,
    }
