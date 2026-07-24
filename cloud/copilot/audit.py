"""Stock audit task — SDD §12.5.

Detects dwell-time drops in zones and audits them with Claude vision.

Flow:
  1. _find_dwell_drops() — cross-tenant scan (superuser) finds zones where
     avg dwell time in the last 2h is <50% of the 7-day baseline.
     This is the "caída de Dwell Time detectada por el Motor Matemático" trigger.
  2. _fetch_snapshot(zone_id) — in production fetches the most recent camera
     snapshot from R2 (Cloudflare/S3 compatible).  In MLP without R2, uses a
     1×1 white JPEG placeholder so the audit code path is fully exercised.
  3. _audit_zone_with_vision() — sends snapshot + context to Claude Sonnet
     (with vision, Batch API model for cost efficiency) and returns the finding.
  4. _persist_finding() — writes to agent_findings via traxia_service (RLS-safe).

All findings are scoped strictly to the tenant/zone they belong to — the
persistence step sets tenant_id from the zone's owning tenant, not from any
parameter the caller controls.
"""

import base64
import logging
import uuid
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

from cloud import config
from cloud.db import service_conn

log = logging.getLogger(__name__)

# Threshold: last 2h avg < this fraction of 7-day baseline triggers audit
DWELL_DROP_THRESHOLD = 0.5
# Minimum baseline sessions to consider the drop meaningful (avoid noise on new zones)
MIN_BASELINE_SESSIONS = 5

# 64×64 gray JPEG — placeholder snapshot when no real camera frame is available.
# Claude Vision rejects 1×1 images with 400; we need a processable image.
# Loaded from file at import time to avoid base64 line-split corruption.
import pathlib as _pathlib
_PLACEHOLDER_JPEG_B64: str = __import__("base64").b64encode(
    (_pathlib.Path(__file__).parent / "_snapshot_placeholder.jpg").read_bytes()
).decode()


def _find_dwell_drops() -> List[Dict[str, Any]]:
    """Scan all zones for significant dwell time drops. Runs as DB owner (no RLS)."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT
                        z.id::text           AS zone_id,
                        z.name               AS zone_name,
                        z.zone_type,
                        t.id::text           AS tenant_id,
                        s.id::text           AS site_id,
                        z.owner_partner_id::text AS partner_id,
                        COALESCE(AVG(CASE WHEN zds.entered_at >= now() - interval '2 hours'
                                         THEN zds.dwell_seconds END), 0)::int
                                             AS recent_avg_dwell,
                        COALESCE(AVG(CASE WHEN zds.entered_at < now() - interval '2 hours'
                                          AND zds.entered_at >= now() - interval '7 days'
                                         THEN zds.dwell_seconds END), 0)::int
                                             AS baseline_avg_dwell,
                        COUNT(CASE WHEN zds.entered_at >= now() - interval '7 days'
                                   THEN 1 END)::int
                                             AS baseline_sessions
                    FROM zones z
                    JOIN cameras c ON c.id = z.camera_id
                    JOIN sites s ON s.id = c.site_id
                    JOIN tenants t ON t.id = s.tenant_id
                    LEFT JOIN zone_dwell_sessions zds ON zds.zone_id = z.id
                    WHERE t.status = 'active'
                    GROUP BY z.id, z.name, z.zone_type, t.id, s.id, z.owner_partner_id
                    HAVING
                        COUNT(CASE WHEN zds.entered_at >= now() - interval '7 days' THEN 1 END) >= %s
                        AND COALESCE(AVG(CASE WHEN zds.entered_at < now() - interval '2 hours'
                                              AND zds.entered_at >= now() - interval '7 days'
                                             THEN zds.dwell_seconds END), 0) > 0
                        AND COALESCE(AVG(CASE WHEN zds.entered_at >= now() - interval '2 hours'
                                             THEN zds.dwell_seconds END), 0)
                            < %s * COALESCE(AVG(CASE WHEN zds.entered_at < now() - interval '2 hours'
                                                     AND zds.entered_at >= now() - interval '7 days'
                                                    THEN zds.dwell_seconds END), 0)
                    """,
                    (MIN_BASELINE_SESSIONS, DWELL_DROP_THRESHOLD),
                )
                return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def _fetch_snapshot(zone_id: str) -> Optional[str]:
    """Fetch most recent snapshot for a zone from R2 (or placeholder in dev).

    In production: query r2_snapshots table / call R2 pre-signed URL.
    In MLP dev (no R2): return a 1×1 placeholder JPEG so the code path works.
    Returns base64-encoded JPEG string.
    """
    if not config.ANTHROPIC_API_KEY:
        return None
    # Production: look up snapshot URL from object storage, fetch bytes
    # For MLP: use placeholder
    return _PLACEHOLDER_JPEG_B64


def _upload_snapshot_to_r2(zone_id: str, run_id: str, snapshot_b64: str) -> Optional[str]:
    """Upload a base64-encoded JPEG snapshot to R2 and return its object key.

    Returns None (silently) if R2 credentials are not configured — the audit
    cycle continues and the finding is persisted without a snapshot URL.
    The key format is deterministic: snapshots/{zone_id}/{run_id}.jpg
    """
    if not (config.R2_ACCOUNT_ID and config.R2_ACCESS_KEY_ID and config.R2_SECRET_ACCESS_KEY):
        return None
    try:
        import boto3  # lazy import — only needed when R2 is configured
        import base64 as _b64
        endpoint = config.R2_ENDPOINT_URL or f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )
        key = f"snapshots/{zone_id}/{run_id}.jpg"
        image_bytes = _b64.b64decode(snapshot_b64)
        s3.put_object(
            Bucket=config.R2_BUCKET_SNAPSHOTS,
            Key=key,
            Body=image_bytes,
            ContentType="image/jpeg",
        )
        log.debug("Snapshot uploaded to R2: %s", key)
        return key
    except Exception as exc:
        log.warning("R2 snapshot upload failed for zone %s: %s — continuing without snapshot URL", zone_id, exc)
        return None


def _audit_zone_with_vision(zone: Dict[str, Any], snapshot_b64: str) -> str:
    """Send zone snapshot + context to Claude Sonnet for stock audit analysis."""
    import anthropic

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    zone_ctx = (
        f"Zone: {zone['zone_name']} (type={zone['zone_type']})\n"
        f"Recent avg dwell: {zone['recent_avg_dwell']}s\n"
        f"7-day baseline avg dwell: {zone['baseline_avg_dwell']}s\n"
        f"Drop ratio: {zone['recent_avg_dwell'] / max(zone['baseline_avg_dwell'], 1):.1%}"
    )

    response = client.messages.create(
        model=config.ANTHROPIC_MODEL_AUDIT,
        max_tokens=512,
        system=(
            "You are a retail operations auditor. You analyze camera snapshots of "
            "store zones to detect stock issues. Be specific and concise. "
            "Focus on visible shelf conditions, empty spaces, or obstructions. "
            "If the image is unclear or insufficient, say so explicitly."
        ),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": snapshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            f"This zone has a significant drop in customer dwell time:\n\n"
                            f"{zone_ctx}\n\n"
                            "Analyze the snapshot for possible stock issues (empty shelves, "
                            "misplaced products, obstructions). Report your finding in 2-3 sentences."
                        ),
                    },
                ],
            }
        ],
    )
    return response.content[0].text


def _persist_finding(
    zone: Dict[str, Any],
    summary: str,
    detail: Dict[str, Any],
    run_id: str,
) -> None:
    with service_conn() as cur:
        cur.execute(
            """
            INSERT INTO agent_findings
                (tenant_id, partner_id, site_id, zone_id, task_type, summary, detail, run_id)
            VALUES (%s, %s, %s, %s, 'stock_audit', %s, %s::jsonb, %s)
            """,
            (
                zone["tenant_id"],
                zone.get("partner_id"),
                zone["site_id"],
                zone["zone_id"],
                summary[:500],
                psycopg2.extras.Json(detail),
                run_id,
            ),
        )


def run_stock_audit_cycle() -> int:
    """Run one audit cycle. Returns number of zones audited."""
    if not config.ANTHROPIC_API_KEY:
        log.debug("Stock audit skipped — ANTHROPIC_API_KEY not configured")
        return 0

    drops = _find_dwell_drops()
    if not drops:
        log.debug("Stock audit: no dwell drops detected")
        return 0

    log.info("Stock audit: %d zones with dwell drop", len(drops))
    run_id = str(uuid.uuid4())
    audited = 0

    for zone in drops:
        try:
            snapshot = _fetch_snapshot(zone["zone_id"])
            if snapshot is None:
                summary = (
                    f"Dwell drop detected in {zone['zone_name']}: "
                    f"{zone['recent_avg_dwell']}s vs {zone['baseline_avg_dwell']}s baseline. "
                    f"No snapshot available for visual audit."
                )
                detail = {
                    "recent_avg_dwell": zone["recent_avg_dwell"],
                    "baseline_avg_dwell": zone["baseline_avg_dwell"],
                    "snapshot_available": False,
                }
            else:
                finding_text = _audit_zone_with_vision(zone, snapshot)
                r2_key = _upload_snapshot_to_r2(zone["zone_id"], run_id, snapshot)
                summary = f"{zone['zone_name']}: {finding_text[:200]}"
                detail: Dict[str, Any] = {
                    "recent_avg_dwell": zone["recent_avg_dwell"],
                    "baseline_avg_dwell": zone["baseline_avg_dwell"],
                    "vision_finding": finding_text,
                    "snapshot_available": True,
                }
                if r2_key:
                    detail["snapshot_r2_key"] = r2_key

            _persist_finding(zone, summary, detail, run_id)
            audited += 1
        except Exception as exc:
            log.error("Audit failed for zone %s: %s", zone["zone_id"], exc)

    return audited
