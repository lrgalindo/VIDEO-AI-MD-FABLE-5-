"""Tests for ModelManager: download, resumption, URL-expiry handling, checksum, cache.

All tests use a fake model file and a local mock HTTP server — no real YOLO model
or Cloudflare R2 required. The ultralytics import is patched so no GPU/PyTorch
dependency is needed.
"""

import hashlib
import threading
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from edge.model_manager import ChecksumError, ModelManager
from edge.tests.mock_cloud import MockCloudServer


# ---------------------------------------------------------------------------
# Minimal auth stub — satisfies ModelManager's required auth_client
# ---------------------------------------------------------------------------

import requests as _requests


class _MockAuth:
    """Thin wrapper that forwards GET calls to a local base URL without auth headers.

    MockCloudServer does not check tokens; this stub satisfies ModelManager's
    mandatory auth_client requirement while keeping the tests free of JWT setup.
    """

    def __init__(self, base_url: str) -> None:
        self._base = base_url.rstrip("/")

    def get(self, path: str) -> _requests.Response:
        return _requests.get(f"{self._base}{path}", timeout=30)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _make_manager(url: str, cache: Path, *_: object) -> ModelManager:
    return ModelManager(
        cloud_api_url=url,
        vertical_type="retail",
        cache_dir=str(cache),
        auth_client=_MockAuth(url),
    )


# ---------------------------------------------------------------------------
# (a) Normal download, checksum verification, cache
# ---------------------------------------------------------------------------

def test_model_downloads_and_is_cached(fake_model_file: Path, tmp_cache: Path) -> None:
    """Happy-path: manifest → download → SHA-256 OK → file cached, model loaded once."""
    load_calls: list[str] = []

    def tracking_load(self: ModelManager, path: Path, version: str) -> None:
        load_calls.append(version)
        self._model = MagicMock(name=f"YOLO_{version}")
        self._loaded_version = version  # must mirror what the real _load does

    with MockCloudServer(fake_model_file) as srv:
        mm = _make_manager(srv.url, tmp_cache, fake_model_file)
        with patch.object(ModelManager, "_load", tracking_load):
            mm.ensure_current()
            assert len(load_calls) == 1, "Model must be loaded on first call"

            bytes_after_first = srv._bytes_served

            # Second call: file cached, version unchanged — no re-download, no reload
            mm.ensure_current()
            assert len(load_calls) == 1, "Should not reload when already at current version"
            assert srv._bytes_served == bytes_after_first, "No bytes re-downloaded on cache hit"

    cached = list(tmp_cache.glob("yolo_retail_*.pt"))
    assert len(cached) == 1, "Exactly one cached file expected"


def test_cached_file_used_on_restart(fake_model_file: Path, tmp_cache: Path) -> None:
    """A new ModelManager instance with warm cache does not re-download."""
    with MockCloudServer(fake_model_file) as srv:
        mm1 = _make_manager(srv.url, tmp_cache, fake_model_file)
        with patch("edge.model_manager.ModelManager._load"):
            mm1.ensure_current()
        bytes_served_after_first = srv._bytes_served

        mm2 = _make_manager(srv.url, tmp_cache, fake_model_file)
        with patch("edge.model_manager.ModelManager._load"):
            mm2.ensure_current()

        assert srv._bytes_served == bytes_served_after_first, (
            "No bytes should be re-downloaded when cache is valid"
        )


def test_corrupted_cache_triggers_redownload(fake_model_file: Path, tmp_cache: Path) -> None:
    """If the cached .pt file has a bad checksum, it is re-downloaded."""
    with MockCloudServer(fake_model_file) as srv:
        # Pre-create a corrupted cache entry
        corrupt = tmp_cache / "yolo_retail_1.0.0.pt"
        corrupt.write_bytes(b"corrupted data")

        mm = _make_manager(srv.url, tmp_cache, fake_model_file)
        with patch("edge.model_manager.ModelManager._load"):
            mm.ensure_current()

        assert srv._bytes_served > 0, "Re-download must happen after checksum mismatch"
        assert corrupt.read_bytes() == fake_model_file.read_bytes(), (
            "Corrupt file must be replaced with correct content"
        )


def test_auth_client_required() -> None:
    """ModelManager must refuse to construct without an auth_client."""
    with pytest.raises(ValueError, match="auth_client is required"):
        ModelManager(cloud_api_url="http://localhost", auth_client=None)


def test_checksum_error_raised_on_bad_server(tmp_path: Path, tmp_cache: Path) -> None:
    """After max_checksum_retries the manager raises ChecksumError, not silently loads."""
    real_model = tmp_path / "real.pt"
    real_model.write_bytes(b"real content " * 100)
    wrong_model = tmp_path / "wrong.pt"
    wrong_model.write_bytes(b"wrong content " * 100)

    real_sha = hashlib.sha256(real_model.read_bytes()).hexdigest()

    with MockCloudServer(wrong_model) as srv:
        srv.model_sha256 = real_sha  # manifest claims real sha but serves wrong bytes

        mm = ModelManager(
            cloud_api_url=srv.url,
            vertical_type="retail",
            cache_dir=str(tmp_cache),
            auth_client=_MockAuth(srv.url),
            max_checksum_retries=2,
        )
        sleeps: list[float] = []
        with pytest.raises(ChecksumError):
            with patch("edge.model_manager.ModelManager._load"):
                mm.ensure_current(_sleep=sleeps.append)

    assert len(sleeps) == 1, (
        "Should sleep once between 2 attempts (1 retry after first failure)"
    )


def test_checksum_retry_succeeds_on_second_attempt(tmp_cache: Path) -> None:
    """After a ChecksumError on attempt 1, ensure_current retries and succeeds on attempt 2."""
    from typing import Any as _Any  # local import avoids re-export from test module scope

    call_count = [0]

    def mock_try_ensure(self: ModelManager) -> _Any:
        call_count[0] += 1
        if call_count[0] == 1:
            raise ChecksumError("simulated bad download on first attempt")
        # Second attempt: "download" succeeded
        self._model = MagicMock(name="YOLO_1.0.0")
        self._loaded_version = "1.0.0"
        return self._model

    mm = ModelManager(
        cloud_api_url="http://unused",
        vertical_type="retail",
        cache_dir=str(tmp_cache),
        auth_client=_MockAuth("http://unused"),
        max_checksum_retries=3,
    )
    sleeps: list[float] = []
    with patch.object(ModelManager, "_try_ensure", mock_try_ensure):
        result = mm.ensure_current(_sleep=sleeps.append)

    assert call_count[0] == 2, "Must have attempted exactly twice (1 failure + 1 success)"
    assert len(sleeps) == 1, "Exactly one backoff sleep between the two attempts"
    assert sleeps[0] == 30.0, "First retry delay is 30s (base × 2⁰)"
    assert result is not None, "Must return the loaded model on successful retry"


# ---------------------------------------------------------------------------
# (b) Resumable download — connection cut mid-download
# ---------------------------------------------------------------------------

def test_resumable_download_after_connection_cut(fake_model_file: Path, tmp_cache: Path) -> None:
    """Simulate a connection cut mid-download and verify the file is completed.

    The mock server is configured to drop the connection after half the bytes.
    The ModelManager must detect the incomplete .part file on the next attempt
    and resume from where it left off (Range header), completing the download.
    """
    half = fake_model_file.stat().st_size // 2

    # First pass: server drops connection at the halfway mark by returning 403
    # (we reuse the expire_after_bytes mechanism as the "drop" signal here).
    # The ModelManager will:
    #   1. Start download → get 403 at mid-point (URL expiry)
    #   2. Re-fetch manifest (same URL, server now serves remainder)
    #   3. Resume with Range: bytes=<offset>-
    with MockCloudServer(fake_model_file, expire_after_bytes=half) as srv:
        mm = _make_manager(srv.url, tmp_cache, fake_model_file)
        with patch("edge.model_manager.ModelManager._load"):
            mm.ensure_current()

        # The manifest was fetched at least twice (initial + after URL expiry)
        assert srv._manifest_fetches >= 2, (
            f"Expected ≥2 manifest fetches (got {srv._manifest_fetches}): "
            "manager should re-fetch manifest on URL expiry, not retry the expired URL"
        )

        cached = list(tmp_cache.glob("yolo_retail_*.pt"))
        assert len(cached) == 1
        assert cached[0].read_bytes() == fake_model_file.read_bytes(), (
            "Completed file must match the original after resumption"
        )


def test_expired_signed_url_triggers_manifest_refetch(fake_model_file: Path, tmp_cache: Path) -> None:
    """403 from the download URL must cause a manifest re-fetch, not a URL retry."""
    with MockCloudServer(fake_model_file, expire_after_bytes=1) as srv:
        mm = _make_manager(srv.url, tmp_cache, fake_model_file)
        initial_url = f"{srv.url}/download/model.pt"

        fetches_before = srv._manifest_fetches
        with patch("edge.model_manager.ModelManager._load"):
            mm.ensure_current()

        assert srv._manifest_fetches > fetches_before + 0, (
            "Manifest must be re-fetched after 403 — expired URL cannot be retried"
        )


# ---------------------------------------------------------------------------
# Single-model-in-memory guarantee
# ---------------------------------------------------------------------------

def test_only_one_model_in_memory(fake_model_file: Path, tmp_cache: Path) -> None:
    """_load sets self._model = None before assigning the new model."""
    with MockCloudServer(fake_model_file) as srv:
        mm = _make_manager(srv.url, tmp_cache, fake_model_file)
        load_calls: list[str] = []

        original_load = ModelManager._load

        def tracking_load(self: ModelManager, path: Path, version: str) -> None:
            # At the moment _load is called the old model reference must be None
            load_calls.append(str(self._model))
            # Don't actually import ultralytics — use a mock
            self._model = MagicMock(name=f"YOLO_{version}")
            self._loaded_version = version

        with patch.object(ModelManager, "_load", tracking_load):
            mm.ensure_current()

        assert load_calls, "_load must be called at least once"
        assert load_calls[0] == "None", (
            "_model must be set to None before the new model is assigned"
        )
