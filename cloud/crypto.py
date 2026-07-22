"""Symmetric encryption for RTSP credentials stored in the cameras table.

Uses Fernet (AES-128-CBC + HMAC-SHA256) from the `cryptography` package.
Key is loaded from RTSP_ENCRYPTION_KEY (URL-safe base64-encoded 32 bytes).

Generate a key:
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""

from cryptography.fernet import Fernet

from cloud import config


def _fernet() -> Fernet:
    return Fernet(config.RTSP_ENCRYPTION_KEY.encode())


def encrypt_rtsp_url(url: str) -> bytes:
    """Encrypt an RTSP URL.  Returns raw ciphertext bytes (store in BYTEA)."""
    return _fernet().encrypt(url.encode())


def decrypt_rtsp_url(ciphertext: bytes) -> str:
    """Decrypt ciphertext bytes back to the original RTSP URL string."""
    return _fernet().decrypt(ciphertext).decode()
