"""Tenant lifecycle endpoints — Sección 3.1 decisión 11.

(a) POST /v1/tenants/register      — public; creates tenant status='onboarding'
(b) POST /v1/superadmin/tenants/{id}/approve
                                   — SuperAdmin; activates tenant and creates
                                     the first Edge Gateway with its activation
                                     code (one-time, 72-hour expiry)
(c) POST /v1/superadmin/tenants/{id}/deactivate
                                   — SuperAdmin; sets tenant status='inactive'
                                     and revokes ALL Edge Gateways for that
                                     tenant by setting status='revoked' — the
                                     same Fase 1 §8.7.0 mechanism that blocks
                                     the /refresh endpoint (which checks
                                     AND status NOT IN ('revoked','decommissioned'))

Authorization:
  (a) Public — no JWT required.  Rate-limiting is the caller's responsibility
      (API gateway / WAF layer, outside this service).
  (b)(c) require_platform_admin dependency — SuperAdmin JWT signed with
      PLATFORM_ADMIN_SECRET, "sa": true claim verified + live DB check.
"""
import secrets
from typing import Any, Dict, Optional

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from cloud import config
from cloud.auth.superadmin import require_platform_admin
from cloud.auth.tokens import sha256_hex
from cloud.db import service_conn

router = APIRouter(tags=["lifecycle"])

_ACTIVATION_CODE_TTL = "72 hours"


# ── Request / Response models ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    contact_email: EmailStr
    vertical_type: str  # 'retail' | 'banking' | 'logistics'


class RegisterResponse(BaseModel):
    tenant_id: str
    status: str  # always 'onboarding'


class ApproveRequest(BaseModel):
    gateway_id: str       # hardware ID of the first Edge Gateway (MAC / serial)
    vertical_type: str    # gateway's vertical (usually matches tenant)


class ApproveResponse(BaseModel):
    tenant_id: str
    status: str           # 'active'
    gateway_id: str
    activation_code: str  # PLAINTEXT — return to approver, stored as hash only
    activation_code_expires_at: str


class DeactivateResponse(BaseModel):
    tenant_id: str
    status: str           # 'inactive'
    gateways_revoked: int


# ── (a) Self-registration ─────────────────────────────────────────────────────

@router.post("/v1/tenants/register", response_model=RegisterResponse, status_code=201)
def register_tenant(body: RegisterRequest) -> RegisterResponse:
    """Create a new tenant in status='onboarding' (public endpoint).

    No authentication required — the self-registration gate is intentionally
    open. Actual system access is only possible once a SuperAdmin approves.
    """
    if body.vertical_type not in ("retail", "banking", "logistics"):
        raise HTTPException(status_code=422, detail="invalid_vertical_type")

    with service_conn() as cur:
        cur.execute(
            """
            INSERT INTO tenants (name, vertical_type, status, contact_email)
            VALUES (%s, %s, 'onboarding', %s)
            RETURNING id::text, status
            """,
            (body.name, body.vertical_type, body.contact_email),
        )
        row = cur.fetchone()

    return RegisterResponse(tenant_id=row["id"], status=row["status"])


# ── (b) Approval — SuperAdmin only ───────────────────────────────────────────

@router.post(
    "/v1/superadmin/tenants/{tenant_id}/approve",
    response_model=ApproveResponse,
)
def approve_tenant(
    tenant_id: str,
    body: ApproveRequest,
    admin: dict = Depends(require_platform_admin),
) -> ApproveResponse:
    """Approve an onboarding tenant and generate the first gateway activation code.

    Steps (all in one transaction via service_conn):
    1. UPDATE tenants SET status='active', approved_by, approved_at WHERE status='onboarding'
    2. INSERT INTO edge_gateways with status='offline'
    3. Generate a cryptographically random activation code (stored as SHA-256 hash)

    The plaintext activation_code is returned ONCE in this response.
    The approver sends it to the customer via secure channel (email/support ticket).
    """
    activation_plain = secrets.token_urlsafe(24)
    activation_hash = sha256_hex(activation_plain)
    admin_id = admin["sub"]

    with service_conn() as cur:
        # Step 1 — approve the tenant
        cur.execute(
            """
            UPDATE tenants
               SET status       = 'active',
                   approved_by  = %s,
                   approved_at  = now()
             WHERE id     = %s
               AND status = 'onboarding'
            RETURNING id::text, status
            """,
            (admin_id, tenant_id),
        )
        row = cur.fetchone()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail="tenant_not_found_or_not_onboarding",
            )

        # Step 2+3 — create the first gateway entry (status='offline') with activation code
        # The gateway must be attached to a site, but we need to find or create one.
        # For the MLP: require a site to exist; the caller must have already created
        # sites via the backoffice flow (or the approval creates a bootstrap site).
        # Here we create a bootstrap site automatically on approval.
        cur.execute(
            """
            INSERT INTO sites (tenant_id, name, status)
            VALUES (%s, 'Sucursal Principal', 'active')
            RETURNING id::text
            """,
            (tenant_id,),
        )
        site_row = cur.fetchone()
        site_id = site_row["id"]

        cur.execute(
            """
            INSERT INTO edge_gateways
                (id, site_id, vertical_type, status,
                 activation_code_hash, activation_code_expires_at)
            VALUES (%s, %s, %s, 'offline', %s,
                   now() + INTERVAL %s)
            ON CONFLICT (id) DO UPDATE
               SET activation_code_hash       = EXCLUDED.activation_code_hash,
                   activation_code_expires_at = EXCLUDED.activation_code_expires_at,
                   status                     = 'offline'
            RETURNING id,
                      activation_code_expires_at::text AS expires_at
            """,
            (
                body.gateway_id,
                site_id,
                body.vertical_type,
                activation_hash,
                _ACTIVATION_CODE_TTL,
            ),
        )
        gw = cur.fetchone()

    return ApproveResponse(
        tenant_id=tenant_id,
        status="active",
        gateway_id=gw["id"],
        activation_code=activation_plain,
        activation_code_expires_at=gw["expires_at"],
    )


# ── (c) Deactivation — SuperAdmin only, reuses Fase 1 §8.7.0 revocation ──────

@router.post(
    "/v1/superadmin/tenants/{tenant_id}/deactivate",
    response_model=DeactivateResponse,
)
def deactivate_tenant(
    tenant_id: str,
    admin: dict = Depends(require_platform_admin),
) -> DeactivateResponse:
    """Set tenant status='inactive' and revoke all its Edge Gateways.

    Gateway revocation reuses the Fase 1 §8.7.0 mechanism:
      UPDATE edge_gateways SET status='revoked', refresh_token_hash=NULL, ...
    After this UPDATE, the /refresh endpoint's existing check
      AND status NOT IN ('revoked', 'decommissioned')
    will reject any subsequent token refresh attempt for all affected gateways.
    No new revocation code path is introduced.
    """
    with service_conn() as cur:
        # Step 1 — mark tenant inactive
        cur.execute(
            """
            UPDATE tenants
               SET status         = 'inactive',
                   deactivated_at = now()
             WHERE id     = %s
               AND status != 'inactive'
            RETURNING id::text
            """,
            (tenant_id,),
        )
        if cur.fetchone() is None:
            raise HTTPException(
                status_code=404,
                detail="tenant_not_found_or_already_inactive",
            )

        # Step 2 — revoke ALL edge gateways for this tenant (Fase 1 §8.7.0 path).
        # Nulling the token hashes + prev_hash is belt-and-suspenders: even if
        # the status check were somehow bypassed, a NULL hash can never match.
        cur.execute(
            """
            UPDATE edge_gateways eg
               SET status                     = 'revoked',
                   refresh_token_hash         = NULL,
                   refresh_token_prev_hash    = NULL,
                   refresh_token_expires_at   = NULL,
                   refresh_token_prev_expires_at = NULL
             FROM sites s
             WHERE s.id = eg.site_id
               AND s.tenant_id = %s
               AND eg.status NOT IN ('decommissioned')
            """,
            (tenant_id,),
        )
        revoked = cur.rowcount

    return DeactivateResponse(
        tenant_id=tenant_id,
        status="inactive",
        gateways_revoked=revoked,
    )
