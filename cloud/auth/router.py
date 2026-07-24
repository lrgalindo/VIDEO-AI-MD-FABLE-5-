from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from cloud.auth.tokens import make_access_token, new_opaque_token, sha256_hex
from cloud.db import service_conn

router = APIRouter(prefix="/v1/edge/token")

_GENERIC_401 = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="invalid_grant",
)


class ActivateRequest(BaseModel):
    gateway_id: str
    activation_code: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int = 86400  # 24 h in seconds
    refresh_token: str


class RefreshRequest(BaseModel):
    gateway_id: str
    refresh_token: str


@router.post("/activate", response_model=TokenResponse)
def activate(body: ActivateRequest) -> TokenResponse:
    """Exchange a one-time activation code for an access + refresh token pair.

    The activation UPDATE atomically:
    - verifies the code hash and expiry (never stores plaintext)
    - clears the activation code so it cannot be reused
    - writes the new refresh_token_hash and sets status = 'online'
    """
    refresh_plain, refresh_hash = new_opaque_token()
    code_hash = sha256_hex(body.activation_code)

    with service_conn() as cur:
        cur.execute(
            """
            UPDATE edge_gateways eg
               SET activation_code_hash       = NULL,
                   activation_code_expires_at = NULL,
                   refresh_token_hash         = %(rh)s,
                   refresh_token_expires_at   = now() + interval '90 days',
                   last_token_refresh_at      = now(),
                   status                     = 'online'
             WHERE eg.id                      = %(gid)s
               AND eg.activation_code_hash    = %(ch)s
               AND eg.activation_code_expires_at > now()
               AND eg.status                  = 'offline'
               AND EXISTS (
                     SELECT 1
                     FROM sites s
                     JOIN tenants t ON t.id = s.tenant_id
                     WHERE s.id = eg.site_id
                       AND t.status = 'active'
                   )
            RETURNING eg.id, eg.site_id, eg.vertical_type
            """,
            {"gid": body.gateway_id, "ch": code_hash, "rh": refresh_hash},
        )
        row = cur.fetchone()

    if row is None:
        raise _GENERIC_401

    return TokenResponse(
        access_token=make_access_token(row["id"], row["site_id"], row["vertical_type"]),
        refresh_token=refresh_plain,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest) -> TokenResponse:
    """Rotate the refresh token and issue a new access token.

    The UPDATE atomically validates (SDD §8.7.0):
    - correct hash — either the current token OR the previous one within the
      grace window (covers lost HTTP responses on unstable networks)
    - token not expired
    - gateway not revoked/decommissioned

    Grace-window mechanics (all in one atomic UPDATE):
    - Matched via current hash  → save old hash as prev_hash for REFRESH_GRACE_SECONDS
    - Matched via prev hash     → clear prev_hash (consumed; one retry only)
    The CASE expressions evaluate the pre-UPDATE column values, so both branches
    are mutually exclusive and race-free.

    Zero rows returned for any failure reason. Single generic 401 — no leakage
    of which condition failed.
    """
    from cloud import config as cfg

    refresh_plain, refresh_hash = new_opaque_token()
    old_hash = sha256_hex(body.refresh_token)

    with service_conn() as cur:
        cur.execute(
            """
            UPDATE edge_gateways eg
               SET refresh_token_hash            = %(new_rh)s,
                   refresh_token_expires_at      = now() + interval '90 days',
                   last_token_refresh_at         = now(),
                   -- If old hash matched the *prev* slot (grace retry): consume it.
                   -- If old hash matched the *current* slot (normal path): save it as prev.
                   refresh_token_prev_hash       = CASE
                       WHEN eg.refresh_token_prev_hash = %(old_rh)s THEN NULL
                       ELSE %(old_rh)s
                     END,
                   refresh_token_prev_expires_at = CASE
                       WHEN eg.refresh_token_prev_hash = %(old_rh)s THEN NULL
                       ELSE now() + (%(grace)s || ' seconds')::interval
                     END
             WHERE eg.id                         = %(gid)s
               AND (
                     eg.refresh_token_hash       = %(old_rh)s
                 OR (eg.refresh_token_prev_hash  = %(old_rh)s
                     AND eg.refresh_token_prev_expires_at > now())
               )
               AND eg.refresh_token_expires_at   > now()
               AND eg.status NOT IN ('revoked', 'decommissioned')
               AND EXISTS (
                     SELECT 1
                     FROM sites s
                     JOIN tenants t ON t.id = s.tenant_id
                     WHERE s.id = eg.site_id
                       AND t.status = 'active'
                   )
            RETURNING eg.id, eg.site_id, eg.vertical_type
            """,
            {
                "gid": body.gateway_id,
                "old_rh": old_hash,
                "new_rh": refresh_hash,
                "grace": cfg.REFRESH_GRACE_SECONDS,
            },
        )
        row = cur.fetchone()

    if row is None:
        raise _GENERIC_401

    return TokenResponse(
        access_token=make_access_token(row["id"], row["site_id"], row["vertical_type"]),
        refresh_token=refresh_plain,
    )
