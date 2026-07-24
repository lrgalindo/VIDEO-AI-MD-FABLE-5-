"""Manages access + refresh tokens for cloud API calls from the Edge Gateway.

Tokens are persisted to TOKEN_FILE so they survive process restarts.
The client proactively refreshes when the access token is within 60 seconds
of expiry — avoiding hard 401s during normal operation.
"""

import json
import time
from pathlib import Path
from typing import Any

import requests

from edge import config


class AuthError(Exception):
    pass


class AuthClient:
    def __init__(
        self,
        cloud_api_url: str = config.CLOUD_API_URL,
        token_file: str = config.TOKEN_FILE,
    ) -> None:
        self._base = cloud_api_url.rstrip("/")
        self._token_file = Path(token_file)
        self._access_token: str = ""
        self._refresh_token: str = ""
        self._access_exp: float = 0.0
        self._load_tokens()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def activate(self, gateway_id: str, activation_code: str) -> None:
        """Exchange a one-time activation code for the initial token pair."""
        resp = requests.post(
            f"{self._base}/v1/edge/token/activate",
            json={"gateway_id": gateway_id, "activation_code": activation_code},
            timeout=30,
        )
        resp.raise_for_status()
        self._store(resp.json())

    def get(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("GET", path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> requests.Response:
        return self._request("POST", path, **kwargs)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _request(self, method: str, path: str, **kwargs: Any) -> requests.Response:
        self._ensure_fresh()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {self._access_token}"
        resp = requests.request(
            method, f"{self._base}{path}", headers=headers, timeout=30, **kwargs
        )
        if resp.status_code == 401:
            # One proactive retry after a fresh refresh
            self._refresh()
            headers["Authorization"] = f"Bearer {self._access_token}"
            resp = requests.request(
                method, f"{self._base}{path}", headers=headers, timeout=30, **kwargs
            )
        return resp

    def _ensure_fresh(self) -> None:
        if time.time() >= self._access_exp - 60:
            self._refresh()

    def _refresh(self) -> None:
        if not self._refresh_token:
            raise AuthError("No refresh token — gateway needs activation")
        resp = requests.post(
            f"{self._base}/v1/edge/token/refresh",
            json={
                "gateway_id": config.GATEWAY_ID,
                "refresh_token": self._refresh_token,
            },
            timeout=30,
        )
        if not resp.ok:
            raise AuthError(f"Token refresh failed: {resp.status_code}")
        self._store(resp.json())

    def _store(self, payload: dict) -> None:
        self._access_token = payload["access_token"]
        self._refresh_token = payload["refresh_token"]
        # access_token is a JWT; decode exp without verifying signature
        # (signature verified by the cloud; edge only needs the exp for scheduling)
        self._access_exp = self._decode_exp(self._access_token)
        data = {
            "access_token": self._access_token,
            "refresh_token": self._refresh_token,
            "access_exp": self._access_exp,
        }
        self._token_file.parent.mkdir(parents=True, exist_ok=True)
        self._token_file.write_text(json.dumps(data))

    def _load_tokens(self) -> None:
        if self._token_file.exists():
            try:
                data = json.loads(self._token_file.read_text())
                self._access_token = data.get("access_token", "")
                self._refresh_token = data.get("refresh_token", "")
                self._access_exp = float(data.get("access_exp", 0))
            except Exception:
                pass

    @staticmethod
    def _decode_exp(token: str) -> float:
        """Extract `exp` from a JWT payload without signature verification."""
        import base64
        try:
            payload_b64 = token.split(".")[1]
            padding = 4 - len(payload_b64) % 4
            payload = json.loads(base64.b64decode(payload_b64 + "=" * padding))
            return float(payload.get("exp", 0))
        except Exception:
            return 0.0
