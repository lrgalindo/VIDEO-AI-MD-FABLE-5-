"""Break-glass access endpoint — SDD §8.5.

POST /v1/superadmin/break-glass
  Activates break-glass access for a platform admin to a specific tenant.
  Creates an entry in break_glass_audit_log.  The sec_break_glass_allows_camera()
  SECURITY DEFINER function (defined in migration 0001) reads this table and the
  GUC app.break_glass_admin_id to permit cross-tenant visibility.

POST /v1/superadmin/break-glass/{log_id}/end
  Closes the break-glass session by setting ended_at = now().

Break-glass does NOT grant write access — it only unlocks SELECT on
tracking_coordinates via the existing RLS policy.  The session expires
automatically after 4 hours (enforced in sec_break_glass_allows_camera).

Only SuperAdmin tokens ({"sa": true}) may call these endpoints.
"""

import uuid
from typing import Any, Dict

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from fastapi import Depends

from cloud import config
from cloud.auth.superadmin import require_platform_admin

router = APIRouter(prefix="/v1/superadmin", tags=["superadmin-breakglass"])


class BreakGlassRequest(BaseModel):
    tenant_id: str
    reason: str
    ticket_id: str


@router.post("/break-glass", status_code=201)
def activate_break_glass(
    body: BreakGlassRequest,
    admin: Dict[str, Any] = Depends(require_platform_admin),
) -> Dict[str, Any]:
    """Activate break-glass access for a platform admin to a tenant.

    Creates an entry in break_glass_audit_log.  The DB function
    sec_break_glass_allows_camera() will allow SELECT on tracking_coordinates
    for the specified tenant when app.break_glass_admin_id GUC is set to
    this admin's id in the session.  Sessions expire after 4 hours.

    Only accessible with a SuperAdmin JWT ({"sa": true}).
    """
    admin_id = admin["sub"]
    log_id = str(uuid.uuid4())

    try:
        tenant_uuid = uuid.UUID(body.tenant_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="tenant_id must be a valid UUID")

    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Verify tenant exists
                cur.execute("SELECT id FROM tenants WHERE id = %s", (str(tenant_uuid),))
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail="tenant_not_found")

                cur.execute(
                    """
                    INSERT INTO break_glass_audit_log
                        (id, platform_admin_id, reason, ticket_id, tenant_id_accessed)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id::text, started_at
                    """,
                    (log_id, admin_id, body.reason, body.ticket_id, str(tenant_uuid)),
                )
                row = cur.fetchone()
    finally:
        conn.close()

    return {
        "log_id": row["id"],
        "admin_id": admin_id,
        "tenant_id": body.tenant_id,
        "started_at": row["started_at"].isoformat(),
        "expires_after_hours": 4,
        "guc_hint": (
            f"SET LOCAL app.break_glass_admin_id = '{admin_id}';"
            " -- must be set in each DB session that needs cross-tenant SELECT"
        ),
    }


@router.post("/break-glass/{log_id}/end")
def end_break_glass(
    log_id: str,
    admin: Dict[str, Any] = Depends(require_platform_admin),
) -> Dict[str, Any]:
    """End a break-glass session by setting ended_at.

    Only the admin who opened the session can close it.
    """
    admin_id = admin["sub"]

    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE break_glass_audit_log
                       SET ended_at = now()
                     WHERE id = %s AND platform_admin_id = %s AND ended_at IS NULL
                    RETURNING id::text
                    """,
                    (log_id, admin_id),
                )
                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail="break_glass_session_not_found_or_already_ended",
                    )
    finally:
        conn.close()

    return {"log_id": log_id, "status": "ended"}
