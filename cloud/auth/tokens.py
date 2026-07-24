import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import List, Optional

import jwt

from cloud import config


def sha256_hex(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def new_opaque_token() -> tuple[str, str]:
    """Return (plaintext_token, sha256_hex_hash). Only the hash is stored."""
    token = secrets.token_urlsafe(32)
    return token, sha256_hex(token)


def make_access_token(gateway_id: str, site_id: str, vertical_type: str) -> str:
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": gateway_id,
        "sid": site_id,
        "vt": vertical_type,
        "iat": now,
        "exp": now + timedelta(hours=config.ACCESS_TOKEN_TTL_HOURS),
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def make_user_token(
    user_id: str,
    tenant_id: str,
    role: str,
    partner_id: Optional[str] = None,
    site_ids: Optional[List[str]] = None,
) -> str:
    """Issue a JWT for a tenant user (admin/operator/viewer).

    Distinguishable from gateway tokens by the presence of "tid" (tenant_id)
    and absence of "sid" (site_id) / "vt" (vertical_type).
    """
    now = datetime.now(tz=timezone.utc)
    payload: dict = {
        "sub": user_id,
        "tid": tenant_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(hours=config.ACCESS_TOKEN_TTL_HOURS),
    }
    if partner_id is not None:
        payload["pid"] = partner_id
    if site_ids:
        payload["sids"] = site_ids
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)
