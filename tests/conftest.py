"""Root conftest: sets up environment variables required before cloud.config is imported.

Applies to all tests under tests/ (backoffice, actions, copilot, findings, etc.).
The edge/ tests have their own conftest and don't import cloud.config.
"""

import os

# Fixed test key — never use in production.
# SQL seeds were pre-encrypted with this key (see comments in seed files).
TEST_RTSP_ENCRYPTION_KEY = "eH0I7ppuNWkf394Y2143HGgWpkWhGr45Gwyj1DEvd_4="

# Set before any cloud.* import so cloud.config doesn't raise ValueError.
os.environ.setdefault("RTSP_ENCRYPTION_KEY", TEST_RTSP_ENCRYPTION_KEY)
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-for-pytest")


def encrypt_test_rtsp(url: str = "rtsp://test-cam.local/stream") -> bytes:
    """Return Fernet-encrypted bytes for use in test camera INSERTs."""
    from cryptography.fernet import Fernet

    return Fernet(TEST_RTSP_ENCRYPTION_KEY.encode()).encrypt(url.encode())
