"""Telemetry ingest endpoint (SDD §8.6).

POST /v1/telemetry/ingest
  Authenticates the Edge Gateway via JWT access token.
  Extracts site_id from the token and sets app.current_ingest_site_id so that
  the tracking_coordinates_ingest RLS policy (via sec_camera_on_ingest_site)
  is satisfied.
  Stores one event per request into tracking_coordinates.

Test-only endpoints (active when E2E_TEST_MODE=true):
  POST /v1/test/maintenance?seconds=N  — make ingest return 503 for N seconds
  GET  /v1/test/stats                  — row count in tracking_coordinates
"""

import os
import threading
import time
from contextlib import contextmanager
from datetime import datetime

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

import jwt

from cloud import config
from cloud.db import app_conn

router = APIRouter()
_bearer = HTTPBearer()

_maintenance_until: float = 0.0
_maintenance_lock = threading.Lock()


def _require_gateway_token(
    creds: HTTPAuthorizationCredentials = Security(_bearer),
) -> dict:
    try:
        return jwt.decode(
            creds.credentials,
            config.JWT_SECRET,
            algorithms=[config.JWT_ALGORITHM],
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token_expired")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="invalid_token")


class TrackingEvent(BaseModel):
    camera_id: str
    person_id: str
    x: int
    y: int
    time: datetime


@router.post("/v1/telemetry/ingest", status_code=204)
def ingest(
    event: TrackingEvent,
    token: dict = Depends(_require_gateway_token),
) -> None:
    with _maintenance_lock:
        if time.time() < _maintenance_until:
            raise HTTPException(status_code=503, detail="maintenance")

    site_id = str(token.get("sid", ""))
    if not site_id:
        raise HTTPException(status_code=401, detail="missing_sid")

    with app_conn(site_id) as cur:
        cur.execute(
            """
            INSERT INTO tracking_coordinates (camera_id, "time", person_id, x, y)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
            """,
            (event.camera_id, event.time, event.person_id, event.x, event.y),
        )


@contextmanager
def _superuser_conn():
    """Superuser connection for test-only operations that need full table access."""
    conn = psycopg2.connect(config.DATABASE_URL)
    try:
        with conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                yield cur
    finally:
        conn.close()


if os.environ.get("E2E_TEST_MODE") == "true":
    @router.post("/v1/test/maintenance", status_code=200)
    def set_maintenance(seconds: int = 60) -> dict:
        global _maintenance_until
        with _maintenance_lock:
            _maintenance_until = time.time() + seconds
        return {"maintenance_until": _maintenance_until, "seconds": seconds}

    @router.get("/v1/test/stats", status_code=200)
    def stats() -> dict:
        with _superuser_conn() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM tracking_coordinates")
            row = cur.fetchone()
        return {"count": int(row["n"])}
