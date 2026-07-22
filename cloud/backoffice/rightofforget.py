"""Right-to-be-forgotten endpoint for Partners (SDD §12.12, Fase 3).

DELETE /v1/tenants/{tenant_id}/partners/{partner_id}/data

WHAT IS PURGED (irreversible):
  - agent_findings rows where partner_id = {partner_id}
  - zones owned by the partner (owner_type='PARTNER', owner_partner_id={partner_id})
    → this cascades to zone_dwell_sessions, tracking_coordinates (via foreign keys)
  - users belonging to the partner (users.partner_id = {partner_id})

WHAT IS RETAINED (for audit/legal hold):
  - partners row (status changed to 'inactive', name left for audit trail)
  - action_rules and action_events referencing the partner (operational history)
  - break_glass_audit_log entries (immutable security record)

Rationale: findings and zones are direct personal data (video analytics linked to
individuals in the partner's spaces).  The partners table itself is retained as a
pointer for audit logs.  Action rules are tenant property, not partner property.

This endpoint is intentionally separate from /partners/{id}/revoke (which only
deactivates access without deleting data).

Authorization: requires tenant admin JWT — the caller must be the tenant admin
of the tenant that owns the partner.  Purging Partner A does not affect Partner B
data in the same tenant (verified by WHERE partner_id = %s in all DELETE statements).
"""

import logging
from typing import Any, Dict

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException

from cloud import config
from cloud.auth.deps import require_tenant_admin

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/tenants", tags=["partner-data"])


@router.delete("/{tenant_id}/partners/{partner_id}/data", status_code=200)
def delete_partner_data(
    tenant_id: str,
    partner_id: str,
    token: dict = Depends(require_tenant_admin),
) -> Dict[str, Any]:
    """Purge all personal data attributed to a Partner (right to erasure).

    See module docstring for exact list of what is purged vs retained.
    This operation is IRREVERSIBLE.
    """
    # Enforce that the caller's tenant matches the URL tenant_id
    caller_tenant = token["tid"]
    if caller_tenant != tenant_id:
        raise HTTPException(status_code=403, detail="tenant_id mismatch")

    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                # Verify partner exists and belongs to this tenant
                cur.execute(
                    "SELECT id FROM partners WHERE id = %s AND tenant_id = %s",
                    (partner_id, tenant_id),
                )
                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail="partner_not_found_or_not_owned_by_tenant",
                    )

                # 1. Purge agent findings attributed to this partner
                cur.execute(
                    "DELETE FROM agent_findings WHERE partner_id = %s",
                    (partner_id,),
                )
                findings_deleted = cur.rowcount

                # 2. Purge users belonging to the partner
                cur.execute(
                    "DELETE FROM users WHERE partner_id = %s",
                    (partner_id,),
                )
                users_deleted = cur.rowcount

                # 3. Purge zones owned by the partner (cascades to zone_dwell_sessions
                #    and tracking_coordinates via ON DELETE CASCADE on FK constraints)
                cur.execute(
                    "DELETE FROM zones WHERE owner_type = 'PARTNER' AND owner_partner_id = %s",
                    (partner_id,),
                )
                zones_deleted = cur.rowcount

                # 4. Deactivate the partner record (retained for audit trail)
                cur.execute(
                    "UPDATE partners SET status = 'inactive' WHERE id = %s",
                    (partner_id,),
                )
    finally:
        conn.close()

    log.info(
        "Partner data purged: partner_id=%s tenant_id=%s "
        "findings=%d users=%d zones=%d",
        partner_id, tenant_id, findings_deleted, users_deleted, zones_deleted,
    )

    return {
        "partner_id": partner_id,
        "purged": {
            "agent_findings": findings_deleted,
            "users": users_deleted,
            "zones": zones_deleted,
        },
        "retained": ["partners (row, for audit trail)", "action_rules", "break_glass_audit_log"],
    }
