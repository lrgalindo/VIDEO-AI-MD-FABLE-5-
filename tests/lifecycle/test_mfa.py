"""MFA relay tests (Sección 3.1 decisión 11d).

MFA is delegated entirely to Supabase Auth — no custom TOTP code.
These tests mock the Supabase HTTP calls with httpx mock transport so they
run without a live Supabase project.

Running:
    pytest tests/lifecycle/test_mfa.py -v

Coverage:
  - Login when MFA is enrolled → 401 with code=mfa_required
  - Successful TOTP verify → session returned to client
  - Wrong TOTP code → 401 from Supabase propagated to client
  - SUPABASE_URL not set → 503 service unavailable
"""

import json
from typing import Optional
from unittest.mock import MagicMock, patch

import httpx
import pytest
from fastapi.testclient import TestClient

from cloud.main import app

client = TestClient(app, raise_server_exceptions=False)


# ── httpx mock helpers ────────────────────────────────────────────────────────

def _make_response(status_code: int, body: dict) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        content=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        request=httpx.Request("POST", "https://mock.supabase.co/auth/v1/token"),
    )


# ── Supabase env patching ─────────────────────────────────────────────────────

_SUPABASE_ENV = {
    "SUPABASE_URL": "https://mock.supabase.co",
    "SUPABASE_ANON_KEY": "mock-anon-key",
}


# ── Tests: POST /v1/auth/login ────────────────────────────────────────────────

def test_login_mfa_required_returns_401():
    """When Supabase returns mfa_required, relay must respond with 401."""
    supabase_resp = _make_response(
        200,
        {
            "error_code": "mfa_required",
            "message": "MFA challenge required",
            "data": {
                "factors": [{"id": "factor-123", "type": "totp"}],
                "amr_challenge": {"id": "challenge-abc"},
            },
        },
    )
    with patch("cloud.auth.mfa.config") as mock_cfg, \
         patch("cloud.auth.mfa.httpx.Client") as mock_client_cls:
        mock_cfg.SUPABASE_URL = "https://mock.supabase.co"
        mock_cfg.SUPABASE_ANON_KEY = "mock-anon-key"
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value = supabase_resp
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/v1/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )

    assert resp.status_code == 401
    body = resp.json()
    # FastAPI wraps HTTPException detail in {"detail": ...}
    detail = body.get("detail", {})
    assert detail.get("code") == "mfa_required"


def test_login_success_without_mfa():
    """When Supabase returns a session (no MFA needed), relay it to client."""
    session = {
        "access_token": "sb-access-token",
        "refresh_token": "sb-refresh-token",
        "user": {"id": "user-id", "email": "user@test.com"},
    }
    supabase_resp = _make_response(200, session)

    with patch("cloud.auth.mfa.config") as mock_cfg, \
         patch("cloud.auth.mfa.httpx.Client") as mock_client_cls:
        mock_cfg.SUPABASE_URL = "https://mock.supabase.co"
        mock_cfg.SUPABASE_ANON_KEY = "mock-anon-key"
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value = supabase_resp
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/v1/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("access_token") == "sb-access-token"


def test_login_wrong_password_propagates_error():
    """Supabase 400 for wrong password is propagated as 400."""
    supabase_resp = _make_response(
        400,
        {"message": "Invalid login credentials", "error": "invalid_grant"},
    )
    with patch("cloud.auth.mfa.config") as mock_cfg, \
         patch("cloud.auth.mfa.httpx.Client") as mock_client_cls:
        mock_cfg.SUPABASE_URL = "https://mock.supabase.co"
        mock_cfg.SUPABASE_ANON_KEY = "mock-anon-key"
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value = supabase_resp
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/v1/auth/login",
            json={"email": "user@test.com", "password": "wrongpass"},
        )

    assert resp.status_code == 400


def test_login_503_when_supabase_not_configured():
    """Without SUPABASE_URL/ANON_KEY, endpoint returns 503 with an unambiguous config-gap message."""
    with patch("cloud.auth.mfa.config") as mock_cfg:
        mock_cfg.SUPABASE_URL = ""
        mock_cfg.SUPABASE_ANON_KEY = ""

        resp = client.post(
            "/v1/auth/login",
            json={"email": "user@test.com", "password": "password123"},
        )

    assert resp.status_code == 503
    body = resp.json()
    detail = body.get("detail", {})
    # Must be clearly "not configured" (deployment gap), not generic "unavailable"
    assert detail.get("code") == "mfa_not_configured"
    assert "SUPABASE_URL" in detail.get("message", "")


# ── Tests: POST /v1/auth/mfa/verify ──────────────────────────────────────────

def test_mfa_verify_valid_totp_returns_session():
    """Valid TOTP code → Supabase session is returned to the client."""
    session = {
        "access_token": "sb-mfa-access-token",
        "refresh_token": "sb-mfa-refresh-token",
        "user": {"id": "user-id"},
    }
    supabase_resp = _make_response(200, session)
    supabase_resp = httpx.Response(
        status_code=200,
        content=json.dumps(session).encode(),
        headers={"Content-Type": "application/json"},
        request=httpx.Request(
            "POST",
            "https://mock.supabase.co/auth/v1/factors/factor-123/verify",
        ),
    )

    with patch("cloud.auth.mfa.config") as mock_cfg, \
         patch("cloud.auth.mfa.httpx.Client") as mock_client_cls:
        mock_cfg.SUPABASE_URL = "https://mock.supabase.co"
        mock_cfg.SUPABASE_ANON_KEY = "mock-anon-key"
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value = supabase_resp
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/v1/auth/mfa/verify",
            json={
                "factor_id": "factor-123",
                "challenge_id": "challenge-abc",
                "code": "123456",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body.get("access_token") == "sb-mfa-access-token"


def test_mfa_verify_wrong_code_returns_401():
    """Wrong TOTP code → Supabase 401 is propagated to client."""
    error_resp = httpx.Response(
        status_code=401,
        content=json.dumps({"message": "Invalid TOTP code"}).encode(),
        headers={"Content-Type": "application/json"},
        request=httpx.Request(
            "POST",
            "https://mock.supabase.co/auth/v1/factors/factor-123/verify",
        ),
    )

    with patch("cloud.auth.mfa.config") as mock_cfg, \
         patch("cloud.auth.mfa.httpx.Client") as mock_client_cls:
        mock_cfg.SUPABASE_URL = "https://mock.supabase.co"
        mock_cfg.SUPABASE_ANON_KEY = "mock-anon-key"
        mock_instance = MagicMock()
        mock_instance.__enter__ = MagicMock(return_value=mock_instance)
        mock_instance.__exit__ = MagicMock(return_value=False)
        mock_instance.post.return_value = error_resp
        mock_client_cls.return_value = mock_instance

        resp = client.post(
            "/v1/auth/mfa/verify",
            json={
                "factor_id": "factor-123",
                "challenge_id": "challenge-abc",
                "code": "000000",
            },
        )

    assert resp.status_code == 401
