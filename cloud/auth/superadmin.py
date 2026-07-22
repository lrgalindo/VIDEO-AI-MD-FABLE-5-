"""SuperAdmin (Platform Admin) JWT authentication.

SuperAdmin tokens carry the claim {"sa": true} and are signed with
PLATFORM_ADMIN_SECRET — a deliberately separate secret from JWT_SECRET so
that a compromised tenant JWT cannot be replayed as a SuperAdmin token.

The require_platform_admin dependency additionally verifies that the admin's
id exists in platform_admins with status='active', preventing tokens from
deleted/disabled admins from being accepted after the fact.

Bootstrap: use make_platform_admin_token(admin_id) to generate a token for
the initial admin account (created manually or via a seed script).

HTTP login: POST /v1/superadmin/login (email + password).
"""
import bcrypt
import jwt
import psycopg2
import psycopg2.extras
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr

from cloud import config

_bearer = HTTPBearer()
router = APIRouter(prefix="/v1/superadmin", tags=["superadmin-auth"])


def _sa_secret() -> str:
    if not config.PLATFORM_ADMIN_SECRET:
        raise HTTPException(
            status_code=503,
            detail="platform_admin_auth_not_configured",
        )
    return config.PLATFORM_ADMIN_SECRET


# ── Request model ─────────────────────────────────────────────────────────────

class SuperAdminLoginRequest(BaseModel):
    email: EmailStr
    password: str


# ── HTTP login endpoint ───────────────────────────────────────────────────────

@router.post("/login")
def superadmin_login(body: SuperAdminLoginRequest) -> dict:
    """Authenticate a platform admin with email + bcrypt password.

    Returns a signed JWT with {"sa": true} on success.
    Only the HTTP endpoint is here — make_platform_admin_token() remains available
    for programmatic bootstrap (first admin creation via CLI/seed).
    """
    if not config.PLATFORM_ADMIN_SECRET:
        raise HTTPException(status_code=503, detail="platform_admin_auth_not_configured")

    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id::text, password_hash, status FROM platform_admins WHERE email = %s",
                    (body.email,),
                )
                row = cur.fetchone()
    finally:
        conn.close()

    # Deliberate timing-safe rejection: run bcrypt even on missing user to prevent
    # email enumeration via response time difference.
    # Pre-computed bcrypt(cost=12) — never matches any real password.
    _DUMMY_HASH = b"$2b$12$D9zREsn07byX.W4lSsTZfe4eFZSyTRFmd4AMAOpkhTTwwX./ZjSSC"
    stored_hash = row["password_hash"].encode() if row else _DUMMY_HASH
    valid = bcrypt.checkpw(body.password.encode(), stored_hash)

    if not row or not valid or row["status"] != "active":
        raise HTTPException(status_code=401, detail="invalid_credentials")

    return {"access_token": make_platform_admin_token(row["id"]), "token_type": "bearer"}


# ── Programmatic token for bootstrap ─────────────────────────────────────────

def make_platform_admin_token(admin_id: str) -> str:
    """Issue a SuperAdmin JWT (signed with PLATFORM_ADMIN_SECRET)."""
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": admin_id,
        "sa": True,
        "iat": now,
        "exp": now + timedelta(hours=config.ACCESS_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, _sa_secret(), algorithm=config.JWT_ALGORITHM)


def require_platform_admin(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Verify a SuperAdmin JWT and confirm the admin is still active in the DB.

    Rejects:
    - Missing or invalid signature (uses PLATFORM_ADMIN_SECRET, not JWT_SECRET)
    - Tokens without the "sa": true claim (prevents tenant tokens from being used)
    - Admin not found in platform_admins or status != 'active'
    """
    secret = _sa_secret()
    try:
        payload = jwt.decode(
            creds.credentials,
            secret,
            algorithms=[config.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")

    if not payload.get("sa"):
        raise HTTPException(status_code=403, detail="platform_admin_token_required")

    admin_id = payload.get("sub")
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id FROM platform_admins WHERE id = %s AND status = 'active'",
                    (admin_id,),
                )
                if cur.fetchone() is None:
                    raise HTTPException(status_code=403, detail="platform_admin_not_active")
    finally:
        conn.close()

    return payload
