"""Agent Findings endpoint (SDD §12.5 / Fase 3).

GET /v1/findings
  Returns agent_findings rows visible to the authenticated user.
  RLS (via user_conn) enforces scope:
    - Tenant admin/operator: all findings for their tenant
    - Partner viewer: ONLY findings where partner_id matches their pid claim

  For each finding that has a snapshot stored in R2 (detail.snapshot_r2_key),
  a short-lived pre-signed URL is generated on the fly and returned as
  snapshot_url in the response.  The raw R2 key is never sent to the client.

  Pre-signed URLs expire in R2_PRESIGN_TTL_SECONDS (default 300s).  A viewer
  who caches the URL cannot use it after expiry — they must re-fetch the
  findings list, which re-validates their JWT and regenerates the URL under
  the same RLS scope.

  Security note: the pre-signed URL grant is scoped to a single R2 object.
  It does not expose any bucket listing capability or other objects.
"""

import logging
from typing import Any, Dict, List, Optional

import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cloud.auth.deps import _require_user_token
from cloud import config
from cloud.db import user_conn

log = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/findings", tags=["findings"])


# ── Presigned URL helper ──────────────────────────────────────────────────────

def _presign_snapshot(r2_key: str) -> Optional[str]:
    """Generate a short-lived pre-signed R2 URL for the given object key.

    Returns None if R2 credentials are not configured — callers treat None
    as "no snapshot URL available" and omit snapshot_url from the response.
    Never raises: a signing failure logs a warning and returns None so the
    rest of the findings list is still returned.
    """
    if not (config.R2_ACCOUNT_ID and config.R2_ACCESS_KEY_ID and config.R2_SECRET_ACCESS_KEY):
        return None
    try:
        import boto3  # lazy import — only needed when R2 is configured
        internal_endpoint = config.R2_ENDPOINT_URL or f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        presign_endpoint = config.R2_PUBLIC_ENDPOINT_URL or internal_endpoint
        s3 = boto3.client(
            "s3",
            endpoint_url=presign_endpoint,
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        return s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": config.R2_BUCKET_SNAPSHOTS, "Key": r2_key},
            ExpiresIn=config.R2_PRESIGN_TTL_SECONDS,
        )
    except Exception as exc:
        log.warning("Failed to presign snapshot key %s: %s", r2_key, exc)
        return None


# ── Response models ───────────────────────────────────────────────────────────

class FindingDetail(BaseModel):
    recent_avg_dwell: Optional[float] = None
    baseline_avg_dwell: Optional[float] = None
    vision_finding: Optional[str] = None
    snapshot_available: Optional[bool] = None
    # snapshot_r2_key is intentionally ABSENT from the response model.
    # The key is an internal storage reference — only the presigned URL is exposed.


class AgentFindingResponse(BaseModel):
    id: str
    task_type: str
    zone_id: Optional[str] = None
    summary: str
    detail: FindingDetail
    snapshot_url: Optional[str] = None  # presigned R2 URL, None if no snapshot or R2 unconfigured
    created_at: str


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("", response_model=List[AgentFindingResponse])
def list_findings(
    token: dict = Depends(_require_user_token),
) -> List[AgentFindingResponse]:
    """List agent findings visible to the authenticated user.

    RLS on agent_findings enforces scope automatically:
    - Tenant admin / operator: sees all findings for their tenant
    - Partner viewer: sees only findings where partner_id = their pid

    This endpoint is intentionally available to all user roles (admin,
    operator, partner viewer) — Motor de Acciones is admin-only but
    Hallazgos is visible to partners per SDD §4.1.
    """
    with user_conn(token) as cur:
        cur.execute(
            """
            SELECT
                id::text,
                task_type,
                zone_id::text,
                summary,
                detail,
                created_at::text
            FROM agent_findings
            ORDER BY created_at DESC
            LIMIT 100
            """
        )
        rows: List[Dict[str, Any]] = [dict(r) for r in cur.fetchall()]

    results = []
    for row in rows:
        raw_detail: Dict[str, Any] = row.get("detail") or {}
        r2_key: Optional[str] = raw_detail.pop("snapshot_r2_key", None)
        snapshot_url: Optional[str] = _presign_snapshot(r2_key) if r2_key else None

        results.append(
            AgentFindingResponse(
                id=row["id"],
                task_type=row["task_type"],
                zone_id=row.get("zone_id"),
                summary=row["summary"],
                detail=FindingDetail(**{k: v for k, v in raw_detail.items() if k in FindingDetail.model_fields}),
                snapshot_url=snapshot_url,
                created_at=row["created_at"],
            )
        )
    return results
