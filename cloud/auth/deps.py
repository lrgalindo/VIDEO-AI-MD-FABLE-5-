"""FastAPI security dependencies for user (backoffice) JWT authentication."""

import jwt
from fastapi import HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cloud import config

_bearer = HTTPBearer()


def _require_user_token(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Decode a user JWT.  Rejects gateway tokens (which lack the 'tid' claim)."""
    try:
        payload = jwt.decode(
            creds.credentials,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")

    if "tid" not in payload:
        raise HTTPException(status_code=401, detail="not_a_user_token")
    return payload


def require_tenant_admin(
    token: dict = Security(_require_user_token),
) -> dict:
    """Require the caller to be a tenant admin (not a partner admin).

    A partner admin has pid set — they can only manage their own partner users,
    not the full tenant's users/partners.  This dependency rejects:
    - Any non-admin role (operator, viewer)
    - Any partner-scoped token (pid present), including partner admins
    """
    if token.get("role") != "admin" or token.get("pid") is not None:
        raise HTTPException(status_code=403, detail="tenant_admin_required")
    return token
