"""Test helper functions (not a pytest conftest — avoids naming collision with
global site-packages/tests package)."""

TEST_RTSP_ENCRYPTION_KEY = "eH0I7ppuNWkf394Y2143HGgWpkWhGr45Gwyj1DEvd_4="


def encrypt_test_rtsp(url: str = "rtsp://test-cam.local/stream") -> bytes:
    """Return Fernet-encrypted bytes for use in test camera INSERTs."""
    from cryptography.fernet import Fernet

    return Fernet(TEST_RTSP_ENCRYPTION_KEY.encode()).encrypt(url.encode())
