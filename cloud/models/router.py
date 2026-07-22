"""Model Registry manifest endpoint (SDD §4, §7.1).

GET /v1/models/{vertical_type}/manifest
  Returns the latest checkpoint metadata for the requested vertical.
  The download_url is a pre-signed object-storage URL (R2 in production).

Authentication: requires a valid Edge Gateway access token (JWT).
  Any unauthenticated or expired request returns 401.
  Rationale: the manifest contains a pre-signed download URL; serving it without
  auth would let anyone enumerate models and obtain download URLs without being
  an activated Edge Gateway.

For the MLP only 'retail' is active (SDD §3.1 decision 1, §5).

E2E smoke test: when FAKE_MODEL_SERVE=true, the manifest points to
GET /v1/models/retail/download which serves the fake model bytes locally.
The download endpoint itself requires no auth (mirrors R2 pre-signed URL behaviour).
"""

import os

from fastapi import APIRouter, Depends, HTTPException, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import jwt

from cloud import config

router = APIRouter(prefix="/v1/models")

_bearer = HTTPBearer()


def _require_gateway_token(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    """Verify a JWT access token issued by POST /v1/edge/token/activate or /refresh."""
    try:
        return jwt.decode(
            creds.credentials,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid_token")


_VALID_VERTICALS = {"retail", "banking", "logistics"}


def _build_registry() -> dict[str, dict]:
    """Build the in-memory model registry.

    In production this would query model_registry_entries and generate a fresh
    pre-signed R2 URL per request.  In E2E smoke tests (FAKE_MODEL_SERVE=true)
    the manifest points to the local download endpoint.
    """
    if os.environ.get("FAKE_MODEL_SERVE") == "true":
        base = os.environ.get("MODEL_BASE_URL", "http://localhost:8000")
        # When REAL_MODEL_SHA256 is set, the manifest returns the checksum of the
        # real YOLO weights pre-cached in the edge container (enables real inference).
        real_sha = config.REAL_MODEL_SHA256
        real_size = config.REAL_MODEL_SIZE
        if real_sha and real_size:
            return {
                "retail": {
                    "version": "1.0.0",
                    "filename": "yolo_retail.pt",
                    "download_url": f"{base}/v1/models/retail/download",
                    "sha256": real_sha,
                    "size": real_size,
                }
            }
        from cloud.models.fake_model import (
            FAKE_MODEL_SHA256,
            FAKE_MODEL_SIZE,
            FAKE_MODEL_VERSION,
        )
        return {
            "retail": {
                "version": FAKE_MODEL_VERSION,
                "filename": "yolo_retail.pt",
                "download_url": f"{base}/v1/models/retail/download",
                "sha256": FAKE_MODEL_SHA256,
                "size": FAKE_MODEL_SIZE,
            }
        }
    # Production path: R2 must be configured.
    # Return 503 rather than a placeholder URL that would silently fail when
    # an Edge Gateway tries to download a non-existent model.
    if not (config.R2_ACCOUNT_ID and config.R2_ACCESS_KEY_ID and config.R2_SECRET_ACCESS_KEY):
        raise HTTPException(
            status_code=503,
            detail={
                "code": "model_registry_not_configured",
                "message": (
                    "Model registry is not available: R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, and "
                    "R2_SECRET_ACCESS_KEY must all be set. This is a deployment configuration "
                    "gap, not a temporary outage. Set these variables before activating "
                    "production Edge Gateways."
                ),
            },
        )
    # TODO: query model_registry_entries table and generate a fresh pre-signed R2 URL.
    # Raise NotImplementedError until the registry backend is built.
    raise HTTPException(
        status_code=501,
        detail={
            "code": "model_registry_not_implemented",
            "message": (
                "Model registry backend is not yet implemented. "
                "R2 credentials are present but no model_registry_entries table query "
                "exists yet. Use FAKE_MODEL_SERVE=true for E2E testing."
            ),
        },
    )


class Manifest(BaseModel):
    version: str
    filename: str
    download_url: str
    sha256: str
    size: int


@router.get("/{vertical_type}/manifest", response_model=Manifest)
def get_manifest(
    vertical_type: str,
    _token: dict = Depends(_require_gateway_token),
) -> Manifest:
    if vertical_type not in _VALID_VERTICALS:
        raise HTTPException(status_code=404, detail="unknown_vertical")
    registry = _build_registry()
    entry = registry.get(vertical_type)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail=f"No model registered for vertical '{vertical_type}'",
        )
    return Manifest(**entry)


@router.get("/retail/download")
def download_fake_model() -> Response:
    """Serve the fake model file for E2E smoke tests.

    Only active when FAKE_MODEL_SERVE=true.  No auth required — mirrors the
    behaviour of a pre-signed R2 URL that the edge gateway downloads directly.
    """
    if os.environ.get("FAKE_MODEL_SERVE") != "true":
        raise HTTPException(status_code=404, detail="not_found")
    from cloud.models.fake_model import FAKE_MODEL_BYTES
    return Response(content=FAKE_MODEL_BYTES, media_type="application/octet-stream")
