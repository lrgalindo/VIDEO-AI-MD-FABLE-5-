"""Backoffice API — tenant admin endpoints (Fase 2).

All endpoints require a tenant admin JWT (require_tenant_admin dependency).
All DB operations run as traxia_app through RLS via user_conn() — no query
bypasses the row-level security policies.

Endpoints:
  POST /v1/backoffice/users               — create user + assign to sites
  GET  /v1/backoffice/users               — list tenant users
  DELETE /v1/backoffice/users/{id}/sites/{site_id} — remove site assignment
  POST /v1/backoffice/partners            — one-step partner creation + invite
  POST /v1/backoffice/partners/{id}/revoke — manual partner revocation
"""

import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from cloud.auth.deps import require_tenant_admin
from cloud.auth.tokens import make_user_token, new_opaque_token
from cloud.backoffice.scheduler import revoke_partner
from cloud.db import user_conn

log = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/backoffice")


# ── Request / Response models ──────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    email: EmailStr
    role: str          # 'operator' | 'viewer'
    site_ids: List[str]  # UUIDs of sites to assign (≥1 for operator/viewer)

    model_config = {"json_schema_extra": {"example": {
        "email": "operator@tienda.com",
        "role": "operator",
        "site_ids": ["c3e20000-0000-0000-0000-000000000001"],
    }}}


class UserResponse(BaseModel):
    user_id: str
    email: str
    role: str
    site_ids: List[str]
    invite_token: str   # plaintext — caller sends this in the invitation email


class UserListItem(BaseModel):
    user_id: str
    email: str
    role: str
    status: str


class ZoneSpec(BaseModel):
    camera_id: str
    name: str
    zone_type: str = "shelf"
    coordinates: dict


class CreatePartnerRequest(BaseModel):
    name: str
    admin_email: EmailStr
    access_expires_at: Optional[str] = None   # ISO-8601 or None for no expiry
    zones: List[ZoneSpec] = []

    model_config = {"json_schema_extra": {"example": {
        "name": "Proveedor Lácteos SA",
        "admin_email": "admin@lacteos.com",
        "access_expires_at": "2027-01-01T00:00:00Z",
        "zones": [{
            "camera_id": "d4e2e000-0000-0000-0000-000000000001",
            "name": "Refrigerador Lácteos",
            "zone_type": "shelf",
            "coordinates": {"type": "polygon", "points": [[0,0],[100,0],[100,100],[0,100]]},
        }],
    }}}


class PartnerResponse(BaseModel):
    partner_id: str
    name: str
    admin_user_id: str
    invite_token: str   # plaintext — caller sends this in the invitation email
    zones_created: int


# ── User management ────────────────────────────────────────────────────────────

@router.post("/users", response_model=UserResponse, status_code=201)
def create_user(
    body: CreateUserRequest,
    token: dict = Depends(require_tenant_admin),
) -> UserResponse:
    """Create an operator or viewer user and assign them to the given sites.

    Admin users implicitly see all tenant sites (the sites_read RLS policy
    handles this with no rows needed in user_site_assignments).  This endpoint
    is for operator/viewer accounts that need explicit per-site access.

    The invite_token in the response must be relayed to the user out-of-band
    (email).  It expires in 72 hours.  Only its SHA-256 hash is stored in the DB.
    """
    if body.role not in ("operator", "viewer"):
        raise HTTPException(status_code=422, detail="role must be 'operator' or 'viewer'")
    if not body.site_ids:
        raise HTTPException(status_code=422, detail="at least one site_id is required")

    invite_plain, invite_hash = new_opaque_token()
    tenant_id = token["tid"]

    with user_conn(token) as cur:
        # Insert user — users_write RLS ensures tenant scoping
        cur.execute(
            """
            INSERT INTO users (tenant_id, email, role, status,
                               invite_token_hash, invite_expires_at)
            VALUES (%s, %s, %s, 'invited', %s, now() + interval '72 hours')
            RETURNING id::text AS user_id
            """,
            (tenant_id, body.email, body.role, invite_hash),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(status_code=409, detail="user already exists or RLS denied insert")
        user_id = row["user_id"]

        # Verify each site belongs to this tenant and assign
        # usa_write RLS: sec_tenant_owns_site(site_id, current_tenant_id) — no bypass needed
        assigned: List[str] = []
        for site_id in body.site_ids:
            try:
                cur.execute(
                    """
                    INSERT INTO user_site_assignments (user_id, site_id)
                    VALUES (%s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (user_id, site_id),
                )
                assigned.append(site_id)
            except Exception as exc:
                log.warning("Site assignment failed for site %s: %s", site_id, exc)
                raise HTTPException(
                    status_code=403,
                    detail=f"site {site_id} not accessible in this tenant or RLS denied",
                )

    return UserResponse(
        user_id=user_id,
        email=body.email,
        role=body.role,
        site_ids=assigned,
        invite_token=invite_plain,
    )


@router.get("/users", response_model=List[UserListItem])
def list_users(
    token: dict = Depends(require_tenant_admin),
) -> List[UserListItem]:
    """List all users belonging to this tenant (excluding partner users)."""
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT id::text AS user_id, email, role, status
            FROM users
            WHERE partner_id IS NULL
            ORDER BY created_at
            """
        )
        rows = cur.fetchall()
    return [
        UserListItem(
            user_id=r["user_id"],
            email=r["email"],
            role=r["role"],
            status=r["status"],
        )
        for r in rows
    ]


@router.delete("/users/{user_id}/sites/{site_id}", status_code=204)
def remove_site_assignment(
    user_id: str,
    site_id: str,
    token: dict = Depends(require_tenant_admin),
) -> None:
    """Remove a site assignment from a user."""
    with user_conn(token) as cur:
        cur.execute(
            "DELETE FROM user_site_assignments WHERE user_id = %s AND site_id = %s",
            (user_id, site_id),
        )


# ── Partner management ─────────────────────────────────────────────────────────

@router.post("/partners", response_model=PartnerResponse, status_code=201)
def create_partner(
    body: CreatePartnerRequest,
    token: dict = Depends(require_tenant_admin),
) -> PartnerResponse:
    """Create a partner, its admin user, and zones — all in one step.

    Flow (atomic within a single transaction via user_conn):
    1. INSERT partner → partners table (partners_write RLS enforces tenant scoping)
    2. INSERT admin user for the partner (users_write RLS)
    3. INSERT zones for each spec (zones_provision RLS: sec_tenant_owns_camera)
    4. Generate invite token (only hash stored; plaintext returned to caller)

    The invite_token must be sent to admin_email out-of-band.  For the MLP
    this is returned in the response; in production it would be sent via email.
    """
    invite_plain, invite_hash = new_opaque_token()
    tenant_id = token["tid"]

    with user_conn(token) as cur:
        # 1. Create partner
        expires_sql = (
            "(%s::timestamptz)" if body.access_expires_at else "NULL"
        )
        if body.access_expires_at:
            cur.execute(
                f"""
                INSERT INTO partners (tenant_id, name, access_expires_at)
                VALUES (%s, %s, {expires_sql})
                RETURNING id::text AS partner_id, name
                """,
                (tenant_id, body.name, body.access_expires_at),
            )
        else:
            cur.execute(
                """
                INSERT INTO partners (tenant_id, name)
                VALUES (%s, %s)
                RETURNING id::text AS partner_id, name
                """,
                (tenant_id, body.name),
            )
        partner_row = cur.fetchone()
        if partner_row is None:
            raise HTTPException(status_code=403, detail="RLS denied partner creation")
        partner_id = partner_row["partner_id"]

        # 2. Create partner admin user
        cur.execute(
            """
            INSERT INTO users (tenant_id, partner_id, email, role, status,
                               invite_token_hash, invite_expires_at)
            VALUES (%s, %s, %s, 'admin', 'invited', %s, now() + interval '72 hours')
            RETURNING id::text AS user_id
            """,
            (tenant_id, partner_id, body.admin_email, invite_hash),
        )
        user_row = cur.fetchone()
        if user_row is None:
            raise HTTPException(status_code=409, detail="admin user could not be created")
        admin_user_id = user_row["user_id"]

        # 3. Create zones (uses zones_provision policy: sec_tenant_owns_camera)
        # We need to set app.provision_tenant_id for the zones_provision policy.
        cur.execute("SET LOCAL app.provision_tenant_id = %s", (tenant_id,))
        zones_created = 0
        for z in body.zones:
            try:
                cur.execute(
                    """
                    INSERT INTO zones (camera_id, owner_type, owner_partner_id,
                                       name, zone_type, coordinates)
                    VALUES (%s, 'PARTNER', %s, %s, %s, %s)
                    """,
                    (z.camera_id, partner_id, z.name, z.zone_type,
                     __import__("json").dumps(z.coordinates)),
                )
                zones_created += 1
            except Exception as exc:
                raise HTTPException(
                    status_code=403,
                    detail=f"zone creation denied for camera {z.camera_id}: {exc}",
                )

    log.info(
        "Partner created: id=%s name=%r admin=%s zones=%d tenant=%s",
        partner_id, body.name, body.admin_email, zones_created, tenant_id,
    )

    return PartnerResponse(
        partner_id=partner_id,
        name=body.name,
        admin_user_id=admin_user_id,
        invite_token=invite_plain,
        zones_created=zones_created,
    )


@router.post("/partners/{partner_id}/revoke", status_code=200)
def revoke_partner_endpoint(
    partner_id: str,
    token: dict = Depends(require_tenant_admin),
) -> dict:
    """Manually revoke a partner's access (same path as the auto-scheduler).

    Sets partners.status = 'inactive'.  The auto-revocation scheduler calls
    the same revoke_partner() function when access_expires_at is passed.
    """
    tenant_id = token["tid"]
    revoke_partner(partner_id, tenant_id)
    return {"revoked": partner_id}
