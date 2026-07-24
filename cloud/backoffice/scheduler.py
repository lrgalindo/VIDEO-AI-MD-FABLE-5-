"""Partner auto-revocation scheduler (Fase 2).

The revoke_partner() function is the single code path for partner revocation —
it is called by both:
  - The manual endpoint: POST /v1/backoffice/partners/{id}/revoke
  - The background scheduler: runs every CHECK_INTERVAL_SECONDS, finds all
    partners where access_expires_at < now() and status = 'active'

Both paths use admin_conn_for_tenant() which runs as traxia_app with
app.current_actor_role = 'admin', satisfying the partners_update RLS policy:
  app_current_partner_id() IS NULL
  AND app_current_role() = 'admin'
  AND partners.tenant_id = app_current_tenant_id()

This means no RLS bypass occurs — the update goes through the same policy
that a manually-authenticated admin user would hit.

Read/write separation in the scheduler:
  - _find_expired_partners() executes a single SELECT (read-only, superuser
    connection, no transaction writes).
  - revoke_partner() performs the only UPDATE, via admin_conn_for_tenant()
    through RLS.  The two steps are deliberately separate to make the
    read-only scan auditable and to ensure every write goes through the
    policy layer.

Known limitation — horizontal scaling (non-blocking for MLP):
  The scheduler is a daemon thread inside the API process.  With N replicas
  (e.g. Render auto-scale, Cloud Run min-instances > 1), N threads will
  independently scan and attempt to revoke the same expired partners.
  The UPDATE is idempotent (WHERE status = 'active' guards it), so duplicate
  executions produce the same final state and no data corruption occurs.
  However, each replica fires N log lines and N DB round-trips per interval.

  To eliminate duplicate work at scale, replace start_revocation_scheduler()
  with a pg_cron job, an external worker queue (e.g. Cloud Scheduler →
  single Cloud Run job), or a distributed lock (e.g. SELECT FOR UPDATE SKIP
  LOCKED on a scheduler_lock table).  No schema change is required — only
  the trigger mechanism changes; revoke_partner() remains the single code path.
"""

import logging
import threading
import time

import psycopg2
import psycopg2.extras

from cloud import config
from cloud.db import admin_conn_for_tenant

log = logging.getLogger(__name__)

CHECK_INTERVAL_SECONDS: int = 60


def revoke_partner(partner_id: str, tenant_id: str) -> None:
    """Set partner status to inactive — shared by manual and scheduled revocation.

    Runs under admin_conn_for_tenant RLS context so the partners_update policy
    is satisfied without superuser/BYPASSRLS.
    """
    with admin_conn_for_tenant(tenant_id) as cur:
        cur.execute(
            "UPDATE partners SET status = 'inactive' WHERE id = %s AND status = 'active'",
            (partner_id,),
        )
        if cur.rowcount == 0:
            log.debug("revoke_partner: partner %s not found or already inactive", partner_id)
        else:
            log.info("Partner %s revoked (tenant %s)", partner_id, tenant_id)


def _find_expired_partners() -> list:
    """Find all partners with access_expires_at in the past (superuser scan).

    This is a system-level read that needs to see all tenants — it runs as the
    postgres connection owner (not traxia_app) so it sees all rows regardless
    of RLS.  The subsequent revoke_partner() call re-enters RLS per tenant.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id::text AS id, tenant_id::text AS tenant_id
                    FROM partners
                    WHERE status = 'active'
                      AND access_expires_at IS NOT NULL
                      AND access_expires_at < now()
                    """
                )
                return cur.fetchall()
    finally:
        conn.close()


def _run_revocation() -> None:
    """Find and revoke all expired partners, one tenant context per partner."""
    try:
        expired = _find_expired_partners()
    except Exception as exc:
        log.error("revocation scan failed: %s", exc)
        return

    for row in expired:
        try:
            revoke_partner(row["id"], row["tenant_id"])
        except Exception as exc:
            log.error("revoke_partner(%s) failed: %s", row["id"], exc)


def start_revocation_scheduler() -> None:
    """Start the background partner auto-revocation thread.

    The thread is daemonized so it does not block process shutdown.
    It runs _run_revocation() once per CHECK_INTERVAL_SECONDS.
    """
    def _loop() -> None:
        log.info("Partner revocation scheduler started (interval=%ds)", CHECK_INTERVAL_SECONDS)
        while True:
            time.sleep(CHECK_INTERVAL_SECONDS)
            _run_revocation()

    t = threading.Thread(target=_loop, daemon=True, name="partner-revocation")
    t.start()
