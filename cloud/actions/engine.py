"""Action Engine — batch/polling rule evaluator (SDD §12.10).

Evaluation cadence: same CHECK_INTERVAL_SECONDS as the Motor Matemático (60s
in dev; 1-5 min configurable in prod via the scheduler).  No streaming.

Rule types:
  threshold               — N or more people in zone for window_minutes
  sop_staff_absent_checkout — zero staff in checkout zone during business hours
  sop_late_opening        — no detection in site after business_hours_start + window
  sop_unattended_customer — person in zone > window_minutes without exit

Isolation guarantee:
  The evaluation of each rule runs inside admin_conn_for_tenant(rule.tenant_id),
  which sets app.current_tenant_id via SET LOCAL.  The RLS policies on
  zone_dwell_sessions (zone_dwell_sessions_isolation) and tracking_coordinates
  (tracking_coordinates_isolation) enforce that only rows owned by that tenant
  are visible — even if a rule's zone_id belongs to another tenant, no rows
  are returned (the zone's owner_tenant_id check fails).  Cross-tenant data
  leakage is structurally impossible without RLS bypass.

The batch scan uses the superuser connection (postgres owner) to read all
enabled rules across all tenants — the same split used by the revocation
scheduler (backoffice/scheduler.py).  Writes (action_log INSERTs) go through
traxia_service which has blanket INSERT on action_log.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from cloud import config
from cloud.actions.channels import dispatch
from cloud.db import admin_conn_for_tenant, service_conn

log = logging.getLogger(__name__)


# ── Cross-tenant scan (superuser connection) ──────────────────────────────────

def _find_enabled_rules() -> List[Dict[str, Any]]:
    """Return all enabled rules across all tenants. Runs as DB owner (no RLS)."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        ar.id::text                 AS id,
                        ar.tenant_id::text          AS tenant_id,
                        ar.site_id::text            AS site_id,
                        ar.zone_id::text            AS zone_id,
                        ar.name,
                        ar.rule_type,
                        ar.threshold_value,
                        ar.threshold_window_minutes,
                        ar.business_hours_start,
                        ar.business_hours_end
                    FROM action_rules ar
                    WHERE ar.enabled = TRUE
                    ORDER BY ar.tenant_id, ar.id
                    """
                )
                return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _find_channels_for_rule(rule_id: str) -> List[Dict[str, Any]]:
    """Return all enabled channels bound to a rule. Runs as DB owner."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        ac.id::text                              AS id,
                        ac.channel_type,
                        ac.config_json,
                        ac.whatsapp_cost_per_conversation_usd   AS whatsapp_cost
                    FROM action_rule_channels arc
                    JOIN action_channels ac ON ac.id = arc.channel_id
                    WHERE arc.rule_id = %s
                      AND ac.enabled = TRUE
                    """,
                    (rule_id,),
                )
                return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ── Per-tenant evaluation (RLS-enforced) ─────────────────────────────────────

def _evaluate_threshold(cur: psycopg2.extras.RealDictCursor, rule: Dict) -> bool:
    """True when person_count in zone >= threshold_value for the last window_minutes.

    Query runs under app_current_tenant_id = rule.tenant_id via admin_conn_for_tenant.
    zone_dwell_sessions_isolation RLS: only rows where zone.owner_tenant_id
    matches are visible — cross-tenant zone_ids return zero rows.
    """
    if not rule["zone_id"] or rule["threshold_value"] is None:
        return False
    window = rule["threshold_window_minutes"] or 5
    cur.execute(
        """
        SELECT COUNT(DISTINCT zds.person_id) AS cnt
        FROM zone_dwell_sessions zds
        WHERE zds.zone_id = %s
          AND zds.exited_at IS NULL
          AND zds.entered_at <= now() - (%s || ' minutes')::interval
        """,
        (rule["zone_id"], str(window)),
    )
    row = cur.fetchone()
    count = row["cnt"] if row else 0
    return count >= rule["threshold_value"]


def _evaluate_sop_staff_absent(cur: psycopg2.extras.RealDictCursor, rule: Dict) -> bool:
    """True when no staff in checkout zone for window_minutes during business hours."""
    if not rule["zone_id"]:
        return False
    bh_start = rule["business_hours_start"]
    bh_end = rule["business_hours_end"]
    if bh_start and bh_end:
        cur.execute("SELECT localtime::time AS t")
        now_t = cur.fetchone()["t"]
        if not (bh_start <= now_t <= bh_end):
            return False  # outside business hours — rule does not apply
    window = rule["threshold_window_minutes"] or 15
    cur.execute(
        """
        SELECT COUNT(DISTINCT zds.person_id) AS cnt
        FROM zone_dwell_sessions zds
        WHERE zds.zone_id = %s
          AND zds.exited_at IS NULL
          AND zds.entered_at >= now() - (%s || ' minutes')::interval
        """,
        (rule["zone_id"], str(window)),
    )
    row = cur.fetchone()
    return (row["cnt"] if row else 0) == 0


def _evaluate_sop_late_opening(cur: psycopg2.extras.RealDictCursor, rule: Dict) -> bool:
    """True when no person detected in site after business_hours_start + window_minutes."""
    if not rule["site_id"] or not rule["business_hours_start"]:
        return False
    bh_start = rule["business_hours_start"]
    window = rule["threshold_window_minutes"] or 15
    # Only relevant after the grace window has elapsed
    cur.execute("SELECT localtime::time AS t, current_date AS d")
    row = cur.fetchone()
    now_t = row["t"]
    today = row["d"]
    # Convert bh_start (datetime.time) to comparable
    from datetime import timedelta
    import datetime as dt
    bh_start_plus_window = (
        dt.datetime.combine(today, bh_start) + timedelta(minutes=window)
    ).time()
    if now_t < bh_start_plus_window:
        return False  # grace window hasn't elapsed yet
    if rule["business_hours_end"] and now_t > rule["business_hours_end"]:
        return False  # too late in the day to be a "late opening" alert
    # Check for any detection since business_hours_start today
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM tracking_coordinates tc
        JOIN cameras c ON c.id = tc.camera_id
        WHERE c.site_id = %s
          AND tc.time >= (current_date + %s::time)
          AND tc.time <= now()
        """,
        (rule["site_id"], bh_start),
    )
    r = cur.fetchone()
    return (r["cnt"] if r else 0) == 0


def _evaluate_sop_unattended_customer(cur: psycopg2.extras.RealDictCursor, rule: Dict) -> bool:
    """True when any person has been in zone > threshold_window_minutes without exiting."""
    if not rule["zone_id"]:
        return False
    window = rule["threshold_window_minutes"] or 10
    cur.execute(
        """
        SELECT COUNT(DISTINCT zds.person_id) AS cnt
        FROM zone_dwell_sessions zds
        WHERE zds.zone_id = %s
          AND zds.exited_at IS NULL
          AND zds.entered_at <= now() - (%s || ' minutes')::interval
        """,
        (rule["zone_id"], str(window)),
    )
    row = cur.fetchone()
    return (row["cnt"] if row else 0) > 0


_EVALUATORS = {
    "threshold": _evaluate_threshold,
    "sop_staff_absent_checkout": _evaluate_sop_staff_absent,
    "sop_late_opening": _evaluate_sop_late_opening,
    "sop_unattended_customer": _evaluate_sop_unattended_customer,
}


def _build_message(rule: Dict, triggered: bool) -> str:
    templates = {
        "threshold":
            f"[Traxia] Alerta: umbral superado en zona ({rule['name']}). "
            f"Se detectaron ≥{rule['threshold_value']} personas.",
        "sop_staff_absent_checkout":
            f"[Traxia] SOP: Personal ausente en zona de caja ({rule['name']}) "
            f"por más de {rule['threshold_window_minutes']} minutos durante horario de negocio.",
        "sop_late_opening":
            f"[Traxia] SOP: Apertura tardía detectada — sin actividad en sede "
            f"({rule['name']}) en los primeros {rule['threshold_window_minutes']} min del horario.",
        "sop_unattended_customer":
            f"[Traxia] SOP: Cliente sin atender en zona ({rule['name']}) "
            f"por más de {rule['threshold_window_minutes']} minutos.",
    }
    return templates.get(rule["rule_type"], f"[Traxia] Regla disparada: {rule['name']}")


def _log_dispatch(
    rule: Dict,
    channel: Dict,
    status: str,
    payload_summary: str,
    meta_cost: Optional[float],
    error: Optional[str],
) -> None:
    with service_conn() as cur:
        cur.execute(
            """
            INSERT INTO action_log
                (rule_id, tenant_id, site_id, channel_id,
                 status, payload_summary, meta_cost_usd, error_detail)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                rule["id"],
                rule["tenant_id"],
                rule.get("site_id"),
                channel["id"],
                status,
                payload_summary[:500] if payload_summary else None,
                meta_cost,
                error,
            ),
        )


def evaluate_rule(rule: Dict) -> None:
    """Evaluate one rule in the context of its own tenant (RLS-enforced).

    admin_conn_for_tenant sets app.current_tenant_id = rule.tenant_id via
    SET LOCAL, which satisfies the zone_dwell_sessions_isolation and
    tracking_coordinates_isolation RLS policies.  A rule's zone_id pointing
    to another tenant's zone will return zero rows — not an error, just no
    trigger — because the zones table lookup in the policy's EXISTS clause
    will fail the owner_tenant_id check.
    """
    evaluator = _EVALUATORS.get(rule["rule_type"])
    if evaluator is None:
        log.error("Unknown rule_type %s for rule %s", rule["rule_type"], rule["id"])
        return

    try:
        with admin_conn_for_tenant(rule["tenant_id"]) as cur:
            triggered = evaluator(cur, rule)
    except Exception as exc:
        log.error("Rule evaluation error rule=%s: %s", rule["id"], exc)
        return

    if not triggered:
        return

    log.info("Rule triggered: %s (%s)", rule["name"], rule["id"])
    message = _build_message(rule, triggered=True)
    channels = _find_channels_for_rule(rule["id"])

    if not channels:
        log.info("Rule %s triggered but no channels configured", rule["id"])
        return

    for ch in channels:
        try:
            ok, meta_cost = dispatch(
                channel_type=ch["channel_type"],
                config=ch["config_json"],
                message=message,
                subject=f"Traxia: {rule['name']}",
                whatsapp_cost_per_conversation=ch.get("whatsapp_cost"),
            )
            _log_dispatch(
                rule=rule,
                channel=ch,
                status="sent" if ok else "failed",
                payload_summary=message,
                meta_cost=meta_cost,
                error=None if ok else "dispatch returned False",
            )
        except Exception as exc:
            log.error("Channel dispatch error channel=%s rule=%s: %s", ch["id"], rule["id"], exc)
            try:
                _log_dispatch(
                    rule=rule,
                    channel=ch,
                    status="failed",
                    payload_summary=message,
                    meta_cost=None,
                    error=str(exc)[:500],
                )
            except Exception:
                pass


def run_evaluation_cycle() -> None:
    """Evaluate all enabled rules. Called by the scheduler on each tick."""
    try:
        rules = _find_enabled_rules()
    except Exception as exc:
        log.error("Failed to load enabled rules: %s", exc)
        return

    for rule in rules:
        evaluate_rule(rule)
