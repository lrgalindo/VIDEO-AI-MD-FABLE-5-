from contextlib import contextmanager
from typing import Any, Dict, Generator

import psycopg2
import psycopg2.extras

from cloud import config


@contextmanager
def service_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """Open a connection that immediately sets the role to traxia_service.

    The connection-level SET ROLE means all statements in this context run
    under traxia_service RLS policies, not as the superuser.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(f"SET ROLE {config.SERVICE_ROLE}")
                yield cur
    finally:
        conn.close()


@contextmanager
def app_conn(ingest_site_id: str) -> Generator[psycopg2.extensions.connection, None, None]:
    """Open a connection as traxia_app with app.current_ingest_site_id set.

    Used by the telemetry ingest endpoint.  traxia_app has INSERT on
    tracking_coordinates; traxia_service does not.  SET LOCAL scopes the GUC to
    the current transaction so the tracking_coordinates_ingest RLS policy
    (which calls sec_camera_on_ingest_site) sees the correct site_id.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SET ROLE traxia_app")
                cur.execute("SET LOCAL app.current_ingest_site_id = %s", (ingest_site_id,))
                yield cur
    finally:
        conn.close()


@contextmanager
def user_conn(token: Dict[str, Any]) -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    """Open a traxia_app connection with session GUCs populated from a user JWT.

    Sets: current_tenant_id, current_actor_role, current_user_id.
    Optionally sets: current_partner_id (if pid claim present),
                     current_user_site_ids (if sids claim present, comma-joined).
    All operations run under RLS as the authenticated user's context.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SET ROLE traxia_app")
                cur.execute("SET LOCAL app.current_tenant_id = %s", (str(token["tid"]),))
                cur.execute("SET LOCAL app.current_actor_role = %s", (token["role"],))
                cur.execute("SET LOCAL app.current_user_id = %s", (str(token["sub"]),))
                sids = token.get("sids") or []
                if sids:
                    cur.execute(
                        "SET LOCAL app.current_user_site_ids = %s",
                        (",".join(str(s) for s in sids),),
                    )
                pid = token.get("pid")
                if pid:
                    cur.execute("SET LOCAL app.current_partner_id = %s", (str(pid),))
                yield cur
    finally:
        conn.close()


@contextmanager
def admin_conn_for_tenant(tenant_id: str) -> Generator[psycopg2.extras.RealDictCursor, None, None]:
    """Open a traxia_app connection in admin context for a specific tenant.

    Used by the auto-revocation scheduler and other system operations that run
    without a live user JWT.  The partners_update / usa_write RLS policies
    require role='admin' + matching tenant_id — this satisfies both.
    """
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute("SET ROLE traxia_app")
                cur.execute("SET LOCAL app.current_tenant_id = %s", (str(tenant_id),))
                cur.execute("SET LOCAL app.current_actor_role = 'admin'")
                yield cur
    finally:
        conn.close()
