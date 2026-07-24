"""Model Manager for the Edge Gateway (SDD §7.1, §9.1).

Responsibilities:
- Fetch the manifest for this gateway's vertical_type from the Cloud API.
  The manifest endpoint requires a valid access token — the auth_client is
  mandatory (no anonymous fallback; see security note below).
- Download the checkpoint (.pt file) with resumable Range requests.
- On signed-URL expiry (HTTP 403/410): re-fetch the manifest for a fresh URL —
  never retry the expired URL.
- Verify SHA-256 checksum before accepting the file.
  On mismatch: delete the partial file, retry up to max_retries times with
  exponential backoff (30 s, 60 s, …). A permanently corrupted source raises
  ChecksumError after all retries are exhausted.
- Cache the verified checkpoint under CACHE_DIR.
- Load exactly ONE model into memory at a time (SDD §7.2 RAM constraint).

Inference validation — confirmed 2026-07-21
-------------------------------------------
The full inference pipeline was validated end-to-end via validate_inference/:

  (a) Inference: ultralytics.YOLO() loaded yolov8n.pt; model.track() (ByteTrack,
      persist=True, tracker="bytetrack.yaml") returned person bounding boxes with
      confidence > 0.50 on 3 real images (bus.jpg, zidane.jpg, bus_bottom_crop.jpg).
      Max confidence observed: 0.885.

  (b) ByteTrack CONTINUITY (the property dwell_time depends on): an 8-frame
      synthetic sequence was generated from bus.jpg with 3px/frame horizontal shift
      to simulate subject motion. A fresh YOLO instance was used (no shared state
      with (a)). 100% of frame-0 person IDs ([2,3,4,5]) persisted through all 8
      frames — confirmed that track_id assignment is stable across a frame sequence,
      not reassigned per call.

      Note: prior to this validation, gateway.py called model(frame) instead of
      model.track(). model() does not engage ByteTrack — box.id was None on every
      frame, making each detection appear as a new person. This was a silent bug
      that pre-dated Fase 1. It is now fixed. See edge/tests/test_bytetrack_contract.py
      for CI regression guards that will catch any revert of this fix.

  (c) E2E pipeline: _yolo_detections() → InferenceQueue.enqueue() → flush() →
      XY bounds check. 3 person events enqueued and flushed, 0 failures, all
      centroids within frame bounds.

Validated with yolov8n.pt (ultralytics public checkpoint, same architecture as
yolo_retail.pt).  When a new custom checkpoint is released, re-run:

    ./validate_inference/run.sh --model /path/to/yolo_retail.pt

See validate_inference/run.sh for the full re-run policy (before each checkpoint
release, on inference code changes, and quarterly for version regression checks).

Security note
-------------
`auth_client` is required.  There is no anonymous fallback because:
- The manifest contains a pre-signed download URL for a model checkpoint.
- Allowing unauthenticated access would let anyone enumerate models and
  obtain download URLs without being an activated Edge Gateway.
- The cloud endpoint (/v1/models/{vertical_type}/manifest) enforces JWT auth;
  any request without a valid token returns 401.
"""

import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Callable, Optional

import requests

from edge import config

log = logging.getLogger(__name__)

_SIGNED_URL_EXPIRED = {403, 410}
_DOWNLOAD_CHUNK = 65_536  # 64 KiB
_CHECKSUM_RETRY_BASE = 30.0  # seconds before first retry after ChecksumError


class ChecksumError(Exception):
    pass


class ModelManager:
    def __init__(
        self,
        cloud_api_url: str = config.CLOUD_API_URL,
        vertical_type: str = config.VERTICAL_TYPE,
        cache_dir: str = config.CACHE_DIR,
        auth_client: Any = None,
        max_checksum_retries: int = 3,
    ) -> None:
        if auth_client is None:
            raise ValueError(
                "auth_client is required — ModelManager never calls the manifest "
                "endpoint without authentication (see module docstring)."
            )
        self._base = cloud_api_url.rstrip("/")
        self._vertical = vertical_type
        self._cache = Path(cache_dir)
        self._cache.mkdir(parents=True, exist_ok=True)
        self._auth = auth_client
        self._max_retries = max_checksum_retries
        self._loaded_version: Optional[str] = None
        self._model: Any = None  # ultralytics.YOLO instance when loaded

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def ensure_current(self, *, _sleep: Callable[[float], None] = time.sleep) -> Any:
        """Download/verify/load the model if it is missing or outdated.

        On ChecksumError (corrupt download from server), retries up to
        max_checksum_retries times with exponential backoff (30 s, 60 s, …).
        After all retries fail, re-raises ChecksumError — the gateway is unable
        to run inference and must surface this as a startup failure.

        The _sleep parameter exists solely for test injection — pass
        `_sleep=lambda _: None` to skip delays in unit tests.

        Returns the loaded model object (ultralytics.YOLO).
        """
        last_exc: Optional[ChecksumError] = None
        for attempt in range(self._max_retries):
            try:
                return self._try_ensure()
            except ChecksumError as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    delay = _CHECKSUM_RETRY_BASE * (2 ** attempt)
                    log.error(
                        "SHA-256 mismatch (attempt %d/%d) — retrying in %.0fs: %s",
                        attempt + 1, self._max_retries, delay, exc,
                    )
                    _sleep(delay)
                else:
                    log.error(
                        "SHA-256 mismatch on final attempt (%d/%d) — giving up: %s",
                        attempt + 1, self._max_retries, exc,
                    )
        raise last_exc  # type: ignore[misc]

    @property
    def model(self) -> Any:
        return self._model

    @property
    def loaded_version(self) -> Optional[str]:
        return self._loaded_version

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _try_ensure(self) -> Any:
        manifest = self._fetch_manifest()
        dest = self._cache / f"yolo_{self._vertical}_{manifest['version']}.pt"

        if not dest.exists() or not self._checksum_matches(dest, manifest["sha256"]):
            log.info("Downloading model v%s …", manifest["version"])
            self._download(manifest["download_url"], manifest["sha256"], manifest["size"], dest)

        if self._loaded_version != manifest["version"]:
            self._load(dest, manifest["version"])

        return self._model

    # ------------------------------------------------------------------
    # Manifest — always uses auth_client
    # ------------------------------------------------------------------

    def _fetch_manifest(self) -> dict:
        resp = self._auth.get(f"/v1/models/{self._vertical}/manifest")
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Resumable download (SDD §9.1)
    # ------------------------------------------------------------------

    def _download(
        self,
        url: str,
        expected_sha256: str,
        total_size: int,
        dest: Path,
    ) -> None:
        """Download to dest with Range-header resumption.

        If the signed URL returns 403 or 410 (expired), the method re-fetches
        the manifest to obtain a fresh URL and resumes from the byte offset
        already written — it never retries the expired URL.
        """
        tmp = dest.with_suffix(".part")
        while True:
            offset = tmp.stat().st_size if tmp.exists() else 0
            if offset >= total_size:
                break

            headers: dict = {"Range": f"bytes={offset}-"}
            try:
                resp = requests.get(url, headers=headers, stream=True, timeout=60)
            except requests.RequestException as exc:
                log.warning("Download error at offset %d: %s — will resume", offset, exc)
                continue

            if resp.status_code in _SIGNED_URL_EXPIRED:
                log.info("Signed URL expired (HTTP %d) — re-fetching manifest", resp.status_code)
                fresh = self._fetch_manifest()
                url = fresh["download_url"]
                continue

            if resp.status_code not in (200, 206):
                resp.raise_for_status()

            with tmp.open("ab") as fh:
                for chunk in resp.iter_content(chunk_size=_DOWNLOAD_CHUNK):
                    if chunk:
                        fh.write(chunk)
                        offset += len(chunk)

        self._verify_checksum(tmp, expected_sha256)
        tmp.rename(dest)
        log.info("Model saved to %s", dest)

    # ------------------------------------------------------------------
    # Checksum
    # ------------------------------------------------------------------

    @staticmethod
    def _checksum_matches(path: Path, expected: str) -> bool:
        try:
            return ModelManager._sha256(path) == expected
        except OSError:
            return False

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65_536), b""):
                h.update(chunk)
        return h.hexdigest()

    @staticmethod
    def _verify_checksum(path: Path, expected: str) -> None:
        actual = ModelManager._sha256(path)
        if actual != expected:
            path.unlink(missing_ok=True)
            raise ChecksumError(
                f"SHA-256 mismatch: expected {expected}, got {actual}"
            )

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def _load(self, path: Path, version: str) -> None:
        """Load the model into memory, releasing the previous one first.

        If ultralytics is not installed (e.g. the smoke-test Docker image),
        stores the sentinel string "STUB" so callers can fall back to synthetic
        inference without a hard failure.
        """
        log.info("Loading model v%s from %s", version, path)
        self._model = None  # release previous reference before loading new one
        try:
            from ultralytics import YOLO  # imported here to allow mocking in tests
            self._model = YOLO(str(path))
            log.info("Model v%s loaded — %s is now the only checkpoint in memory", version, path.name)
        except ImportError:
            log.warning(
                "ultralytics not installed — model v%s verified (SHA-256 OK) but running in STUB mode",
                version,
            )
            self._model = "STUB"
        self._loaded_version = version
