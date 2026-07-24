"""Fake YOLO checkpoint served by the Cloud API in E2E smoke tests.

The bytes are deterministic so the SHA-256 is stable across rebuilds.
The edge gateway downloads this file, verifies the checksum, and loads it —
but ultralytics is not installed in the smoke-test container so _load() falls
back to STUB mode and the gateway uses synthetic inference instead.
"""

import hashlib

FAKE_MODEL_BYTES: bytes = b"TRAXIA-FAKE-YOLO-RETAIL-V1.0\x00" * 400 + b"\x00PAD" * 100
FAKE_MODEL_SHA256: str = hashlib.sha256(FAKE_MODEL_BYTES).hexdigest()
FAKE_MODEL_SIZE: int = len(FAKE_MODEL_BYTES)
FAKE_MODEL_VERSION: str = "1.0.0"
